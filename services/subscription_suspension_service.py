"""Subscription suspension service for overdue payments"""
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, SubscriptionStatus, BillingConfiguration
)

logger = logging.getLogger(__name__)


class SubscriptionSuspensionService:
    """Manages automatic suspension of overdue subscriptions"""
    
    async def check_and_suspend_overdue(
        self,
        session: AsyncSession,
        school_id: str
    ) -> Dict:
        """
        Check all overdue subscriptions and suspend if past suspension period
        
        Returns count of subscriptions suspended
        """
        try:
            # Get billing configuration
            config = await self._get_config(session, school_id)
            if not config:
                return {"success": False, "message": "No billing configuration"}
            
            # Get all active/pending subscriptions with unpaid balance
            result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.school_id == school_id,
                    PlatformSubscription.status.in_([
                        SubscriptionStatus.PENDING,
                        SubscriptionStatus.ACTIVE
                    ]),
                    PlatformSubscription.amount_paid < PlatformSubscription.total_amount_due
                )
            )
            subscriptions = result.scalars().all()
            
            count = 0
            suspended = []
            
            for sub in subscriptions:
                # Check if subscription is past suspension period
                days_overdue = (datetime.utcnow() - sub.due_date).days
                
                if days_overdue > config.default_suspension_days:
                    # Suspend subscription
                    sub.status = SubscriptionStatus.SUSPENDED
                    suspended.append({
                        "subscription_id": sub.id,
                        "school_id": sub.school_id,
                        "days_overdue": days_overdue,
                        "amount_due": sub.total_amount_due - sub.amount_paid,
                        "suspended_at": datetime.utcnow().isoformat()
                    })
                    count += 1
            
            if count > 0:
                await session.commit()
                logger.info(f"Suspended {count} subscriptions for school {school_id}")
            
            return {
                "success": True,
                "subscriptions_suspended": count,
                "suspended_subscriptions": suspended,
                "message": f"Suspended {count} overdue subscriptions"
            }
            
        except Exception as e:
            logger.error(f"Error checking suspension: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def suspend_subscription(
        self,
        session: AsyncSession,
        subscription_id: str
    ) -> Dict:
        """
        Manually suspend a subscription
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
            
            if subscription.status == SubscriptionStatus.SUSPENDED:
                return {"success": False, "error": "Already suspended"}
            
            # Suspend
            subscription.status = SubscriptionStatus.SUSPENDED
            await session.commit()
            
            logger.info(f"Suspended subscription {subscription_id}")
            
            return {
                "success": True,
                "message": "Subscription suspended",
                "subscription_id": subscription_id
            }
            
        except Exception as e:
            logger.error(f"Error suspending subscription: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def reactivate_subscription(
        self,
        session: AsyncSession,
        subscription_id: str,
        verify_payment: bool = True
    ) -> Dict:
        """
        Reactivate a suspended subscription (after payment made)
        
        Args:
            subscription_id: Subscription to reactivate
            verify_payment: If True, verify all balance is paid before reactivating
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
            
            if subscription.status != SubscriptionStatus.SUSPENDED:
                return {"success": False, "error": "Not in suspended status"}
            
            # Verify payment if requested
            if verify_payment:
                remaining = subscription.total_amount_due - subscription.amount_paid
                if remaining > 0:
                    return {
                        "success": False,
                        "error": f"Unable to reactivate: GHS {remaining:.2f} still outstanding"
                    }
            
            # Reactivate
            subscription.status = SubscriptionStatus.ACTIVE
            await session.commit()
            
            logger.info(f"Reactivated subscription {subscription_id}")
            
            return {
                "success": True,
                "message": "Subscription reactivated",
                "subscription_id": subscription_id
            }
            
        except Exception as e:
            logger.error(f"Error reactivating subscription: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_suspended_subscriptions(
        self,
        session: AsyncSession,
        school_id: str
    ) -> List[Dict]:
        """
        Get all suspended subscriptions for a school
        """
        try:
            result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.school_id == school_id,
                    PlatformSubscription.status == SubscriptionStatus.SUSPENDED
                )
            )
            subscriptions = result.scalars().all()
            
            return [
                {
                    "subscription_id": sub.id,
                    "academic_term_id": sub.academic_term_id,
                    "student_count": sub.student_count,
                    "total_due": sub.total_amount_due,
                    "amount_paid": sub.amount_paid,
                    "outstanding": sub.total_amount_due - sub.amount_paid,
                    "due_date": sub.due_date.isoformat(),
                    "suspended_since": (datetime.utcnow() - sub.due_date).days,
                    "late_fees": sub.late_fee_amount
                }
                for sub in subscriptions
            ]
            
        except Exception as e:
            logger.error(f"Error fetching suspended subscriptions: {str(e)}")
            return []
    
    async def _get_config(
        self,
        session: AsyncSession,
        school_id: str
    ):
        """Get billing configuration for school"""
        result = await session.execute(
            select(BillingConfiguration).where(
                BillingConfiguration.school_id == school_id
            )
        )
        return result.scalar_one_or_none()
