"""High-level online payment service - orchestrates payment flow"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.fee import Fee, FeePayment, PaymentStatus
from models.student import Parent
from models.payment import OnlineTransaction, TransactionStatus, PaymentVerification
from models.finance import JournalEntry, JournalLineItem, ReferenceType
from models.finance.chart_of_accounts import GLAccount
from services.paystack_service import PaystackService
from services.sms_service import sms_service  # Existing SMS service

logger = logging.getLogger(__name__)


class OnlinePaymentService:
    """Orchestrates online payment flow"""
    
    def __init__(self, paystack_secret_key: str):
        self.paystack = PaystackService(paystack_secret_key)
    
    async def initiate_payment(
        self,
        session: AsyncSession,
        fee_id: str,
        parent_id: str,
        parent_email: str,
        school_id: str,
        amount_to_pay: Optional[float] = None
    ) -> Dict:
        """
        Initiate online payment for a fee
        
        Returns:
        {
            "success": True,
            "transaction_id": "txn-xxx",
            "payment_url": "https://checkout.paystack.com/...",
            "reference": "PAY-xxx"
        }
        """
        
        try:
            # Get fee details
            fee_result = await session.execute(
                select(Fee).where(Fee.id == fee_id, Fee.school_id == school_id)
            )
            fee = fee_result.scalar_one_or_none()
            
            if not fee:
                return {"success": False, "error": "Fee not found"}
            
            # Calculate amount due (total - already paid)
            amount_due = fee.amount_due - fee.amount_paid
            if amount_due <= 0:
                return {"success": False, "error": "No amount due"}
            
            # Use custom amount if provided, otherwise use full balance
            if amount_to_pay is not None:
                if amount_to_pay <= 0:
                    return {"success": False, "error": "Payment amount must be greater than zero"}
                if amount_to_pay > amount_due:
                    return {"success": False, "error": f"Payment amount cannot exceed outstanding balance of GHS {amount_due}"}
                payment_amount = amount_to_pay
            else:
                payment_amount = amount_due
            
            # Create transaction record
            transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
            
            transaction = OnlineTransaction(
                school_id=school_id,
                fee_id=fee_id,
                student_id=fee.student_id,
                parent_id=parent_id,
                amount=payment_amount,
                gateway="paystack",
                reference=transaction_id,
                status=TransactionStatus.PENDING
            )
            
            session.add(transaction)
            await session.flush()  # Get the ID
            
            # Call Paystack API
            amount_kobo = int(payment_amount * 100)  # Convert GHS to kobo
            metadata = {
                "fee_id": fee_id,
                "student_id": fee.student_id,
                "transaction_id": transaction_id,
                "is_partial": amount_to_pay is not None
            }
            
            paystack_result = await self.paystack.initialize_payment(
                amount_kobo=amount_kobo,
                email=parent_email,
                reference=transaction_id,
                metadata=metadata
            )
            
            if paystack_result["success"]:
                # Update transaction with Paystack details
                transaction.payment_url = paystack_result["authorization_url"]
                transaction.access_code = paystack_result["access_code"]
                transaction.reference = paystack_result["reference"]
                transaction.status = TransactionStatus.PROCESSING
                
                session.add(transaction)
                await session.commit()
                
                logger.info(f"Payment initiated: {transaction_id}")
                
                return {
                    "success": True,
                    "transaction_id": transaction_id,
                    "payment_url": paystack_result["authorization_url"],
                    "reference": paystack_result["reference"],
                    "amount": payment_amount
                }
            else:
                transaction.status = TransactionStatus.FAILED
                transaction.failed_reason = paystack_result.get("error", "Payment initialization failed")
                session.add(transaction)
                await session.commit()
                
                return {
                    "success": False,
                    "error": paystack_result.get("error", "Payment initialization failed")
                }
        
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            return {
                "success": False,
                "error": f"Error: {str(e)}"
            }
    
    async def process_webhook(
        self,
        session: AsyncSession,
        payload: Dict
    ) -> Dict:
        """
        Process webhook from Paystack
        
        Paystack sends this when payment status changes
        """
        
        try:
            reference = payload.get("reference")
            
            if not reference:
                logger.warning("Webhook missing reference")
                return {"success": False, "error": "Missing reference"}
            
            # Find transaction
            trans_result = await session.execute(
                select(OnlineTransaction).where(OnlineTransaction.reference == reference)
            )
            transaction = trans_result.scalar_one_or_none()
            
            if not transaction:
                logger.warning(f"Transaction not found: {reference}")
                return {"success": False, "error": "Transaction not found"}
            
            # Check if already processed (idempotency)
            if transaction.status == TransactionStatus.SUCCESS:
                logger.info(f"Transaction already processed: {reference}")
                return {"success": True, "processed": False}
            
            # Verify with Paystack
            verify_result = await self.paystack.verify_payment(reference)
            
            if not verify_result["success"]:
                logger.error(f"Verification failed: {reference}")
                transaction.status = TransactionStatus.FAILED
                transaction.failed_reason = "Verification failed"
                session.add(transaction)
                await session.commit()
                return {"success": False, "error": "Verification failed"}
            
            paystack_data = verify_result["data"]
            paystack_status = paystack_data.get("status")
            
            # Handle payment status
            if paystack_status == "success":
                amount_paid = paystack_data.get("amount", 0) / 100  # Convert from kobo
                
                # Record verification
                verification = PaymentVerification(
                    transaction_id=transaction.id,
                    gateway="paystack",
                    reference=reference,
                    expected_amount=transaction.amount,
                    actual_amount=amount_paid,
                    verified=True,
                    match_status="AMOUNT_MATCH" if abs(amount_paid - transaction.amount) < 0.01 else "AMOUNT_MISMATCH"
                )
                session.add(verification)
                
                # Update transaction
                transaction.status = TransactionStatus.SUCCESS
                transaction.payment_status = "success"
                transaction.amount_paid = amount_paid
                transaction.completed_at = datetime.utcnow()
                transaction.verified_at = datetime.utcnow()
                transaction.gateway_response = str(paystack_data)
                session.add(transaction)
                
                # Create FeePayment record (this triggers GL posting automatically)
                fee_payment = FeePayment(
                    school_id=transaction.school_id,
                    fee_id=transaction.fee_id,
                    student_id=transaction.student_id,
                    amount=amount_paid,
                    payment_method="online_payment_paystack",
                    reference_number=reference,
                    receipt_number=f"RCP-{uuid.uuid4().hex[:8].upper()}",
                    payment_date=datetime.utcnow().isoformat(),
                    remarks=f"Online payment via Paystack",
                    received_by="online_system"
                )
                session.add(fee_payment)
                await session.flush()
                
                # Update transaction with journal_entry_id (will be created by GL posting)
                transaction.journal_entry_id = fee_payment.id
                session.add(transaction)
                
                # Update Fee status
                fee_result = await session.execute(
                    select(Fee).where(Fee.id == transaction.fee_id)
                )
                fee = fee_result.scalar_one()
                fee.amount_paid += amount_paid
                
                if fee.amount_paid >= fee.amount_due:
                    fee.status = PaymentStatus.PAID
                else:
                    fee.status = PaymentStatus.PARTIAL
                
                fee.updated_at = datetime.utcnow()
                session.add(fee)
                await session.commit()
                
                logger.info(f"Payment recorded: {reference}, Amount: {amount_paid}")
                
                # Send notifications (async, don't wait)
                try:
                    await self._send_payment_notifications(
                        session, transaction, fee_payment, fee
                    )
                except Exception as e:
                    logger.error(f"Error sending notifications: {str(e)}")
                
                return {"success": True, "processed": True}
            
            else:
                # Payment failed
                transaction.status = TransactionStatus.FAILED
                transaction.payment_status = paystack_status
                transaction.failed_reason = paystack_data.get("gateway_response", "Payment declined")
                transaction.gateway_response = str(paystack_data)
                session.add(transaction)
                await session.commit()
                
                logger.warning(f"Payment failed: {reference}")
                return {"success": True, "processed": True}
        
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def _send_payment_notifications(
        self,
        session: AsyncSession,
        transaction: OnlineTransaction,
        fee_payment: FeePayment,
        fee: Fee
    ):
        """Send SMS/Email notifications after successful payment"""
        
        try:
            # Get parent info
            parent_result = await session.execute(
                select(Parent).where(Parent.id == transaction.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            
            if not parent:
                logger.warning(f"Parent not found: {transaction.parent_id}")
                return
            
            # Calculate balance
            balance = fee.amount_due - fee.amount_paid
            
            # SMS notification
            message = (
                f"Fee payment of GHS {transaction.amount_paid:.2f} received. "
                f"Remaining balance: GHS {balance:.2f}. "
                f"Receipt: {fee_payment.receipt_number}"
            )
            
            if parent.phone_number:
                try:
                    await sms_service.send_sms(parent.phone_number, message)
                    logger.info(f"SMS sent to {parent.phone_number}")
                except Exception as e:
                    logger.error(f"SMS send error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error sending notifications: {str(e)}")
