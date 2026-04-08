"""Payment router - handles payment API endpoints"""
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import os

from database import get_session
from auth import get_current_user
from models.payment import OnlineTransaction, TransactionStatus
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_services():
    """Initialize payment services (lazy initialization)"""
    from services.online_payment_service import OnlinePaymentService
    from services.paystack_service import PaystackService
    
    paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    
    if not paystack_secret_key:
        raise ValueError("PAYSTACK_SECRET_KEY not configured in .env")
    
    return {
        "paystack": PaystackService(paystack_secret_key),
        "online_payment": OnlinePaymentService(paystack_secret_key)
    }


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class InitiatePaymentRequest:
    """Request to initiate payment"""
    fee_id: str


class TransactionResponse:
    """Response for transaction status"""
    transaction_id: str
    fee_id: str
    student_id: str
    amount: float
    amount_paid: float
    status: str
    payment_url: Optional[str]
    reference: str
    created_at: str
    completed_at: Optional[str]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/initialize", status_code=200)
async def initialize_payment(
    fee_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Initiate online payment for a fee
    
    **Auth Required:** Parent role
    
    **Query Parameters:**
    - fee_id: UUID of the fee to pay
    
    **Returns:**
    ```json
    {
        "success": true,
        "transaction_id": "TXN-xxx",
        "payment_url": "https://checkout.paystack.com/...",
        "reference": "PAY-xxx",
        "amount": 500.00
    }
    ```
    
    **Errors:**
    - 400: Invalid fee ID
    - 404: Fee not found or already paid
    - 500: Payment initialization failed
    """
    
    try:
        # Get services
        services = get_payment_services()
        online_payment_service = services["online_payment"]
        
        # Verify user is parent
        if current_user.role != "parent":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only parents can initiate payments"
            )
        
        # Get parent's email from user context
        parent_email = current_user.email
        
        # Initiate payment
        result = await online_payment_service.initiate_payment(
            session=session,
            fee_id=fee_id,
            parent_id=current_user.id,
            parent_email=parent_email,
            school_id=current_user.school_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Payment initialization failed")
            )
        
        logger.info(f"Payment initiated: {result['transaction_id']}")
        return result
    
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment system not configured"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment initialization failed"
        )


@router.post("/webhook/paystack", status_code=200)
async def paystack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Webhook endpoint for Paystack payment notifications
    
    **No Auth Required** - Webhook is verified via HMAC signature
    
    **Paystack Calls This:**
    - When payment status changes
    - Includes HMAC-SHA512 signature in X-Paystack-Signature header
    
    **Returns:**
    ```json
    {
        "success": true,
        "processed": true
    }
    ```
    
    **Security:**
    - Verifies HMAC signature before processing
    - Rejects if signature doesn't match
    
    **Errors:**
    - 401: Invalid signature
    - 400: Missing signature or payload
    - 500: Webhook processing error
    """
    
    try:
        # Get services
        services = get_payment_services()
        paystack_service = services["paystack"]
        online_payment_service = services["online_payment"]
        
        # Import PaystackService for static method
        from services.paystack_service import PaystackService
        signature = request.headers.get("X-Paystack-Signature")
        
        if not signature:
            logger.warning("Webhook call without signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Paystack-Signature header"
            )
        
        # Get raw body
        body = await request.body()
        
        # Get secret key
        paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
        
        # Verify signature
        is_valid = PaystackService.verify_webhook_signature(
            payload_bytes=body,
            signature=signature,
            secret_key=paystack_secret_key
        )
        
        if not is_valid:
            logger.warning(f"Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse payload
        payload = json.loads(body)
        
        # Process webhook
        result = await online_payment_service.process_webhook(
            session=session,
            payload=payload
        )
        
        logger.info(f"Webhook processed: {payload.get('reference')}")
        return {"success": True, "processed": result.get("processed", True)}
    
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment system not configured"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


@router.get("/{transaction_id}", status_code=200)
async def get_transaction_status(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get payment transaction status
    
    **Auth Required:** Parent role
    
    **Path Parameters:**
    - transaction_id: UUID of the transaction
    
    **Returns:**
    ```json
    {
        "transaction_id": "TXN-xxx",
        "fee_id": "fee-xxx",
        "student_id": "student-xxx",
        "amount": 500.00,
        "amount_paid": 0.00,
        "status": "pending|processing|success|failed",
        "payment_url": "https://checkout.paystack.com/...",
        "reference": "PAY-xxx",
        "created_at": "2026-04-08T10:30:00",
        "completed_at": null
    }
    ```
    
    **Errors:**
    - 404: Transaction not found
    - 403: Not authorized to view this transaction
    """
    
    try:
        # Get transaction
        result = await session.execute(
            select(OnlineTransaction).where(
                OnlineTransaction.reference == transaction_id,
                OnlineTransaction.school_id == current_user.school_id
            )
        )
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Verify authorization (parent can only see their own)
        if current_user.role == "parent" and transaction.parent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this transaction"
            )
        
        return {
            "transaction_id": transaction.reference,
            "fee_id": str(transaction.fee_id),
            "student_id": str(transaction.student_id),
            "amount": float(transaction.amount),
            "amount_paid": float(transaction.amount_paid or 0),
            "status": transaction.status.value,
            "payment_url": transaction.payment_url,
            "reference": transaction.reference,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
            "failed_reason": transaction.failed_reason
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving transaction"
        )


@router.get("/transactions/", status_code=200)
async def list_transactions(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    List payment transactions (filtered by role)
    
    **Auth Required:** Parent, Admin, or Accountant
    
    **Query Parameters:**
    - skip: Number of records to skip (default 0)
    - limit: Number of records to return (default 50, max 100)
    - status_filter: Filter by status (pending, processing, success, failed)
    
    **For Parents:** Only returns their own transactions
    **For Admin/Accountant:** Returns all transactions for school
    
    **Returns:**
    ```json
    {
        "total": 42,
        "count": 10,
        "skip": 0,
        "limit": 50,
        "transactions": [
            {
                "transaction_id": "TXN-xxx",
                "fee_id": "fee-xxx",
                "student_id": "student-xxx",
                "parent_id": "parent-xxx",
                "amount": 500.00,
                "status": "success",
                "reference": "PAY-xxx",
                "created_at": "2026-04-08T10:30:00"
            }
        ]
    }
    ```
    
    **Errors:**
    - 403: Insufficient permissions
    """
    
    try:
        # Validate limit
        limit = min(limit, 100)
        
        # Build query
        query = select(OnlineTransaction).where(
            OnlineTransaction.school_id == current_user.school_id
        )
        
        # Filter by role
        if current_user.role == "parent":
            query = query.where(OnlineTransaction.parent_id == current_user.id)
        elif current_user.role not in ["admin", "accountant"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Filter by status if provided
        if status_filter:
            try:
                status_enum = TransactionStatus(status_filter)
                query = query.where(OnlineTransaction.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}"
                )
        
        # Get total count
        count_result = await session.execute(select(OnlineTransaction).where(
            OnlineTransaction.school_id == current_user.school_id
        ))
        total = len(count_result.all())
        
        # Get paginated results
        result = await session.execute(query.offset(skip).limit(limit))
        transactions = result.scalars().all()
        
        return {
            "total": total,
            "count": len(transactions),
            "skip": skip,
            "limit": limit,
            "transactions": [
                {
                    "transaction_id": t.reference,
                    "fee_id": str(t.fee_id),
                    "student_id": str(t.student_id),
                    "parent_id": str(t.parent_id),
                    "amount": float(t.amount),
                    "status": t.status.value,
                    "reference": t.reference,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in transactions
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving transactions"
        )
