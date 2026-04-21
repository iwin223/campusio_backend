"""Late fee service for platform billing (Phase 2)"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, LateFeeCharge, BillingConfiguration, SubscriptionStatus
)
from models.finance import JournalEntry, JournalLineItem, PostingStatus, ReferenceType

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
            
            # Update subscription
            subscription.late_fee_amount = late_fee
            subscription.late_fee_applied_date = datetime.utcnow()
            subscription.final_amount_due = subscription.after_discount + late_fee
            
            # Create late fee charge record
            late_fee_charge = LateFeeCharge(
                subscription_id=subscription_id,
                school_id=subscription.school_id,
                outstanding_balance=outstanding_balance,
                late_fee_percentage=late_fee_percentage,
                late_fee_amount=late_fee,
                max_late_fee=max_late_fee
            )
            
            session.add(late_fee_charge)
            await session.flush()
            
            # Create GL entry for late fee
            gl_result = await self._create_late_fee_gl_entry(
                session,
                subscription.school_id,
                late_fee,
                subscription_id
            )
            
            if gl_result.get("success"):
                late_fee_charge.journal_entry_id = gl_result.get("entry_id")
                subscription.late_fee_journal_entry_id = gl_result.get("entry_id")
            
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
            
            # Clear late fee
            subscription.late_fee_amount = 0.0
            subscription.final_amount_due = subscription.after_discount
            
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
    
    async def _create_late_fee_gl_entry(
        self,
        session: AsyncSession,
        school_id: str,
        late_fee_amount: float,
        subscription_id: str
    ) -> Dict:
        """Create GL journal entry for late fee"""
        try:
            entry_id = f"JE-{uuid.uuid4().hex[:12].upper()}"
            
            entry = JournalEntry(
                id=entry_id,
                school_id=school_id,
                entry_date=datetime.utcnow(),
                reference_type=ReferenceType.PLATFORM_SUBSCRIPTION,
                reference_id=subscription_id,
                description=f"Late fee charge - Platform subscription",
                total_debit=late_fee_amount,
                total_credit=late_fee_amount,
                posting_status=PostingStatus.POSTED,
                posted_date=datetime.utcnow(),
                created_by="SYSTEM"
            )
            
            # Debit: Accounts Receivable (1200)
            debit_line = JournalLineItem(
                id=f"JLI-{uuid.uuid4().hex[:12].upper()}",
                journal_entry_id=entry_id,
                school_id=school_id,
                gl_account_id="1200",
                debit=late_fee_amount,
                credit=0
            )
            
            # Credit: Late Fee Income (4260)
            credit_line = JournalLineItem(
                id=f"JLI-{uuid.uuid4().hex[:12].upper()}",
                journal_entry_id=entry_id,
                school_id=school_id,
                gl_account_id="4260",
                debit=0,
                credit=late_fee_amount
            )
            
            session.add(entry)
            session.add(debit_line)
            session.add(credit_line)
            
            return {"success": True, "entry_id": entry_id}
            
        except Exception as e:
            logger.error(f"Error creating GL entry for late fee: {str(e)}")
            return {"success": False, "error": str(e)}
