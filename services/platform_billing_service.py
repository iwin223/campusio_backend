"""Platform billing service - manages school subscription to platform"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import (
    PlatformSubscription, SubscriptionInvoice, SubscriptionStatus,
    PlatformSubscriptionResponse, SubscriptionInvoiceResponse,
    SubscriptionMetrics
)
from models.school import AcademicTerm
from models.student import Student, StudentStatus
from models.payment import OnlineTransaction, TransactionStatus, TransactionType
from models.finance import JournalEntry, JournalLineItem, ReferenceType, PostingStatus
from services.paystack_service import PaystackService
from services.sms_service import sms_service

logger = logging.getLogger(__name__)


class PlatformBillingService:
    """Manages school platform subscription billing"""
    
    def __init__(self, paystack_secret_key: str):
        self.paystack = PaystackService(paystack_secret_key)
        self.unit_price = 20.0  # GHS per student
    
    async def generate_term_subscription(
        self,
        session: AsyncSession,
        school_id: str,
        academic_term_id: str
    ) -> Dict:
        """
        Generate platform subscription for a term
        
        Called at the start of each academic term
        
        Returns:
        {
            "success": True,
            "subscription_id": "sub-xxx",
            "invoice_id": "inv-xxx",
            "total_due": 8400.00
        }
        """
        try:
            # Check if subscription already exists for this term
            existing = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.school_id == school_id,
                    PlatformSubscription.academic_term_id == academic_term_id
                )
            )
            if existing.scalar_one_or_none():
                return {
                    "success": False,
                    "error": "Subscription already exists for this term"
                }
            
            # Get academic term details
            term_result = await session.execute(
                select(AcademicTerm).where(AcademicTerm.id == academic_term_id)
            )
            academic_term = term_result.scalar_one_or_none()
            if not academic_term:
                return {"success": False, "error": "Academic term not found"}
            
            # Count active students for this school
            students_result = await session.execute(
                select(Student).where(
                    Student.school_id == school_id,
                    Student.status == StudentStatus.ACTIVE
                )
            )
            active_students = students_result.scalars().all()
            student_count = len(active_students)
            
            if student_count == 0:
                return {
                    "success": False,
                    "error": "No active students in school"
                }
            
            # Calculate subscription amount
            total_due = student_count * self.unit_price
            due_date = datetime.utcnow() + timedelta(days=30)
            
            # Create subscription record
            subscription = PlatformSubscription(
                school_id=school_id,
                academic_term_id=academic_term_id,
                student_count=student_count,
                unit_price=self.unit_price,
                total_amount_due=total_due,
                due_date=due_date,
                status=SubscriptionStatus.PENDING
            )
            
            session.add(subscription)
            await session.flush()
            
            # Create invoice
            invoice_number = await self._generate_invoice_number(session, school_id)
            invoice = SubscriptionInvoice(
                school_id=school_id,
                subscription_id=subscription.id,
                invoice_number=invoice_number,
                academic_year=academic_term.academic_year,
                term=academic_term.term.value,
                student_count=student_count,
                unit_price=self.unit_price,
                subtotal=total_due,
                total_amount=total_due,
                due_date=due_date,
                status="ISSUED"
            )
            
            session.add(invoice)
            subscription.invoice_id = invoice.id
            await session.flush()
            
            await session.commit()
            
            logger.info(
                f"Generated subscription for school {school_id}, "
                f"term {academic_term_id}, amount: GHS {total_due}"
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "invoice_id": invoice.id,
                "student_count": student_count,
                "total_due": total_due,
                "due_date": due_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating subscription: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def initiate_subscription_payment(
        self,
        session: AsyncSession,
        subscription_id: str,
        payer_email: str,
        amount_to_pay: Optional[float] = None
    ) -> Dict:
        """
        Initiate Paystack payment for subscription
        
        Returns:
        {
            "success": True,
            "payment_url": "https://checkout.paystack.com/...",
            "transaction_id": "txn-xxx",
            "reference": "PLAT-xxx"
        }
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
            
            if subscription.status == SubscriptionStatus.CANCELLED:
                return {"success": False, "error": "Subscription is cancelled"}
            
            # Calculate amount to pay
            amount_due = subscription.total_amount_due - subscription.amount_paid
            
            if amount_due <= 0:
                return {"success": False, "error": "No amount due"}
            
            if amount_to_pay is not None:
                if amount_to_pay <= 0:
                    return {
                        "success": False,
                        "error": "Payment amount must be greater than zero"
                    }
                if amount_to_pay > amount_due:
                    return {
                        "success": False,
                        "error": f"Payment exceeds balance of GHS {amount_due}"
                    }
                payment_amount = amount_to_pay
            else:
                payment_amount = amount_due
            
            # Create transaction record
            transaction_id = f"PLAT-{uuid.uuid4().hex[:12].upper()}"
            
            transaction = OnlineTransaction(
                school_id=subscription.school_id,
                fee_id=subscription_id,  # Using subscription ID as fee_id
                student_id="",  # Not applicable for platform billing
                parent_id="",  # Not applicable
                amount=payment_amount,
                gateway="paystack",
                reference=transaction_id,
                transaction_type=TransactionType.SUBSCRIPTION,  # Mark as subscription, not fee
                status=TransactionStatus.PENDING
            )
            
            session.add(transaction)
            await session.flush()
            
            # Call Paystack
            amount_kobo = int(payment_amount * 100)
            metadata = {
                "type": "platform_subscription",
                "subscription_id": subscription_id,
                "school_id": subscription.school_id,
                "invoice_id": subscription.invoice_id
            }
            
            paystack_result = await self.paystack.initialize_payment(
                amount_kobo=amount_kobo,
                email=payer_email,
                reference=transaction_id,
                metadata=metadata
            )
            
            logger.info(f"Paystack result: {paystack_result}")
            
            if not paystack_result.get("success"):
                await session.rollback()
                error_msg = paystack_result.get("error", "Paystack initialization failed")
                logger.error(f"Paystack init failed: {error_msg}, result: {paystack_result}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Store Paystack reference
            transaction.status = TransactionStatus.PROCESSING
            transaction.reference = paystack_result["reference"]
            transaction.access_code = paystack_result.get("access_code")
            transaction.payment_url = paystack_result["authorization_url"]
            
            subscription.online_transaction_id = transaction.id
            
            await session.commit()
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "payment_url": transaction.payment_url,
                "reference": transaction.reference,
                "amount": payment_amount
            }
            
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def verify_and_process_payment(
        self,
        session: AsyncSession,
        transaction_id: str,
        reference: str,
        amount_paid: float
    ) -> Dict:
        """
        Verify payment and process subscription
        
        Called from webhook after Paystack confirms payment
        """
        try:
            # Get transaction
            txn_result = await session.execute(
                select(OnlineTransaction).where(
                    OnlineTransaction.id == transaction_id
                )
            )
            transaction = txn_result.scalar_one_or_none()
            
            if not transaction:
                return {"success": False, "error": "Transaction not found"}
            
            # Get subscription
            sub_result = await session.execute(
                select(PlatformSubscription).where(
                    PlatformSubscription.id == transaction.fee_id
                )
            )
            subscription = sub_result.scalar_one_or_none()
            
            if not subscription:
                return {"success": False, "error": "Subscription not found"}
            
            # Verify amount
            if amount_paid < subscription.total_amount_due - subscription.amount_paid:
                # Partial payment - update status
                subscription.amount_paid += amount_paid
                transaction.amount_paid = amount_paid
                subscription.status = SubscriptionStatus.ACTIVE  # Allow partial
            else:
                # Full payment
                subscription.amount_paid = subscription.total_amount_due
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.paid_at = datetime.utcnow()
            
            transaction.status = TransactionStatus.SUCCESS
            transaction.completed_at = datetime.utcnow()
            
            # Create GL entry for revenue
            gl_result = await self._create_gl_entry(
                session,
                school_id=subscription.school_id,
                amount=amount_paid,
                reference=reference,
                description=f"Platform subscription payment - {subscription.student_count} students",
                subscription_id=subscription.id
            )
            
            if gl_result.get("success"):
                subscription.journal_entry_id = gl_result.get("entry_id")
            
            # Update invoice status
            if subscription.invoice_id:
                inv_result = await session.execute(
                    select(SubscriptionInvoice).where(
                        SubscriptionInvoice.id == subscription.invoice_id
                    )
                )
                invoice = inv_result.scalar_one_or_none()
                if invoice:
                    invoice.amount_paid = amount_paid
                    invoice.paid_at = datetime.utcnow()
                    invoice.status = "PAID" if amount_paid >= invoice.total_amount else "PARTIAL"
            
            await session.commit()
            
            logger.info(
                f"Processed payment for subscription {subscription.id}, "
                f"amount: GHS {amount_paid}"
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status.value,
                "amount_paid": amount_paid
            }
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_subscription(
        self,
        session: AsyncSession,
        subscription_id: str
    ) -> Optional[PlatformSubscriptionResponse]:
        """Get subscription details"""
        result = await session.execute(
            select(PlatformSubscription).where(
                PlatformSubscription.id == subscription_id
            )
        )
        sub = result.scalar_one_or_none()
        
        if not sub:
            return None
        
        return PlatformSubscriptionResponse(
            id=sub.id,
            school_id=sub.school_id,
            academic_term_id=sub.academic_term_id,
            student_count=sub.student_count,
            unit_price=sub.unit_price,
            total_amount_due=sub.total_amount_due,
            amount_paid=sub.amount_paid,
            status=sub.status,
            billing_date=sub.billing_date,
            due_date=sub.due_date,
            paid_at=sub.paid_at,
            created_at=sub.created_at
        )
    
    async def get_school_current_subscription(
        self,
        session: AsyncSession,
        school_id: str
    ) -> Optional[PlatformSubscriptionResponse]:
        """Get current term subscription for school"""
        result = await session.execute(
            select(PlatformSubscription)
            .where(PlatformSubscription.school_id == school_id)
            .order_by(PlatformSubscription.created_at.desc())
        )
        sub = result.scalars().first()
        
        if not sub:
            return None
        
        return PlatformSubscriptionResponse(
            id=sub.id,
            school_id=sub.school_id,
            academic_term_id=sub.academic_term_id,
            student_count=sub.student_count,
            unit_price=sub.unit_price,
            total_amount_due=sub.total_amount_due,
            amount_paid=sub.amount_paid,
            status=sub.status,
            billing_date=sub.billing_date,
            due_date=sub.due_date,
            paid_at=sub.paid_at,
            created_at=sub.created_at
        )
    
    async def get_school_subscriptions(
        self,
        session: AsyncSession,
        school_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[PlatformSubscriptionResponse]:
        """Get all subscriptions for school"""
        result = await session.execute(
            select(PlatformSubscription)
            .where(PlatformSubscription.school_id == school_id)
            .order_by(PlatformSubscription.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        subs = result.scalars().all()
        
        return [
            PlatformSubscriptionResponse(
                id=sub.id,
                school_id=sub.school_id,
                academic_term_id=sub.academic_term_id,
                student_count=sub.student_count,
                unit_price=sub.unit_price,
                total_amount_due=sub.total_amount_due,
                amount_paid=sub.amount_paid,
                status=sub.status,
                billing_date=sub.billing_date,
                due_date=sub.due_date,
                paid_at=sub.paid_at,
                created_at=sub.created_at
            )
            for sub in subs
        ]
    
    async def get_school_invoices(
        self,
        session: AsyncSession,
        school_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[SubscriptionInvoiceResponse]:
        """Get all invoices for school"""
        result = await session.execute(
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.school_id == school_id)
            .order_by(SubscriptionInvoice.issued_at.desc())
            .limit(limit)
            .offset(offset)
        )
        invoices = result.scalars().all()
        
        return [
            SubscriptionInvoiceResponse(
                id=inv.id,
                school_id=inv.school_id,
                invoice_number=inv.invoice_number,
                academic_year=inv.academic_year,
                term=inv.term,
                student_count=inv.student_count,
                total_amount=inv.total_amount,
                amount_paid=inv.amount_paid,
                status=inv.status,
                issued_at=inv.issued_at,
                due_date=inv.due_date,
                paid_at=inv.paid_at
            )
            for inv in invoices
        ]
    
    async def get_subscription_metrics(
        self,
        session: AsyncSession,
        school_id: str
    ) -> Optional[SubscriptionMetrics]:
        """Get subscription metrics for dashboard"""
        # Get current subscription
        current = await self.get_school_current_subscription(session, school_id)
        
        if not current:
            return None
        
        days_until_due = (current.due_date - datetime.utcnow()).days
        is_overdue = days_until_due < 0
        remaining_balance = current.total_amount_due - current.amount_paid
        
        return SubscriptionMetrics(
            school_id=school_id,
            current_term_status=current.status,
            total_due=current.total_amount_due,
            total_paid=current.amount_paid,
            remaining_balance=remaining_balance,
            student_count=current.student_count,
            unit_price=current.unit_price,
            days_until_due=max(days_until_due, 0),
            is_overdue=is_overdue
        )
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    async def _generate_invoice_number(
        self,
        session: AsyncSession,
        school_id: str
    ) -> str:
        """Generate unique invoice number"""
        # Get current year
        year = datetime.utcnow().year
        
        # Count invoices for this school this year
        result = await session.execute(
            select(SubscriptionInvoice).where(
                SubscriptionInvoice.school_id == school_id,
                SubscriptionInvoice.invoice_number.like(f"{year}%")
            )
        )
        count = len(result.scalars().all())
        
        # Generate invoice number: PLAT-2026-0001
        return f"PLAT-{year}-{str(count + 1).zfill(4)}"
    
    async def _create_gl_entry(
        self,
        session: AsyncSession,
        school_id: str,
        amount: float,
        reference: str,
        description: str,
        subscription_id: str
    ) -> Dict:
        """Create GL journal entry for platform subscription revenue"""
        try:
            # Create journal entry
            entry_id = f"JE-{uuid.uuid4().hex[:12].upper()}"
            
            entry = JournalEntry(
                id=entry_id,
                school_id=school_id,
                entry_date=datetime.utcnow(),
                reference_type=ReferenceType.PLATFORM_SUBSCRIPTION,
                reference_id=subscription_id,
                description=description,
                total_debit=amount,
                total_credit=amount,
                posting_status=PostingStatus.POSTED,
                posted_date=datetime.utcnow(),
                created_by="SYSTEM"
            )
            
            # Line items
            # Debit: Cash/Bank (1100)
            debit_line = JournalLineItem(
                id=f"JLI-{uuid.uuid4().hex[:12].upper()}",
                journal_entry_id=entry_id,
                school_id=school_id,
                gl_account_id="1100",  # Will need to fetch actual account ID
                debit=amount,
                credit=0
            )
            
            # Credit: Platform Revenue (4250)
            credit_line = JournalLineItem(
                id=f"JLI-{uuid.uuid4().hex[:12].upper()}",
                journal_entry_id=entry_id,
                school_id=school_id,
                gl_account_id="4250",  # Will need to fetch actual account ID
                debit=0,
                credit=amount
            )
            
            session.add(entry)
            session.add(debit_line)
            session.add(credit_line)
            
            return {"success": True, "entry_id": entry_id}
            
        except Exception as e:
            logger.error(f"Error creating GL entry: {str(e)}")
            return {"success": False, "error": str(e)}
