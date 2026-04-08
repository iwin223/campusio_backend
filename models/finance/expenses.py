"""Expense models for school operational spending

Tracks all school expenses (utilities, supplies, maintenance, etc.)
with approval workflow and GL account mapping.
"""
from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class ExpenseCategory(str, Enum):
    """Categories of school expenses"""
    UTILITIES = "utilities"              # Electricity, water, internet, phone
    SUPPLIES = "supplies"                # Office, classroom, lab materials
    MAINTENANCE = "maintenance"          # Building repairs, equipment maintenance
    TRANSPORTATION = "transportation"    # Transport for school activities
    MEALS = "meals"                      # Staff meals, student programs
    PROFESSIONAL_SERVICES = "professional_services"  # Consultants, auditors
    INSURANCE = "insurance"              # School insurance policies
    EQUIPMENT = "equipment"              # Office/teaching equipment purchases
    FURNITURE = "furniture"              # Desks, chairs, filing cabinets
    CLEANING = "cleaning"                # Cleaning supplies and services
    SECURITY = "security"                # Security services and equipment
    PROGRAMS = "programs"                # Educational programs, workshops
    TRAVEL = "travel"                    # Staff travel, conferences
    PRINTING = "printing"                # Printing and stationery
    MISCELLANEOUS = "miscellaneous"      # Other expenses


class ExpenseStatus(str, Enum):
    """Status of an expense record"""
    DRAFT = "draft"                  # Created but not submitted
    PENDING = "pending"              # Submitted, awaiting approval
    APPROVED = "approved"            # Approved by admin
    REJECTED = "rejected"            # Rejected and not posted
    POSTED = "posted"                # Posted to GL


class PaymentStatus(str, Enum):
    """Payment status of an expense"""
    OUTSTANDING = "outstanding"     # Not yet paid
    PARTIAL = "partial"             # Partially paid
    PAID = "paid"                   # Fully paid


class Expense(SQLModel, table=True):
    """Individual expense record"""
    __tablename__ = "expenses"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Description and classification
    category: ExpenseCategory = Field(index=True)
    description: str  # What was the expense for
    vendor_name: Optional[str] = None  # Who was paid
    
    # Amounts
    amount: float = Field(gt=0.0)  # Must be positive
    currency: str = Field(default="GHS")
    
    # GL mapping
    gl_account_id: Optional[str] = None  # Maps to GL account
    gl_account_code: Optional[str] = None  # Account code for reference
    
    # Dates
    expense_date: datetime = Field(index=True)  # When was expense incurred
    approved_date: Optional[datetime] = None
    posted_date: Optional[datetime] = None
    
    # Approval workflow
    status: ExpenseStatus = Field(default=ExpenseStatus.DRAFT, index=True)
    submitted_by: Optional[str] = None  # User who submitted
    submitted_at: Optional[datetime] = None
    approved_by: Optional[str] = None  # Admin who approved
    rejected_reason: Optional[str] = None
    rejected_by: Optional[str] = None
    
    # Payment tracking
    payment_status: PaymentStatus = Field(default=PaymentStatus.OUTSTANDING, index=True)
    amount_paid: float = Field(default=0.0, ge=0.0)
    payment_date: Optional[datetime] = None
    paid_by: Optional[str] = None
    
    # Journal entry link (if posted to GL)
    journal_entry_id: Optional[str] = None
    
    # Audit
    notes: Optional[str] = None
    created_by: str  # User creating the expense
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExpenseCreate(SQLModel):
    """Validation model for creating expenses"""
    category: ExpenseCategory
    description: str
    vendor_name: Optional[str] = None
    amount: float
    currency: str = "GHS"
    gl_account_id: Optional[str] = None
    gl_account_code: Optional[str] = None
    expense_date: datetime
    notes: Optional[str] = None


class ExpenseUpdate(SQLModel):
    """Validation model for updating expenses"""
    category: Optional[ExpenseCategory] = None
    description: Optional[str] = None
    vendor_name: Optional[str] = None
    amount: Optional[float] = None
    gl_account_id: Optional[str] = None
    gl_account_code: Optional[str] = None
    expense_date: Optional[datetime] = None
    notes: Optional[str] = None


class ExpenseSubmitRequest(SQLModel):
    """Request model for submitting expense for approval"""
    submission_notes: Optional[str] = None


class ExpenseApprovalRequest(SQLModel):
    """Request model for approving an expense"""
    approval_notes: Optional[str] = None


class ExpenseRejectionRequest(SQLModel):
    """Request model for rejecting an expense"""
    rejection_reason: str


class ExpensePaymentRequest(SQLModel):
    """Request model for recording expense payment"""
    amount_paid: float
    payment_date: datetime
    payment_notes: Optional[str] = None


class ExpenseResponse(SQLModel):
    """Response model for expense"""
    id: str
    school_id: str
    category: ExpenseCategory
    description: str
    vendor_name: Optional[str]
    amount: float
    currency: str
    gl_account_id: Optional[str]
    gl_account_code: Optional[str]
    expense_date: datetime
    status: ExpenseStatus
    payment_status: PaymentStatus
    amount_paid: float
    submitted_by: Optional[str]
    submitted_at: Optional[datetime]
    approved_by: Optional[str]
    approved_date: Optional[datetime]
    rejected_reason: Optional[str]
    journal_entry_id: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


# ==================== Summary & Analysis Models ====================

class ExpenseSummary(SQLModel):
    """Summary of expenses for analysis"""
    total_expenses: int
    draft_count: int
    pending_count: int
    approved_count: int
    posted_count: int
    rejected_count: int
    total_amount: float
    total_paid: float
    outstanding_amount: float
    by_category: dict  # {category: {count, total_amount, total_paid}}


class ExpenseByCategory(SQLModel):
    """Breakdown of expenses by category"""
    category: ExpenseCategory
    count: int
    total_amount: float
    total_paid: float
    outstanding_amount: float
    percentage_of_total: float
