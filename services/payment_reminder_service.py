"""Payment reminder service for platform billing (Phase 2)"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, PaymentReminder, BillingConfiguration, SubscriptionStatus
)

logger = logging.getLogger(__name__)


class PaymentReminderService:
    """Manages payment reminders (SMS/Email)"""
    
    async def send_pending_reminders(
        self,
        session: AsyncSession,
        school_id: Optional[str] = None
    ) -> Dict:
        """
        Send reminders for subscriptions upcoming due or overdue
        
        Args:
            school_id: Optional filter for specific school
        
        Returns count of reminders sent
        """
        try:
            # Get billing configuration
            query = select(BillingConfiguration)
            if school_id:
                query = query.where(
                    BillingConfiguration.school_id == school_id
                )
            
            config_result = await session.execute(query)
            configs = config_result.scalars().all()
            
            total_sent = 0
            
            for config in configs:
                if not config.enable_reminders:
                    continue
                
                # Get subscriptions approaching due date
                sub_result = await session.execute(
                    select(PlatformSubscription).where(
                        PlatformSubscription.school_id == config.school_id,
                        PlatformSubscription.status.in_([
                            SubscriptionStatus.PENDING,
                            SubscriptionStatus.ACTIVE
                        ]),
                        PlatformSubscription.amount_paid < 
                            PlatformSubscription.total_amount_due
                    )
                )
                subscriptions = sub_result.scalars().all()
                
                for sub in subscriptions:
                    # Check if reminder should be sent
                    days_until_due = (sub.due_date - datetime.utcnow()).days
                    
                    # Send reminder if within the reminder window and no reminder sent yet
                    if 0 <= days_until_due <= config.reminder_days_before_due:
                        sent_count = await self._send_reminders(
                            session,
                            sub,
                            config
                        )
                        total_sent += sent_count
            
            await session.commit()
            
            return {
                "success": True,
                "reminders_sent": total_sent,
                "message": f"Sent {total_sent} payment reminders"
            }
            
        except Exception as e:
            logger.error(f"Error sending reminders: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def schedule_reminder(
        self,
        session: AsyncSession,
        subscription_id: str,
        reminder_type: str,  # "sms", "email", "both"
        days_before_due: int,
        recipient: str,
        custom_message: Optional[str] = None
    ) -> Dict:
        """
        Create a scheduled reminder for a subscription
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
            
            # Generate message
            message = custom_message or self._generate_reminder_message(
                subscription,
                days_before_due
            )
            
            reminder = PaymentReminder(
                subscription_id=subscription_id,
                school_id=subscription.school_id,
                reminder_type=reminder_type,
                days_before_due=days_before_due,
                message=message,
                recipient=recipient,
                sent=False,
                status="pending"
            )
            
            session.add(reminder)
            await session.commit()
            
            return {
                "success": True,
                "reminder_id": reminder.id,
                "scheduled_date": (subscription.due_date - 
                    timedelta(days=days_before_due)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scheduling reminder: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def send_reminder_now(
        self,
        session: AsyncSession,
        reminder_id: str
    ) -> Dict:
        """
        Send a reminder immediately (for admin override)
        """
        try:
            result = await session.execute(
                select(PaymentReminder).where(
                    PaymentReminder.id == reminder_id
                )
            )
            reminder = result.scalar_one_or_none()
            
            if not reminder:
                return {"success": False, "error": "Reminder not found"}
            
            # Send via appropriate channel
            send_result = await self._send_reminder(reminder)
            
            if send_result.get("success"):
                reminder.sent = True
                reminder.sent_at = datetime.utcnow()
                reminder.status = "sent"
                await session.commit()
            else:
                reminder.status = "failed"
                reminder.error_message = send_result.get("error")
                await session.commit()
            
            return send_result
            
        except Exception as e:
            logger.error(f"Error sending reminder: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_reminder_history(
        self,
        session: AsyncSession,
        subscription_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> Dict:
        """
        Get reminder sending history for a subscription
        """
        try:
            count_result = await session.execute(
                select(PaymentReminder).where(
                    PaymentReminder.subscription_id == subscription_id
                )
            )
            total = len(count_result.scalars().all())
            
            result = await session.execute(
                select(PaymentReminder).where(
                    PaymentReminder.subscription_id == subscription_id
                )
                .order_by(PaymentReminder.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            reminders = result.scalars().all()
            
            return {
                "count": total,
                "limit": limit,
                "offset": offset,
                "data": [
                    {
                        "id": r.id,
                        "type": r.reminder_type,
                        "recipient": r.recipient,
                        "status": r.status,
                        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                        "days_before_due": r.days_before_due,
                        "error": r.error_message
                    }
                    for r in reminders
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting reminder history: {str(e)}")
            return {"count": 0, "data": [], "error": str(e)}
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    async def _send_reminders(
        self,
        session: AsyncSession,
        subscription: PlatformSubscription,
        config: BillingConfiguration
    ) -> int:
        """Send reminders for a subscription"""
        sent_count = 0
        days_until_due = (subscription.due_date - datetime.utcnow()).days
        
        # Check if reminder already sent
        existing = await session.execute(
            select(PaymentReminder).where(
                PaymentReminder.subscription_id == subscription.id,
                PaymentReminder.days_before_due == config.reminder_days_before_due,
                PaymentReminder.sent == True
            )
        )
        
        if existing.scalar_one_or_none():
            return 0  # Already sent
        
        # Generate message
        message = self._generate_reminder_message(subscription, days_until_due)
        
        # Send SMS if enabled
        if "sms" in config.enable_reminders or config.enable_reminders == True:
            # Get school contact (in real implementation, fetch from school DB)
            # For now, placeholder
            sms_recipient = "+233XXXXXXXXXX"  # Placeholder
            
            sms_reminder = PaymentReminder(
                subscription_id=subscription.id,
                school_id=subscription.school_id,
                reminder_type="sms",
                days_before_due=days_until_due,
                message=message,
                recipient=sms_recipient,
                sent=True,
                sent_at=datetime.utcnow(),
                status="sent"
            )
            
            session.add(sms_reminder)
            sent_count += 1
            
            # In production, call SMS service here
            logger.info(
                f"SMS reminder sent to {sms_recipient} for "
                f"subscription {subscription.id}"
            )
        
        return sent_count
    
    async def _send_reminder(self, reminder: PaymentReminder) -> Dict:
        """
        Send individual reminder (SMS or Email)
        
        In production, connect to SMS/Email services
        """
        try:
            if reminder.reminder_type == "sms":
                # Call SMS service
                logger.info(
                    f"Sending SMS to {reminder.recipient}: {reminder.message}"
                )
                # In production: await sms_service.send(...)
                return {"success": True, "channel": "sms"}
            
            elif reminder.reminder_type == "email":
                # Call Email service
                logger.info(
                    f"Sending Email to {reminder.recipient}: {reminder.message}"
                )
                # In production: await email_service.send(...)
                return {"success": True, "channel": "email"}
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown reminder type: {reminder.reminder_type}"
                }
        
        except Exception as e:
            logger.error(f"Error sending reminder: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _generate_reminder_message(
        self,
        subscription: PlatformSubscription,
        days_until_due: int
    ) -> str:
        """Generate reminder message for subscription"""
        if days_until_due < 0:
            return (
                f"⚠️ Your School ERP platform bill is {abs(days_until_due)} days overdue! "
                f"Outstanding: GHS {subscription.total_amount_due - subscription.amount_paid:.2f}. "
                f"Please pay immediately to avoid suspension."
            )
        elif days_until_due == 0:
            return (
                f"⏰ Your School ERP platform bill is DUE TODAY! "
                f"Amount: GHS {subscription.total_amount_due - subscription.amount_paid:.2f}. "
                f"Pay now to keep platform access active."
            )
        else:
            return (
                f"📢 Reminder: Your School ERP platform bill is due in {days_until_due} days. "
                f"Amount: GHS {subscription.total_amount_due - subscription.amount_paid:.2f}. "
                f"Pay early to avoid late fees."
            )
