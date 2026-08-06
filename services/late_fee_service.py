"""Late fee service for platform billing (Phase 2)

Late fees live in the platform ledger only (PlatformSubscription +
LateFeeCharge). No school-GL entries are written here — platform fees are
Termly's receivable, not the school's revenue, and the collectible total
is computed as total_amount_due + late_fee_amount - discount_amount by
services/platform_billing_service.py::subscription_outstanding().
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, LateFeeCharge, BillingConfiguration, SubscriptionStatus
)

logger = logging.getLogger(__name__)


class LateFeeService:
    """Manages late fee calculation and application"""
    
    async def check_and_apply_late_fees(
        self,
        session: AsyncSession,
        school_id: str
    ) -> Dict:
        """
        Check all subscriptions and apply late fees if applicable
        
        Returns count of subscriptions with late fees applied
        """
        try:
            # Get billing configuration
            config = await self._get_config(session, school_id)
            if not config or not config.enable_late_fees:
                return {"success": False, "message": "Late fees disabled"}
            
            # Get all overdue subscriptions without late fees
            result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.school_id == school_id,
                    PlatformSubscription.status.in_([
                        SubscriptionStatus.PENDING,
                        SubscriptionStatus.SUSPENDED
                    ]),
                    PlatformSubscription.amount_paid < PlatformSubscription.total_amount_due,
                    PlatformSubscription.late_fee_amount == 0.0  # Not yet charged
                )
            )
            subscriptions = result.scalars().all()
            
            count = 0
            for sub in subscriptions:
                # Check if subscription is past grace period
                days_overdue = (datetime.utcnow() - sub.due_date).days
                
                if days_overdue > config.grace_period_days:
                    # Apply late fee
                    apply_result = await self.apply_late_fee(
                        session,
                        sub.id,
                        config.late_fee_percentage,
                        config.max_late_fee
                    )
                    
                    if apply_result.get("success"):
                        count += 1
            
            await session.commit()
            
            return {
                "success": True,
                "subscriptions_with_late_fees": count,
                "message": f"Applied late fees to {count} subscriptions"
            }
            
        except Exception as e:
            logger.error(f"Error applying late fees: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def apply_late_fee(
        self,
        session: AsyncSession,
        subscription_id: str,
        late_fee_percentage: float,
        max_late_fee: Optional[float] = None
    ) -> Dict:
        """
        Apply late fee to a specific subscription
        
        Returns the late fee amount applied
        """
        try:
            # Get subscription
            sub_result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.id == subscription_id
                )
            )
            subscription = sub_result.scalar_one_or_none()
            
            if not subscription:
                return {"success": False, "error": "Subscription not found"}
            
            if subscription.late_fee_amount > 0:
                return {"success": False, "error": "Late fee already applied"}
            
            # Calculate late fee
            outstanding_balance = subscription.total_amount_due - subscription.amount_paid
            
            if outstanding_balance <= 0:
                return {"success": False, "error": "No outstanding balance"}
            
            late_fee = (outstanding_balance * late_fee_percentage) / 100
            
            # Apply cap if configured
            if max_late_fee and late_fee > max_late_fee:
                late_fee = max_late_fee
            
            late_fee = round(late_fee, 2)

            # Update subscription. Derive from total_amount_due directly
            # rather than after_discount, which is 0.0 on rows generated
            # before it was initialized at creation time.
            base_after_discount = round(
                subscription.total_amount_due - subscription.discount_amount, 2
            )
            subscription.late_fee_amount = late_fee
            subscription.late_fee_applied_date = datetime.utcnow()
            subscription.after_discount = base_after_discount
            subscription.final_amount_due = round(base_after_discount + late_fee, 2)
            subscription.updated_at = datetime.utcnow()

            # Create late fee charge record — the append-only audit row for
            # this charge (never updated, even if the fee is later waived).
            late_fee_charge = LateFeeCharge(
                subscription_id=subscription_id,
                school_id=subscription.school_id,
                outstanding_balance=outstanding_balance,
                late_fee_percentage=late_fee_percentage,
                late_fee_amount=late_fee,
                max_late_fee=max_late_fee
            )

            session.add(late_fee_charge)
            await session.commit()
            
            logger.info(
                f"Applied late fee to subscription {subscription_id}: "
                f"GHS {late_fee}"
            )
            
            return {
                "success": True,
                "late_fee_amount": late_fee,
                "total_due_now": subscription.final_amount_due
            }
            
        except Exception as e:
            logger.error(f"Error applying late fee: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def waive_late_fee(
        self,
        session: AsyncSession,
        subscription_id: str,
        reason: str = "Manual waiver"
    ) -> Dict:
        """
        Waive (cancel) late fee for a subscription
        """
        try:
            sub_result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.id == subscription_id
                )
            )
            subscription = sub_result.scalar_one_or_none()
            
            if not subscription:
                return {"success": False, "error": "Subscription not found"}
            
            if subscription.late_fee_amount == 0:
                return {"success": False, "error": "No late fee to waive"}
            
            # Store original amount for audit
            original_late_fee = subscription.late_fee_amount

            # Clear late fee. Same defensive derivation as apply_late_fee —
            # after_discount is 0.0 on pre-initialization rows, and using it
            # directly would zero out the school's entire balance.
            base_after_discount = round(
                subscription.total_amount_due - subscription.discount_amount, 2
            )
            subscription.late_fee_amount = 0.0
            subscription.after_discount = base_after_discount
            subscription.final_amount_due = base_after_discount
            subscription.updated_at = datetime.utcnow()

            await session.commit()
            
            logger.info(
                f"Waived late fee for subscription {subscription_id}: "
                f"GHS {original_late_fee} ({reason})"
            )
            
            return {
                "success": True,
                "waived_amount": original_late_fee,
                "new_total_due": subscription.final_amount_due,
                "reason": reason
            }
            
        except Exception as e:
            logger.error(f"Error waiving late fee: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_late_fee_details(
        self,
        session: AsyncSession,
        subscription_id: str
    ) -> Optional[Dict]:
        """Get late fee details for a subscription"""
        try:
            # Get late fee charge record
            result = await session.execute(
                select(LateFeeCharge).where(
                    LateFeeCharge.subscription_id == subscription_id
                )
            )
            charge = result.scalar_one_or_none()
            
            if not charge:
                return None
            
            return {
                "id": charge.id,
                "outstanding_balance": charge.outstanding_balance,
                "late_fee_percentage": charge.late_fee_percentage,
                "late_fee_amount": charge.late_fee_amount,
                "applied_date": charge.applied_date.isoformat(),
                "journal_entry_id": charge.journal_entry_id
            }
            
        except Exception as e:
            logger.error(f"Error getting late fee details: {str(e)}")
            return None
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    async def _get_config(
        self,
        session: AsyncSession,
        school_id: str
    ) -> Optional[BillingConfiguration]:
        """Get billing configuration for school"""
        result = await session.execute(
            select(BillingConfiguration).where(
                BillingConfiguration.school_id == school_id
            )
        )
        return result.scalar_one_or_none()

