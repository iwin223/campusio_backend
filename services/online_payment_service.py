"""High-level online payment service - orchestrates payment flow"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from sqlmodel import select

from models.fee import Fee, FeePayment, PaymentStatus, PaymentMethod
from models.student import Parent
from models.payment import OnlineTransaction, TransactionStatus, PaymentVerification, TransactionType
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
        parent_id: str,  # NOTE: This is User.id, not Parent.id. Will be looked up via Parent.user_id
        parent_email: str,
        school_id: str,
        amount_to_pay: Optional[float] = None,
        fee: Optional[Fee] = None  # Optional: pre-fetched fee object for validation
    ) -> Dict:
        """
        Initiate online payment for a fee
        
        SECURITY: This method validates the fee object to prevent unauthorized payments
        
        Args:
            parent_id: User.id of the parent user (not Parent.id)
                       Will be looked up via Parent.user_id relationship
        
        Returns:
        {
            "success": True,
            "transaction_id": "txn-xxx",
            "payment_url": "https://checkout.paystack.com/...",
            "reference": "PAY-xxx",
            "amount": 500.00
        }
        """
        
        try:
            # Get fee details if not provided
            if fee is None:
                fee_result = await session.execute(
                    select(Fee).where(Fee.id == fee_id)
                )
                fee = fee_result.scalar_one_or_none()
            
            if not fee:
                return {"success": False, "error": "Fee not found"}
            
            # SECURITY: Validate fee belongs to correct school (defensive check)
            if fee.school_id != school_id:
                logger.error(
                    f"School mismatch in payment: fee.school_id={fee.school_id}, "
                    f"expected={school_id}, parent_id={parent_id}"
                )
                return {"success": False, "error": "Unauthorized fee access"}
            
            # SECURITY: Validate parent exists (defensive check)
            # Note: parent_id is actually User.id, so we query by user_id
            parent_result = await session.execute(
                select(Parent).where(Parent.user_id == parent_id)
            )
            parent_record = parent_result.scalar_one_or_none()
            if not parent_record:
                logger.error(f"Parent record not found: {parent_id}")
                return {"success": False, "error": "Parent not found"}
            
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
            
            # Use the actual Parent.id (not User.id) for transaction record
            transaction = OnlineTransaction(
                school_id=school_id,
                fee_id=fee_id,
                student_id=fee.student_id,
                parent_id=parent_record.id,  # Use Parent record ID, not User ID
                amount=payment_amount,
                gateway="paystack",
                reference=transaction_id,
                transaction_type=TransactionType.FEE,  # Mark as fee payment
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
                    "transaction_id": str(transaction.id),  # Return UUID, not reference
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
            # Extract reference from nested structure (data is the wrapper)
            data = payload.get("data", {})
            reference = data.get("reference") if isinstance(data, dict) else payload.get("reference")
            amount = data.get("amount") if isinstance(data, dict) else payload.get("amount")
            status_val = data.get("status") if isinstance(data, dict) else payload.get("status")
            customer_email = data.get("customer", {}).get("email") if isinstance(data.get("customer"), dict) else None
            
            logger.info(f"Processing webhook - Reference: {reference}, Amount: {amount}, Status: {status_val}, Email: {customer_email}")
            
            if not reference:
                logger.warning("Webhook missing reference - attempting fallback by email and amount")
                
                # Fallback: match by email and amount if reference is missing
                if customer_email and amount:
                    amount_ghs = amount / 100  # Convert from kobo
                    trans_result = await session.execute(
                        select(OnlineTransaction).where(
                            (OnlineTransaction.payer_email == customer_email) &
                            (OnlineTransaction.amount == amount_ghs) &
                            (OnlineTransaction.status == TransactionStatus.PENDING)
                        ).order_by(OnlineTransaction.created_at.desc())
                    )
                    transaction = trans_result.scalars().first()
                    
                    if transaction:
                        reference = transaction.reference
                        logger.info(f"Matched transaction by email/amount fallback: {reference}")
                
                if not reference:
                    logger.error("Could not match transaction - no reference and email/amount fallback failed")
                    return {"success": False, "error": "Could not match payment to transaction"}
            
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
            
            # Check webhook status first (no API call needed)
            if status_val == "success":
                logger.info(f"Webhook indicates success, processing payment: {reference}")
                paystack_status = "success"
                amount_paid = amount / 100 if amount else 0  # Convert from kobo
                # Create paystack_data from webhook payload for consistency
                paystack_data = data if isinstance(data, dict) else {"reference": reference, "amount": amount, "status": status_val}
            else:
                logger.info(f"Webhook status not success, verifying with Paystack: {reference}")
                # Verify with Paystack for non-success webhooks or if status missing
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
                amount_paid = paystack_data.get("amount", 0) / 100  # Convert from kobo
            
            # Handle payment status
            if paystack_status == "success":
                
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
                
                # Distribute payment to fees (handles overpayment automatically)
                remaining_amount, fee_payments = await self._distribute_payment_to_fees(
                    session=session,
                    student_id=transaction.student_id,
                    school_id=transaction.school_id,
                    amount_to_distribute=amount_paid,
                    reference_number=reference,
                    received_by="online_system"
                )
                
                # Flush to ensure all FeePayments have IDs
                await session.flush()
                
                # Log distribution result
                if remaining_amount > 0:
                    logger.warning(
                        f"Payment distribution: GHS {remaining_amount:.2f} could not be "
                        f"distributed (student has no more outstanding fees)"
                    )
                
                # Update transaction with first fee payment ID (for reference)
                if fee_payments:
                    transaction.journal_entry_id = fee_payments[0].id
                
                session.add(transaction)
                await session.commit()
                
                # Get primary fee for notifications
                primary_fee_result = await session.execute(
                    select(Fee).where(Fee.id == transaction.fee_id)
                )
                primary_fee = primary_fee_result.scalar_one_or_none()
                
                # Get the first fee payment for notification data
                if fee_payments:
                    first_fee_payment = fee_payments[0]
                    
                    # Send notifications (async, don't wait)
                    try:
                        await self._send_payment_notifications(
                            session, transaction, first_fee_payment, primary_fee
                        )
                    except Exception as e:
                        logger.error(f"Error sending notifications: {str(e)}")
                
                logger.info(
                    f"Payment processed successfully: {reference}, "
                    f"Total amount: GHS {amount_paid}, "
                    f"Distributed to {len(fee_payments)} fee(s)"
                )
                
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
    
    async def _distribute_payment_to_fees(
        self,
        session: AsyncSession,
        student_id: str,
        school_id: str,
        amount_to_distribute: float,
        reference_number: str,
        received_by: str = "online_system"
    ) -> tuple[float, list]:
        """
        Distribute a payment to student's outstanding fees
        
        Applies payment to fees in order until exhausted:
        1. Cap payment to each fee's outstanding balance
        2. Pass excess to next fee
        3. Repeat until payment exhausted or all fees covered
        
        Returns:
        (remaining_amount_after_distribution, list_of_fee_payment_records_created)
        """
        
        fee_payments_created = []
        remaining_amount = amount_to_distribute
        
        # Get all outstanding fees for this student, ordered by creation date
        fees_result = await session.execute(
            select(Fee).where(
                and_(
                    Fee.student_id == student_id,
                    Fee.school_id == school_id,
                    Fee.status.in_(["pending", "partial", "overdue"])
                )
            ).order_by(Fee.created_at)
        )
        outstanding_fees = fees_result.scalars().all()
        
        if not outstanding_fees:
            logger.warning(f"No outstanding fees found for student {student_id}")
            return remaining_amount, fee_payments_created
        
        # Distribute payment across fees
        for fee in outstanding_fees:
            if remaining_amount <= 0:
                break
            
            # Calculate outstanding balance for this fee
            fee_balance = fee.amount_due - fee.amount_paid - fee.discount
            
            if fee_balance <= 0:
                # Fee already fully paid, skip to next
                continue
            
            # Determine how much to apply to this fee
            amount_for_this_fee = min(remaining_amount, fee_balance)
            
            # Create FeePayment record
            fee_payment = FeePayment(
                school_id=school_id,
                fee_id=fee.id,
                student_id=student_id,
                amount=amount_for_this_fee,
                payment_method=PaymentMethod.ONLINE_PAYMENT_PAYSTACK.value,
                reference_number=reference_number,
                receipt_number=f"RCP-{uuid.uuid4().hex[:8].upper()}",
                payment_date=datetime.utcnow().isoformat(),
                remarks=f"Online payment via Paystack (Ref: {reference_number})",
                received_by=received_by
            )
            session.add(fee_payment)
            fee_payments_created.append(fee_payment)
            
            # Update fee with payment
            fee.amount_paid += amount_for_this_fee
            
            # Update fee status
            fee_balance_after = fee.amount_due - fee.amount_paid - fee.discount
            if fee_balance_after <= 0:
                fee.status = PaymentStatus.PAID.value
            else:
                fee.status = PaymentStatus.PARTIAL.value
            
            fee.updated_at = datetime.utcnow()
            session.add(fee)
            
            # Reduce remaining amount
            remaining_amount -= amount_for_this_fee
            
            logger.info(
                f"Applied GHS {amount_for_this_fee} to fee {fee.id}, "
                f"balance now: {fee_balance_after:.2f}"
            )
        
        return remaining_amount, fee_payments_created
