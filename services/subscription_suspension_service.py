"""Subscription suspension service for overdue payments.

This is the ledger-side status flag (PlatformSubscription.status).
Enforcement — actually blocking a school's users from every module — lives
in auth.py::get_current_user, which checks School.access_suspended, not
this status. The two used to be entirely disconnected: this service could
mark a subscription SUSPENDED and nothing would happen. Every method here
now keeps School.access_suspended in sync, so suspending/reactivating a
subscription actually locks/unlocks the school.

Nothing calls check_and_suspend_overdue() on a schedule — there is no task
scheduler anywhere in this codebase. It only runs when a super admin (or a
future cron job) hits POST /billing/subscriptions/suspend/check-overdue.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, SubscriptionStatus, BillingConfiguration
)
from models.school import School
from services.platform_billing_service import subscription_outstanding

logger = logging.getLogger(__name__)


class SubscriptionSuspensionService:
    """Manages automatic suspension of overdue subscriptions"""

    async def _set_school_access(
        self, session: AsyncSession, school_id: str, suspended: bool, reason: Optional[str] = None
    ) -> None:
        """Keep School.access_suspended in sync with subscription status —
        this is the field auth.py actually enforces."""
        result = await session.execute(select(School).where(School.id == school_id))
        school = result.scalar_one_or_none()
        if not school:
            return
        school.access_suspended = suspended
        school.access_suspended_reason = reason if suspended else None
        school.access_suspended_at = datetime.utcnow() if suspended else None
        school.updated_at = datetime.utcnow()

    async def check_and_suspend_overdue(
        self,
        session: AsyncSession,
        school_id: Optional[str]
    ) -> Dict:
        """
        Check overdue subscriptions and suspend (both the subscription
        status AND the school's module access) if past the suspension
        period. school_id=None checks every school.
        """
        try:
            query = select(PlatformSubscription).where(
                PlatformSubscription.status.in_([
                    SubscriptionStatus.PENDING,
                    SubscriptionStatus.ACTIVE
                ])
            )
            if school_id:
                query = query.where(PlatformSubscription.school_id == school_id)
            result = await session.execute(query)
            subscriptions = result.scalars().all()

            count = 0
            suspended = []

            for sub in subscriptions:
                # subscription_outstanding() accounts for late fees and
                # discounts — total_amount_due - amount_paid alone (the old
                # check) flags a fully-paid-after-discount subscription as
                # still owing money, since amount_paid never reaches the
                # pre-discount total_amount_due.
                outstanding = subscription_outstanding(sub)
                if outstanding <= 0:
                    continue

                config = await self._get_config(session, sub.school_id)
                suspension_days = config.default_suspension_days if config else 14
                days_overdue = (datetime.utcnow() - sub.due_date).days

                if days_overdue > suspension_days:
                    sub.status = SubscriptionStatus.SUSPENDED
                    sub.updated_at = datetime.utcnow()
                    await self._set_school_access(
                        session, sub.school_id, suspended=True,
                        reason=f"Platform subscription {days_overdue} days overdue, GHS {outstanding:.2f} outstanding"
                    )
                    suspended.append({
                        "subscription_id": sub.id,
                        "school_id": sub.school_id,
                        "days_overdue": days_overdue,
                        "amount_due": outstanding,
                        "suspended_at": datetime.utcnow().isoformat()
                    })
                    count += 1

            if count > 0:
                await session.commit()
                logger.info(f"Suspended {count} subscriptions" + (f" for school {school_id}" if school_id else " platform-wide"))

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
        subscription_id: str,
        reason: Optional[str] = None,
    ) -> Dict:
        """Manually suspend a subscription (and the school's module access)."""
        try:
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

            subscription.status = SubscriptionStatus.SUSPENDED
            subscription.updated_at = datetime.utcnow()
            await self._set_school_access(
                session, subscription.school_id, suspended=True,
                reason=reason or "Platform subscription manually suspended"
            )
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
        Reactivate a suspended subscription (and restore the school's
        module access).

        Args:
            subscription_id: Subscription to reactivate
            verify_payment: If True, verify the outstanding balance (base +
                late fees - discounts - paid) is fully settled first
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

            if subscription.status != SubscriptionStatus.SUSPENDED:
                return {"success": False, "error": "Not in suspended status"}

            if verify_payment:
                remaining = subscription_outstanding(subscription)
                if remaining > 0:
                    return {
                        "success": False,
                        "error": f"Unable to reactivate: GHS {remaining:.2f} still outstanding"
                    }

            subscription.status = SubscriptionStatus.ACTIVE
            subscription.updated_at = datetime.utcnow()
            await self._set_school_access(session, subscription.school_id, suspended=False)
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
        school_id: Optional[str]
    ) -> List[Dict]:
        """Get all suspended subscriptions (all schools if school_id is None)."""
        try:
            query = select(PlatformSubscription).where(
                PlatformSubscription.status == SubscriptionStatus.SUSPENDED
            )
            if school_id:
                query = query.where(PlatformSubscription.school_id == school_id)
            result = await session.execute(query)
            subscriptions = result.scalars().all()

            return [
                {
                    "subscription_id": sub.id,
                    "school_id": sub.school_id,
                    "academic_term_id": sub.academic_term_id,
                    "student_count": sub.student_count,
                    "total_due": sub.total_amount_due,
                    "amount_paid": sub.amount_paid,
                    "outstanding": subscription_outstanding(sub),
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
