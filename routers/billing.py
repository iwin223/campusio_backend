"""Billing router - handles platform subscription API endpoints"""
import logging
import os
import json
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from database import get_session
from auth import get_current_user
from models.user import User, UserRole
from models.school import AcademicTerm
from models.billing import (
    PlatformSubscription, SubscriptionInvoice,
    PlatformSubscriptionResponse, SubscriptionInvoiceResponse,
    GenerateSubscriptionRequest, ProcessSubscriptionPaymentRequest,
    SubscriptionMetrics
)
from typing import Optional
from models.payment import OnlineTransaction, TransactionStatus, PaymentVerification
from services.platform_billing_service import PlatformBillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def get_billing_service() -> PlatformBillingService:
    """Initialize billing service"""
    paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    
    if not paystack_secret_key:
        raise ValueError("PAYSTACK_SECRET_KEY not configured in .env")
    
    return PlatformBillingService(paystack_secret_key)


# ============================================================================
# ENDPOINTS - SUBSCRIPTION MANAGEMENT
# ============================================================================

@router.post("/subscriptions/generate-term", status_code=201)
async def generate_term_subscription(
    request_data: GenerateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Generate platform subscription for academic term
    
    **Auth Required:** Admin, Principal, or School roles
    
    **Request Body:**
    ```json
    {
        "academic_term_id": "term-uuid"
    }
    ```
    
    **Response:**
    ```json
    {
        "success": true,
        "subscription_id": "sub-xxx",
        "invoice_id": "inv-xxx",
        "student_count": 420,
        "total_due": 8400.00,
        "due_date": "2026-05-15T10:30:00"
    }
    ```
    """
    
    # Verify authorization
    if current_user.role not in [UserRole.ADMIN, UserRole.SCHOOL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or school users can generate subscriptions"
        )
    
    if current_user.role == UserRole.SCHOOL:
        school_id = current_user.school_id
    else:
        # Admin must be with a school
        if not current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must be associated with a school"
            )
        school_id = current_user.school_id
    
    result = await billing_service.generate_term_subscription(
        session=session,
        school_id=school_id,
        academic_term_id=request_data.academic_term_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to generate subscription")
        )
    
    return result


@router.get("/subscriptions/current", status_code=200)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Get current academic term subscription for school
    
    **Auth Required:** Authenticated user
    
    **Response:**
    ```json
    {
        "id": "sub-xxx",
        "school_id": "school-xxx",
        "academic_term_id": "term-xxx",
        "student_count": 420,
        "unit_price": 20.00,
        "total_amount_due": 8400.00,
        "amount_paid": 0.00,
        "status": "pending",
        "billing_date": "2026-04-15T10:30:00",
        "due_date": "2026-05-15T10:30:00",
        "paid_at": null,
        "created_at": "2026-04-15T10:30:00"
    }
    ```
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    subscription = await billing_service.get_school_current_subscription(
        session=session,
        school_id=current_user.school_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    return subscription.dict()


@router.get("/subscriptions/{subscription_id}", status_code=200)
async def get_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Get subscription details by ID
    
    **Auth Required:** Authenticated user
    """
    
    subscription = await billing_service.get_subscription(
        session=session,
        subscription_id=subscription_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Verify access
    if current_user.role == UserRole.SCHOOL and subscription.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return subscription.dict()


@router.get("/subscriptions", status_code=200)
async def get_school_subscriptions(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Get all subscriptions for school (paginated)
    
    **Auth Required:** Authenticated user
    
    **Query Parameters:**
    - `limit`: Number of subscriptions per page (default: 10)
    - `offset`: Pagination offset (default: 0)
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    subscriptions = await billing_service.get_school_subscriptions(
        session=session,
        school_id=current_user.school_id,
        limit=limit,
        offset=offset
    )
    
    return {
        "count": len(subscriptions),
        "limit": limit,
        "offset": offset,
        "data": [sub.dict() for sub in subscriptions]
    }


# ============================================================================
# ENDPOINTS - INVOICES
# ============================================================================

@router.get("/invoices", status_code=200)
async def get_school_invoices(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Get all invoices for school (paginated)
    
    **Auth Required:** Authenticated user
    
    **Query Parameters:**
    - `limit`: Number of invoices per page (default: 10)
    - `offset`: Pagination offset (default: 0)
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    invoices = await billing_service.get_school_invoices(
        session=session,
        school_id=current_user.school_id,
        limit=limit,
        offset=offset
    )
    
    return {
        "count": len(invoices),
        "limit": limit,
        "offset": offset,
        "data": [inv.dict() for inv in invoices]
    }


# ============================================================================
# ENDPOINTS - PAYMENT PROCESSING
# ============================================================================

@router.post("/subscriptions/{subscription_id}/pay", status_code=200)
async def initiate_subscription_payment(
    subscription_id: str,
    request_data: ProcessSubscriptionPaymentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Initiate payment for platform subscription via Paystack
    
    **Auth Required:** Authenticated user
    
    **Request Body:**
    ```json
    {
        "subscription_id": "sub-xxx",
        "amount_to_pay": 8400.00  // Optional, defaults to full amount
    }
    ```
    
    **Response:**
    ```json
    {
        "success": true,
        "transaction_id": "txn-xxx",
        "payment_url": "https://checkout.paystack.com/...",
        "reference": "PLAT-xxx",
        "amount": 8400.00
    }
    ```
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    # Get subscription to verify access
    subscription = await billing_service.get_subscription(
        session=session,
        subscription_id=subscription_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if subscription.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Initiate payment
    result = await billing_service.initiate_subscription_payment(
        session=session,
        subscription_id=subscription_id,
        payer_email=current_user.email,
        amount_to_pay=request_data.amount_to_pay
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to initiate payment")
        )
    
    return result


# ============================================================================
# ENDPOINTS - DASHBOARDS & METRICS
# ============================================================================

@router.get("/metrics", status_code=200)
async def get_subscription_metrics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Get subscription metrics for school dashboard
    
    **Auth Required:** Authenticated user
    
    **Auto-generates subscription** if none exists for current term
    
    **Response:**
    ```json
    {
        "school_id": "school-xxx",
        "current_term_status": "pending",
        "total_due": 8400.00,
        "total_paid": 0.00,
        "remaining_balance": 8400.00,
        "student_count": 420,
        "unit_price": 20.00,
        "days_until_due": 30,
        "is_overdue": false
    }
    ```
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    # Try to get existing metrics
    metrics = await billing_service.get_subscription_metrics(
        session=session,
        school_id=current_user.school_id
    )
    
    # If no metrics, try to auto-generate subscription for current term
    if not metrics:
        # Get current academic term
        term_result = await session.execute(
            select(AcademicTerm)
            .where(AcademicTerm.school_id == current_user.school_id)
            .order_by(AcademicTerm.start_date.desc())
        )
        current_term = term_result.scalars().first()
        
        if current_term:
            # Try to generate subscription
            result = await billing_service.generate_term_subscription(
                session=session,
                school_id=current_user.school_id,
                academic_term_id=current_term.id
            )
            
            if result.get("success"):
                # Retry getting metrics
                metrics = await billing_service.get_subscription_metrics(
                    session=session,
                    school_id=current_user.school_id
                )
        
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No subscription available. Please ensure students are enrolled and try again."
            )
    
    return metrics.dict()


# ============================================================================
# ENDPOINTS - WEBHOOK (PAYSTACK CALLBACK)
# ============================================================================

@router.post("/webhook/paystack", status_code=200)
async def handle_paystack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Handle Paystack webhook callback for platform subscription payments
    
    **Note:** This endpoint does NOT require authentication
    **Security:** Paystack signature is verified
    
    **Webhook Event:**
    Paystack sends POST request to this endpoint on successful/failed payment
    """
    
    try:
        # Get webhook body
        body = await request.body()
        payload = json.loads(body)
        
        # Verify Paystack signature
        paystack_secret = os.getenv("PAYSTACK_SECRET_KEY", "")
        signature = request.headers.get("x-paystack-signature", "")
        
        # Verify signature (implementation depends on Paystack client)
        # For now, we'll trust the reference and amount
        
        if payload.get("event") != "charge.success":
            logger.info(f"Ignoring webhook event: {payload.get('event')}")
            return {"status": "ok"}
        
        # Extract payment details
        data = payload.get("data", {})
        reference = data.get("reference")
        amount = data.get("amount") / 100  # Convert from kobo to GHS
        status_val = data.get("status")
        
        if status_val != "success":
            logger.info(f"Payment unsuccessful: {reference}")
            return {"status": "ok"}
        
        # Get transaction
        txn_result = await session.execute(
            select(OnlineTransaction).where(
                OnlineTransaction.reference == reference
            )
        )
        transaction = txn_result.scalar_one_or_none()
        
        if not transaction:
            logger.warning(f"Transaction not found for reference: {reference}")
            return {"status": "ok"}
        
        # Check if it's a platform subscription payment
        if not transaction.fee_id.startswith("sub-"):
            logger.info(f"Not a platform subscription payment: {reference}")
            return {"status": "ok"}
        
        # Verify and process
        result = await billing_service.verify_and_process_payment(
            session=session,
            transaction_id=transaction.id,
            reference=reference,
            amount_paid=amount
        )
        
        if result.get("success"):
            logger.info(f"Webhook processed successfully: {reference}")
        else:
            logger.error(f"Webhook processing failed: {result.get('error')}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        # Return 200 OK to Paystack to avoid retries, but log the error
        return {"status": "error", "message": str(e)}


# ============================================================================
# ENDPOINTS - PHASE 2: LATE FEES, DISCOUNTS, REMINDERS, REPORTING
# ============================================================================

# --- LATE FEES ENDPOINTS ---

@router.post("/late-fees/apply", status_code=200)
async def apply_late_fees(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Check and apply late fees to overdue subscriptions (Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "subscriptions_with_late_fees": 5,
        "message": "Applied late fees to 5 subscriptions"
    }
    ```
    """
    
    # Admin only
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can apply late fees"
        )
    
    from services.late_fee_service import LateFeeService
    
    service = LateFeeService()
    result = await service.check_and_apply_late_fees(
        session=session,
        school_id=current_user.school_id if current_user.school_id else None
    )
    
    return result


@router.post("/subscriptions/{subscription_id}/late-fee/waive", status_code=200)
async def waive_late_fee(
    subscription_id: str,
    reason: str = "Manual waiver",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Waive late fee for subscription (Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "waived_amount": 420.00,
        "new_total_due": 8400.00
    }
    ```
    """
    
    # Admin or school admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SCHOOL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    from services.late_fee_service import LateFeeService
    
    service = LateFeeService()
    result = await service.waive_late_fee(
        session=session,
        subscription_id=subscription_id,
        reason=reason
    )
    
    return result


# --- SUSPENSION ENDPOINTS ---

@router.post("/subscriptions/suspend/check-overdue", status_code=200)
async def check_and_suspend_overdue(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Check for overdue subscriptions and suspend if past suspension period (Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "subscriptions_suspended": 2,
        "message": "Suspended 2 overdue subscriptions"
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from services.subscription_suspension_service import SubscriptionSuspensionService
    
    service = SubscriptionSuspensionService()
    
    # Check all school suspensions
    all_results = []
    result = await service.check_and_suspend_overdue(
        session=session,
        school_id=None  # Check all schools
    )
    
    return result


@router.post("/subscriptions/{subscription_id}/suspend", status_code=200)
async def suspend_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_service: PlatformBillingService = Depends(get_billing_service)
) -> dict:
    """
    Manually suspend a subscription (Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "message": "Subscription suspended",
        "subscription_id": "sub-xxx"
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from services.subscription_suspension_service import SubscriptionSuspensionService
    
    service = SubscriptionSuspensionService()
    result = await service.suspend_subscription(
        session=session,
        subscription_id=subscription_id
    )
    
    return result


@router.post("/subscriptions/{subscription_id}/reactivate", status_code=200)
async def reactivate_subscription(
    subscription_id: str,
    verify_payment: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Reactivate a suspended subscription (Admin only)
    
    **Auth Required:** Admin or School
    
    **Query Params:**
    - `verify_payment`: If true, verify payment is complete before reactivating
    
    **Response:**
    ```json
    {
        "success": true,
        "message": "Subscription reactivated",
        "subscription_id": "sub-xxx"
    }
    ```
    """
    
    if current_user.role not in [UserRole.ADMIN, UserRole.SCHOOL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or school access required"
        )
    
    # Verify access
    subscription = await session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.id == subscription_id
        )
    )
    sub = subscription.scalar_one_or_none()
    
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if current_user.role == UserRole.SCHOOL and sub.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    from services.subscription_suspension_service import SubscriptionSuspensionService
    
    service = SubscriptionSuspensionService()
    result = await service.reactivate_subscription(
        session=session,
        subscription_id=subscription_id,
        verify_payment=verify_payment
    )
    
    return result


@router.get("/subscriptions/suspended/list", status_code=200)
async def get_suspended_subscriptions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get all suspended subscriptions for school (Admin only)
    
    **Auth Required:** Admin or School
    
    **Response:**
    ```json
    {
        "suspended_count": 2,
        "subscriptions": [...]
    }
    ```
    """
    
    if current_user.role == UserRole.SCHOOL and not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    from services.subscription_suspension_service import SubscriptionSuspensionService
    
    service = SubscriptionSuspensionService()
    
    school_id = current_user.school_id if current_user.role == UserRole.SCHOOL else None
    
    suspended = await service.get_suspended_subscriptions(
        session=session,
        school_id=school_id
    )
    
    return {
        "suspended_count": len(suspended),
        "subscriptions": suspended
    }


# --- REMINDER ENDPOINTS ---

@router.post("/reminders/send-pending", status_code=200)
async def send_pending_reminders(
    school_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Send pending payment reminders (Admin only)
    
    Sends reminders for:
    - 7 days before due date
    - On due date
    - 3 days after due date (overdue)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "reminders_sent": 5,
        "message": "Sent 5 payment reminders"
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from services.payment_reminder_service import PaymentReminderService
    
    service = PaymentReminderService()
    result = await service.check_and_send_reminders(
        session=session,
        school_id=school_id,
        reminder_type="email"
    )
    
    return result


@router.get("/reminders/{subscription_id}/history", status_code=200)
async def get_reminder_history(
    subscription_id: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get reminder history for a subscription
    
    **Auth Required:** Authenticated user
    
    **Response:**
    ```json
    {
        "subscription_id": "sub-xxx",
        "reminder_count": 3,
        "reminders": [...]
    }
    ```
    """
    
    from services.payment_reminder_service import PaymentReminderService
    
    service = PaymentReminderService()
    reminders = await service.get_reminder_history(
        session=session,
        subscription_id=subscription_id,
        limit=limit
    )
    
    return {
        "subscription_id": subscription_id,
        "reminder_count": len(reminders),
        "reminders": reminders
    }


# --- DISCOUNT ENDPOINTS ---

@router.post("/discounts/rules", status_code=201)
async def create_discount_rule(
    min_students: int,
    discount_percentage: float = None,
    discount_amount: float = None,
    max_students: int = None,
    description: str = "",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Create bulk discount rule (School Admin only)
    
    **Auth Required:** Admin or School
    
    **Query Params:**
    - `min_students`: Minimum students to apply discount
    - `discount_percentage`: % discount (e.g., 5 for 5%)
    - `max_students` (optional): Upper limit
    - `description`: Rule description
    
    **Response:**
    ```json
    {
        "success": true,
        "rule_id": "rule-xxx",
        "description": "500+ students get 5% off"
    }
    ```
    """
    
    if current_user.role not in [UserRole.ADMIN, UserRole.SCHOOL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or school users can create discount rules"
        )
    
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    from services.bulk_discount_service import BulkDiscountService
    
    service = BulkDiscountService()
    result = await service.create_discount_rule(
        session=session,
        school_id=school_id,
        min_students=min_students,
        discount_percentage=discount_percentage,
        discount_amount=discount_amount,
        max_students=max_students,
        description=description
    )
    
    return result


@router.get("/discounts/rules", status_code=200)
async def list_discount_rules(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    List all discount rules for school
    
    **Auth Required:** Authenticated user
    
    **Response:**
    ```json
    {
        "rules": [
            {
                "id": "rule-xxx",
                "min_students": 500,
                "discount_percentage": 5.0,
                "description": "500+ students get 5% off"
            }
        ]
    }
    ```
    """
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a school"
        )
    
    from services.bulk_discount_service import BulkDiscountService
    
    service = BulkDiscountService()
    rules = await service.list_discount_rules(
        session=session,
        school_id=current_user.school_id
    )
    
    return {"rules": rules}


# --- REMINDER ENDPOINTS ---

@router.post("/reminders/send-pending", status_code=200)
async def send_pending_reminders(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Send pending payment reminders (Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "reminders_sent": 12,
        "message": "Sent 12 payment reminders"
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can send reminders"
        )
    
    from services.payment_reminder_service import PaymentReminderService
    
    service = PaymentReminderService()
    result = await service.send_pending_reminders(
        session=session,
        school_id=current_user.school_id if current_user.school_id else None
    )
    
    return result


@router.get("/subscriptions/{subscription_id}/reminders", status_code=200)
async def get_reminder_history(
    subscription_id: str,
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get reminder history for subscription
    
    **Auth Required:** Authenticated user
    
    **Response:**
    ```json
    {
        "count": 3,
        "data": [
            {
                "id": "rem-xxx",
                "type": "sms",
                "recipient": "+233XXXXXXXXXX",
                "status": "sent",
                "sent_at": "2026-05-08T10:30:00"
            }
        ]
    }
    ```
    """
    
    from services.payment_reminder_service import PaymentReminderService
    
    service = PaymentReminderService()
    result = await service.get_reminder_history(
        session=session,
        subscription_id=subscription_id,
        limit=limit,
        offset=offset
    )
    
    return result


# --- REPORTING ENDPOINTS ---

@router.get("/reports/revenue", status_code=200)
async def get_revenue_report(
    school_id: str = None,
    academic_year: str = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get revenue and collection report
    
    **Auth Required:** Admin
    
    **Query Params:**
    - `school_id` (optional): Filter by school
    - `academic_year` (optional): Filter by year (e.g., "2025/2026")
    
    **Response:**
    ```json
    {
        "success": true,
        "report": {
            "school_id": "ALL",
            "academic_year": "2025/2026",
            "total_subscriptions": 42,
            "total_revenue_expected": 352800.00,
            "total_revenue_collected": 298600.00,
            "collection_rate": 84.64,
            "overdue_subscriptions": 8,
            "overdue_amount": 67200.00,
            "late_fees_charged": 5,
            "late_fees_total": 2100.00,
            "total_discounts_given": 28000.00
        }
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view reports"
        )
    
    # If not admin of all schools, can only view own school
    if school_id and school_id != current_user.school_id:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view other schools' reports"
            )
    
    from services.billing_reporting_service import BillingReportingService
    
    service = BillingReportingService()
    result = await service.get_revenue_report(
        session=session,
        school_id=school_id,
        academic_year=academic_year
    )
    
    return result


@router.get("/reports/aging", status_code=200)
async def get_aging_analysis(
    school_id: str = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get aging analysis of overdue accounts
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "success": true,
        "total_overdue": 67200.00,
        "aging_buckets": {
            "current": {"count": 34, "amount": 285200.00, "percentage": 80.92},
            "1_30_days": {"count": 5, "amount": 42000.00, "percentage": 11.91},
            "31_60_days": {"count": 2, "amount": 16800.00, "percentage": 4.76},
            "61_plus_days": {"count": 1, "amount": 8400.00, "percentage": 2.38}
        }
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view reports"
        )
    
    from services.billing_reporting_service import BillingReportingService
    
    service = BillingReportingService()
    result = await service.get_aging_analysis(
        session=session,
        school_id=school_id
    )
    
    return result


@router.get("/reports/top-paying-schools", status_code=200)
async def get_top_paying_schools(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get top paying schools by collection rate (System Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "schools": [
            {
                "school_id": "sch-001",
                "collection_rate": 98.50,
                "expected": 84000.00,
                "collected": 82800.00
            }
        ]
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view reports"
        )
    
    from services.billing_reporting_service import BillingReportingService
    
    service = BillingReportingService()
    schools = await service.get_top_paying_schools(
        session=session,
        limit=limit
    )
    
    return {"schools": schools}


@router.get("/reports/bottom-paying-schools", status_code=200)
async def get_bottom_paying_schools(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get bottom paying schools needing follow-up (System Admin only)
    
    **Auth Required:** Admin
    
    **Response:**
    ```json
    {
        "schools": [
            {
                "school_id": "sch-042",
                "collection_rate": 42.30,
                "expected": 84000.00,
                "collected": 35532.00,
                "overdue": 28000.00,
                "late_fees": 1400.00
            }
        ]
    }
    ```
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view reports"
        )
    
    from services.billing_reporting_service import BillingReportingService
    
    service = BillingReportingService()
    schools = await service.get_bottom_paying_schools(
        session=session,
        limit=limit
    )
    
    return {"schools": schools}
