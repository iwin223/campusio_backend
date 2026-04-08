"""Finance Reports router - Schools view payment data"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_
from sqlmodel import select

from database import get_session
from auth import get_current_user
from models.user import User
from models.payment import OnlineTransaction, TransactionStatus, PaymentVerification
from models.fee import Fee, PaymentStatus as FeeStatus
from models.student import Student
from models.parent import Parent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["Finance Reports"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class PaymentSummary:
    """Summary of a payment"""
    transaction_id: str
    reference: str
    student_name: str
    parent_name: str
    parent_email: str
    parent_phone: str
    fee_type: str
    amount: float
    status: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class PaymentStatistics:
    """Payment statistics for dashboard"""
    total_transactions: int
    successful_payments: int
    failed_payments: int
    pending_payments: int
    total_amount_collected: float
    total_amount_pending: float
    period_start: datetime
    period_end: datetime


class ParentPaymentHistory:
    """Payment history for a specific parent"""
    parent_id: str
    parent_name: str
    parent_email: str
    total_payments: int
    total_amount_paid: float
    last_payment_date: Optional[datetime]
    transactions: List[PaymentSummary]


# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

async def verify_school_financial_access(
    current_user: User = Depends(get_current_user)
) -> str:
    """
    Verify user has access to school financial data.
    Only admin, accountant, and finance staff can view.
    """
    allowed_roles = ['admin', 'accountant', 'finance_officer', 'principal']
    
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role}' cannot access financial reports"
        )
    
    return current_user.school_id


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/payments", status_code=200)
async def get_payments(
    skip: int = Query(0, gte=0),
    limit: int = Query(50, gte=1, le=500),
    status_filter: Optional[str] = Query(None),  # pending, success, failed, all
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),  # Search by parent name/email/student name
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get list of online payments for the school.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Query Parameters:**
    - skip: Number of records to skip (pagination)
    - limit: Number of records to return (max 500)
    - status_filter: Filter by status (pending, success, failed, all)
    - start_date: Filter payments from this date
    - end_date: Filter payments to this date
    - search: Search by parent name, email, or student name
    
    **Returns:**
    ```json
    {
        "total": 150,
        "skip": 0,
        "limit": 50,
        "payments": [
            {
                "transaction_id": "txn-001",
                "reference": "ref-xyz",
                "student_name": "John Doe",
                "parent_name": "Jane Doe",
                "parent_email": "jane@example.com",
                "parent_phone": "+233123456789",
                "fee_type": "Tuition",
                "amount": 500.00,
                "status": "success",
                "initiated_at": "2026-04-08T10:30:00",
                "completed_at": "2026-04-08T10:35:00",
                "verified_at": "2026-04-08T10:35:30"
            }
        ]
    }
    ```
    """
    try:
        # Build query
        query = select(
            OnlineTransaction.id,
            OnlineTransaction.reference,
            Student.name,
            Parent.first_name,
            Parent.email,
            Parent.phone,
            Fee.fee_type,
            OnlineTransaction.amount,
            OnlineTransaction.status,
            OnlineTransaction.initiated_at,
            OnlineTransaction.completed_at,
            OnlineTransaction.verified_at
        ).join(
            Fee, OnlineTransaction.fee_id == Fee.id
        ).join(
            Student, OnlineTransaction.student_id == Student.id
        ).join(
            Parent, OnlineTransaction.parent_id == Parent.id
        ).where(
            OnlineTransaction.school_id == school_id
        )
        
        # Status filter
        if status_filter and status_filter != 'all':
            query = query.where(OnlineTransaction.status == status_filter)
        
        # Date range filter
        if start_date:
            query = query.where(OnlineTransaction.initiated_at >= start_date)
        if end_date:
            # Add 1 day to include full end date
            end_date_inclusive = end_date + timedelta(days=1)
            query = query.where(OnlineTransaction.initiated_at < end_date_inclusive)
        
        # Search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Student.name.ilike(search_pattern),
                    Parent.first_name.ilike(search_pattern),
                    Parent.email.ilike(search_pattern)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(OnlineTransaction).where(
            OnlineTransaction.school_id == school_id
        )
        if status_filter and status_filter != 'all':
            count_query = count_query.where(OnlineTransaction.status == status_filter)
        if start_date:
            count_query = count_query.where(OnlineTransaction.initiated_at >= start_date)
        if end_date:
            end_date_inclusive = end_date + timedelta(days=1)
            count_query = count_query.where(OnlineTransaction.initiated_at < end_date_inclusive)
        
        total = await session.exec(count_query)
        total = total.one()
        
        # Execute query with pagination
        query = query.order_by(OnlineTransaction.initiated_at.desc()).offset(skip).limit(limit)
        results = await session.exec(query)
        payments = results.all()
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "payments": [
                {
                    "transaction_id": p[0],
                    "reference": p[1],
                    "student_name": p[2],
                    "parent_name": f"{p[3]} {getattr(Parent, 'last_name', '')}",
                    "parent_email": p[4],
                    "parent_phone": p[5],
                    "fee_type": p[6],
                    "amount": float(p[7]),
                    "status": p[8],
                    "initiated_at": p[9],
                    "completed_at": p[10],
                    "verified_at": p[11]
                }
                for p in payments
            ]
        }
    
    except Exception as e:
        logger.error(f"Error fetching payments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching payments: {str(e)}")


@router.get("/payments/statistics", status_code=200)
async def get_payment_statistics(
    period_days: int = Query(30, ge=1, le=365),
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> PaymentStatistics:
    """
    Get payment statistics for the school.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Query Parameters:**
    - period_days: Number of days to look back (default 30)
    
    **Returns:**
    ```json
    {
        "total_transactions": 150,
        "successful_payments": 120,
        "failed_payments": 15,
        "pending_payments": 15,
        "total_amount_collected": 45000.00,
        "total_amount_pending": 7500.00,
        "period_start": "2026-03-08T00:00:00",
        "period_end": "2026-04-08T00:00:00"
    }
    ```
    """
    try:
        period_start = datetime.utcnow() - timedelta(days=period_days)
        period_end = datetime.utcnow()
        
        # Get totals
        query = select(OnlineTransaction).where(
            and_(
                OnlineTransaction.school_id == school_id,
                OnlineTransaction.initiated_at >= period_start,
                OnlineTransaction.initiated_at <= period_end
            )
        )
        
        results = await session.exec(query)
        transactions = results.all()
        
        total_transactions = len(transactions)
        successful = sum(1 for t in transactions if t.status == TransactionStatus.SUCCESS)
        failed = sum(1 for t in transactions if t.status == TransactionStatus.FAILED)
        pending = sum(1 for t in transactions if t.status in [
            TransactionStatus.PENDING, 
            TransactionStatus.PROCESSING,
            TransactionStatus.WEBHOOK_RECEIVED
        ])
        
        total_collected = sum(
            t.amount_paid for t in transactions 
            if t.status == TransactionStatus.SUCCESS
        )
        total_pending = sum(
            t.amount for t in transactions 
            if t.status in [TransactionStatus.PENDING, TransactionStatus.PROCESSING]
        )
        
        return {
            "total_transactions": total_transactions,
            "successful_payments": successful,
            "failed_payments": failed,
            "pending_payments": pending,
            "total_amount_collected": float(total_collected),
            "total_amount_pending": float(total_pending),
            "period_start": period_start,
            "period_end": period_end
        }
    
    except Exception as e:
        logger.error(f"Error fetching statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching statistics: {str(e)}")


@router.get("/payments/by-parent", status_code=200)
async def get_payments_by_parent(
    skip: int = Query(0, gte=0),
    limit: int = Query(50, gte=1, le=500),
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get payment history grouped by parent.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Returns:**
    ```json
    {
        "total": 75,
        "parents": [
            {
                "parent_id": "parent-001",
                "parent_name": "Jane Doe",
                "parent_email": "jane@example.com",
                "total_payments": 5,
                "total_amount_paid": 2500.00,
                "last_payment_date": "2026-04-08T10:30:00",
                "transactions": [...]
            }
        ]
    }
    ```
    """
    try:
        # Get unique parents with their payment summaries
        parent_query = select(
            Parent.id,
            Parent.first_name,
            Parent.email
        ).join(
            OnlineTransaction, Parent.id == OnlineTransaction.parent_id
        ).where(
            OnlineTransaction.school_id == school_id
        ).distinct().offset(skip).limit(limit)
        
        parent_results = await session.exec(parent_query)
        parents = parent_results.all()
        
        parent_data = []
        for parent_id, parent_first, parent_email in parents:
            # Get transactions for this parent
            txn_query = select(OnlineTransaction).where(
                and_(
                    OnlineTransaction.parent_id == parent_id,
                    OnlineTransaction.school_id == school_id,
                    OnlineTransaction.status == TransactionStatus.SUCCESS
                )
            ).order_by(OnlineTransaction.initiated_at.desc())
            
            txn_results = await session.exec(txn_query)
            transactions = txn_results.all()
            
            total_paid = sum(t.amount_paid for t in transactions)
            last_payment = transactions[0].completed_at if transactions else None
            
            parent_data.append({
                "parent_id": parent_id,
                "parent_name": parent_first,
                "parent_email": parent_email,
                "total_payments": len(transactions),
                "total_amount_paid": float(total_paid),
                "last_payment_date": last_payment,
                "transactions": len(transactions)  # Simplified for listing
            })
        
        return {
            "total": len(parent_data),
            "parents": parent_data
        }
    
    except Exception as e:
        logger.error(f"Error fetching parent payments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching parent payments: {str(e)}")


@router.get("/payments/by-fee-type", status_code=200)
async def get_payments_by_fee_type(
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get payment summary grouped by fee type.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Returns:**
    ```json
    {
        "fee_types": [
            {
                "fee_type": "Tuition",
                "total_due": 150000.00,
                "total_collected": 120000.00,
                "total_pending": 30000.00,
                "collection_rate": 80.0,
                "transaction_count": 45
            }
        ]
    }
    ```
    """
    try:
        query = select(
            Fee.fee_type,
            func.sum(Fee.amount_due).label('total_due'),
            func.sum(Fee.amount_paid).label('total_paid'),
            func.count(Fee.id).label('fee_count')
        ).select_from(Fee).join(
            OnlineTransaction, Fee.id == OnlineTransaction.fee_id
        ).where(
            Fee.school_id == school_id
        ).group_by(Fee.fee_type)
        
        results = await session.exec(query)
        fee_types = results.all()
        
        summary = []
        for fee_type, total_due, total_paid, count in fee_types:
            total_due = float(total_due or 0)
            total_paid = float(total_paid or 0)
            total_pending = total_due - total_paid
            collection_rate = (total_paid / total_due * 100) if total_due > 0 else 0
            
            summary.append({
                "fee_type": fee_type,
                "total_due": total_due,
                "total_collected": total_paid,
                "total_pending": total_pending,
                "collection_rate": round(collection_rate, 2),
                "transaction_count": count
            })
        
        return {"fee_types": sorted(summary, key=lambda x: x['total_collected'], reverse=True)}
    
    except Exception as e:
        logger.error(f"Error fetching fee type summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching fee type summary: {str(e)}")


@router.get("/payments/reconciliation", status_code=200)
async def get_payment_reconciliation(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get reconciliation report comparing payments to GL entries.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Returns:**
    ```json
    {
        "total_transactions": 150,
        "posted_to_gl": 145,
        "pending_gl_posting": 5,
        "discrepancies": [
            {
                "transaction_id": "txn-001",
                "issue": "GL entry not created",
                "amount": 500.00
            }
        ]
    }
    ```
    """
    try:
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = select(OnlineTransaction).where(
            and_(
                OnlineTransaction.school_id == school_id,
                OnlineTransaction.status == TransactionStatus.SUCCESS,
                OnlineTransaction.initiated_at >= start_date,
                OnlineTransaction.initiated_at <= end_date
            )
        )
        
        results = await session.exec(query)
        transactions = results.all()
        
        discrepancies = []
        posted_count = 0
        
        for txn in transactions:
            if txn.journal_entry_id:
                posted_count += 1
            else:
                discrepancies.append({
                    "transaction_id": txn.id,
                    "reference": txn.reference,
                    "issue": "GL entry not created",
                    "amount": float(txn.amount_paid),
                    "completed_at": txn.completed_at
                })
        
        return {
            "total_transactions": len(transactions),
            "posted_to_gl": posted_count,
            "pending_gl_posting": len(transactions) - posted_count,
            "discrepancies": discrepancies
        }
    
    except Exception as e:
        logger.error(f"Error fetching reconciliation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching reconciliation: {str(e)}")


@router.get("/payments/{transaction_id}", status_code=200)
async def get_payment_detail(
    transaction_id: str,
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Get detailed view of a specific payment transaction.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    
    **Path Parameters:**
    - transaction_id: UUID of the transaction
    
    **Returns:**
    ```json
    {
        "transaction": {
            "id": "txn-001",
            "reference": "ref-xyz",
            "student_name": "John Doe",
            "parent_name": "Jane Doe",
            "parent_email": "jane@example.com",
            "fee_type": "Tuition",
            "amount": 500.00,
            "amount_paid": 500.00,
            "status": "success",
            "initiated_at": "2026-04-08T10:30:00",
            "completed_at": "2026-04-08T10:35:00",
            "verified_at": "2026-04-08T10:35:30",
            "journal_entry_id": "jne-001"
        }
    }
    ```
    """
    try:
        query = select(OnlineTransaction).where(
            and_(
                OnlineTransaction.id == transaction_id,
                OnlineTransaction.school_id == school_id
            )
        )
        
        result = await session.exec(query)
        transaction = result.first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Get related data
        fee_query = select(Fee).where(Fee.id == transaction.fee_id)
        fee = await session.exec(fee_query)
        fee = fee.first()
        
        student_query = select(Student).where(Student.id == transaction.student_id)
        student = await session.exec(student_query)
        student = student.first()
        
        parent_query = select(Parent).where(Parent.id == transaction.parent_id)
        parent = await session.exec(parent_query)
        parent = parent.first()
        
        return {
            "transaction": {
                "id": transaction.id,
                "reference": transaction.reference,
                "student_name": student.name if student else "Unknown",
                "student_id": transaction.student_id,
                "parent_name": f"{parent.first_name} {parent.last_name}" if parent else "Unknown",
                "parent_email": parent.email if parent else "Unknown",
                "parent_phone": parent.phone if parent else "Unknown",
                "fee_type": fee.fee_type if fee else "Unknown",
                "amount": float(transaction.amount),
                "amount_paid": float(transaction.amount_paid),
                "status": transaction.status,
                "gateway": transaction.gateway,
                "initiated_at": transaction.initiated_at,
                "completed_at": transaction.completed_at,
                "verified_at": transaction.verified_at,
                "journal_entry_id": transaction.journal_entry_id,
                "failed_reason": transaction.failed_reason
            }
        }
    
    except Exception as e:
        logger.error(f"Error fetching transaction detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching transaction: {str(e)}")


# ============================================================================
# EXPORT ENDPOINTS (CSV/PDF)
# ============================================================================

@router.get("/payments/export/csv", status_code=200)
async def export_payments_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    school_id: str = Depends(verify_school_financial_access),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Export payments as CSV. Returns URL to download.
    
    **Auth Required:** Admin, Accountant, Finance Officer
    """
    # Implementation would export to S3 or generate CSV file
    return {
        "message": "Export functionality to be implemented",
        "status": "pending"
    }
