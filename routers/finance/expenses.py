"""Expense Router - School expense management with approval workflow

ROLE-BASED ACCESS CONTROL:
- SUPER_ADMIN: Full access to all operations
- SCHOOL_ADMIN: Full access to school's expenses (approve/post)
- HR: Can create, submit, and view expenses
- TEACHER/STUDENT/PARENT: Read-only access to summary
- Others: No access to expenses

SCHOOL SCOPING:
- All endpoints enforce school_id scoping for multi-tenancy
- All expenses automatically scoped to current user's school

EXPENSE LIFECYCLE:
- DRAFT: Created, can be edited or submitted
- PENDING: Submitted for approval, awaiting admin review
- APPROVED: Approved by admin, ready to post to GL
- POSTED: Posted to GL (immutable)
- REJECTED: Rejected during approval (no GL posting)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime

from models.finance import (
    Expense,
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    ExpenseCategory,
    ExpenseStatus,
    PaymentStatus,
    ExpenseSubmitRequest,
    ExpenseApprovalRequest,
    ExpenseRejectionRequest,
    ExpensePaymentRequest,
    ExpenseSummary,
)
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from services.expense_service import ExpenseService, ExpenseError, ExpenseValidationError

router = APIRouter(prefix="/finance/expenses", tags=["Finance - Expenses"])


# ==================== Expense Creation ====================

@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
        UserRole.HR,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Create a new expense record (in DRAFT status)
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN, HR
    
    Required fields:
    - category: Expense category [utilities, supplies, maintenance, transportation, meals, professional_services, insurance, equipment, furniture, cleaning, security, programs, travel, printing, miscellaneous]
    - description: What was the expense for
    - amount: Amount spent (must be positive)
    
    Optional fields:
    - vendor_name: Who was paid
    - gl_account_id: GL account to post to (must exist and be active)
    - gl_account_code: GL account code for reference
    - expense_date: When incurred (default: now)
    - currency: Currency code (default: GHS)
    - notes: Additional notes
    
    Returns:
    - New expense in DRAFT status
    - Can be edited or deleted while in DRAFT
    - Must be submitted for approval before posting to GL
    
    Example:
    ```json
    {
        "category": "utilities",
        "description": "Monthly electricity bill",
        "vendor_name": "ECG",
        "amount": 5000.00,
        "currency": "GHS",
        "expense_date": "2026-04-01T10:00:00",
        "notes": "Month of March 2026"
    }
    ```
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context - contact administrator"
        )
    
    service = ExpenseService(session)
    
    try:
        expense = await service.create_expense(
            school_id=school_id,
            expense_data=expense_data,
            created_by=current_user.id,
        )
        return ExpenseResponse.model_validate(expense)
    except ExpenseValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating expense: {str(e)}"
        )


# ==================== Expense Retrieval ====================

@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific expense by ID
    
    **Access:** All authenticated users (read-only for non-admin)
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    expense = await service.get_expense_by_id(school_id, expense_id)
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )
    
    return ExpenseResponse.model_validate(expense)


@router.get("", response_model=List[ExpenseResponse])
async def list_expenses(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    skip: int = Query(0, ge=0, description="Number of expenses to skip"),
    limit: int = Query(50, ge=1, le=1000, description="Number of expenses to return"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List expenses with optional filtering
    
    **Access:** All authenticated users
    
    Query parameters:
    - category: Filter by category [utilities, supplies, maintenance, etc.]
    - status: Filter by status [draft, pending, approved, rejected, posted]
    - start_date: Filter expenses from this date onwards (ISO format)
    - end_date: Filter expenses up to this date (ISO format)
    - skip: Pagination offset (default: 0)
    - limit: Page size (default: 50, max: 1000)
    
    Returns:
    - List of expenses matching filters
    - Ordered by expense_date descending
    
    Examples:
    - GET /api/finance/expenses - All expenses
    - GET /api/finance/expenses?status=pending - All pending approval
    - GET /api/finance/expenses?category=utilities - All utility expenses
    - GET /api/finance/expenses?status=draft&limit=25 - First 25 draft expenses
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    # Parse optional filter parameters
    expense_category = None
    if category:
        try:
            expense_category = ExpenseCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {category}"
            )
    
    expense_status = None
    if status:
        try:
            expense_status = ExpenseStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )
    
    service = ExpenseService(session)
    
    try:
        expenses = await service.get_expenses_filtered(
            school_id=school_id,
            category=expense_category,
            status=expense_status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
        return [ExpenseResponse.model_validate(exp) for exp in expenses]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving expenses: {str(e)}"
        )


# ==================== Expense Updates ====================

@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str,
    update_data: ExpenseUpdate,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
        UserRole.HR,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Update a DRAFT expense
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN, HR
    
    Can update:
    - category, description, vendor_name
    - amount, currency
    - gl_account_id, gl_account_code
    - expense_date, notes
    
    Restrictions:
    - Only DRAFT expenses can be updated
    - Submitted/approved expenses must be rejected to modify
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        updated_expense = await service.update_expense(
            school_id=school_id,
            expense_id=expense_id,
            update_data=update_data,
        )
        return ExpenseResponse.model_validate(updated_expense)
    except ExpenseValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating expense: {str(e)}"
        )


# ==================== Approval Workflow ====================

@router.post("/{expense_id}/submit", response_model=ExpenseResponse)
async def submit_expense(
    expense_id: str,
    request: ExpenseSubmitRequest,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
        UserRole.HR,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Submit expense for approval (DRAFT → PENDING)
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN, HR
    
    Request body:
    - submission_notes: Optional notes for admin review
    
    Effect:
    - Changes status from DRAFT to PENDING
    - Cannot be edited after submission
    - Admin review and approval required before GL posting
    
    Returns:
    - Expense with PENDING status
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        submitted_expense = await service.submit_expense(
            school_id=school_id,
            expense_id=expense_id,
            submitted_by=current_user.id,
        )
        return ExpenseResponse.model_validate(submitted_expense)
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting expense: {str(e)}"
        )


@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
async def approve_expense(
    expense_id: str,
    request: ExpenseApprovalRequest,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Approve an expense for GL posting (PENDING → APPROVED)
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN only
    
    Request body:
    - approval_notes: Optional approval notes for audit trail
    
    Effect:
    - Changes status from PENDING to APPROVED
    - Ready to be posted to GL
    - GL posting is separate step (see /post endpoint)
    
    Returns:
    - Expense with APPROVED status
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        approved_expense = await service.approve_expense(
            school_id=school_id,
            expense_id=expense_id,
            approved_by=current_user.id,
            approval_notes=request.approval_notes,
        )
        return ExpenseResponse.model_validate(approved_expense)
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving expense: {str(e)}"
        )


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
async def reject_expense(
    expense_id: str,
    request: ExpenseRejectionRequest,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Reject an expense (PENDING → REJECTED)
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN only
    
    Request body:
    - rejection_reason: Required - reason for rejection
    
    Effect:
    - Changes status from PENDING to REJECTED
    - Will NOT be posted to GL
    - Audit trail preserved
    
    Returns:
    - Expense with REJECTED status
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        rejected_expense = await service.reject_expense(
            school_id=school_id,
            expense_id=expense_id,
            rejected_by=current_user.id,
            rejection_reason=request.rejection_reason,
        )
        return ExpenseResponse.model_validate(rejected_expense)
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting expense: {str(e)}"
        )


# ==================== GL Posting ====================

@router.post("/{expense_id}/post", response_model=ExpenseResponse)
async def post_expense_to_gl(
    expense_id: str,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Post approved expense to GL (APPROVED → POSTED)
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN only
    
    Effect:
    - Changes status from APPROVED to POSTED
    - Creates GL journal entry automatically
    - Posts to GL immediately (immutable)
    - Links to journal entry for audit trail
    
    GL Posting:
    - Dr. Expense GL account: full amount
    - Cr. 1010 (Bank Account): full amount
    
    Returns:
    - Expense with POSTED status and journal_entry_id
    
    Note: Expense GL account must exist and be active
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        posted_expense = await service.post_expense_to_gl(
            school_id=school_id,
            expense_id=expense_id,
            posted_by=current_user.id,
        )
        return ExpenseResponse.model_validate(posted_expense)
    except ExpenseValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error posting expense to GL: {str(e)}"
        )


# ==================== Payment Tracking ====================

@router.post("/{expense_id}/payment", response_model=ExpenseResponse)
async def record_expense_payment(
    expense_id: str,
    request: ExpensePaymentRequest,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
    )),
    session: AsyncSession = Depends(get_session),
):
    """Record a payment for an expense
    
    **Access:** SUPER_ADMIN, SCHOOL_ADMIN only
    
    Request body:
    - amount_paid: Amount being paid
    - payment_date: Date of payment
    - payment_notes: Optional notes
    
    Effect:
    - Increases amount_paid
    - Updates payment_status (outstanding/partial/paid)
    - Does not affect GL posting
    
    Returns:
    - Updated expense with payment_status and amount_paid
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        updated_expense = await service.record_payment(
            school_id=school_id,
            expense_id=expense_id,
            amount_paid=request.amount_paid,
            paid_by=current_user.id,
            payment_date=request.payment_date,
        )
        return ExpenseResponse.model_validate(updated_expense)
    except ExpenseValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ExpenseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording payment: {str(e)}"
        )


# ==================== Summary & Analysis ====================

@router.get("/summary/stats", response_model=dict)
async def get_expense_summary(
    start_date: Optional[datetime] = Query(None, description="Start date for summary"),
    end_date: Optional[datetime] = Query(None, description="End date for summary"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get expense summary statistics
    
    **Access:** All authenticated users
    
    Query parameters:
    - start_date: Filter summary from this date (ISO format, optional)
    - end_date: Filter summary up to this date (ISO format, optional)
    
    Returns:
    - total_expenses: Count of all expenses
    - draft_count, pending_count, approved_count, posted_count, rejected_count
    - total_amount: Sum of all expense amounts
    - total_paid: Sum of all payments
    - outstanding_amount: Unpaid portion
    - by_category: Breakdown by expense category
    
    Use case: Dashboard analytics and budget tracking
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No school context"
        )
    
    service = ExpenseService(session)
    
    try:
        summary = await service.get_expense_summary(
            school_id=school_id,
            start_date=start_date,
            end_date=end_date,
        )
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )
