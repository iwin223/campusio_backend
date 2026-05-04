"""Sub-Ledger Reconciliation Models

Handles reconciliation of detail accounts (AR, AP, Hostel Deposits) 
to their GL control accounts.

Supports:
- Detail account to control account matching
- Aging analysis
- Variance detection
- Reconciliation of individual records
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class SubLedgerType(str, Enum):
    """Type of sub-ledger"""
    ACCOUNTS_RECEIVABLE = "accounts_receivable"  # Student/customer invoices
    ACCOUNTS_PAYABLE = "accounts_payable"        # Vendor invoices
    HOSTEL_DEPOSITS = "hostel_deposits"          # Student hostel security deposits
    EMPLOYEE_ADVANCES = "employee_advances"      # Employee loan advances
    OTHER = "other"


class SubLedgerStatus(str, Enum):
    """Status of sub-ledger reconciliation"""
    IN_PROGRESS = "in_progress"      # Reconciliation being worked on
    COMPLETED = "completed"          # Reconciliation complete and balanced
    REJECTED = "rejected"            # Reconciliation rejected


class DetailItemStatus(str, Enum):
    """Status of a detail item vs control account"""
    MATCHED = "matched"              # Matched to GL posting
    UNMATCHED = "unmatched"          # No GL posting found
    VARIANCE = "variance"            # GL posting exists but amount differs
    PENDING = "pending"              # Awaiting review


class AgeingBucket(str, Enum):
    """Ageing buckets for detail items"""
    CURRENT = "current"              # 0-30 days
    THIRTY_TO_SIXTY = "30_to_60"     # 30-60 days
    SIXTY_TO_NINETY = "60_to_90"     # 60-90 days
    OVER_NINETY = "over_90"          # 90+ days


class SubLedgerReconciliation(SQLModel, table=True):
    """Sub-Ledger Reconciliation - Header for detail to control account reconciliation
    
    Reconciles detail accounts (e.g., individual student AR accounts) to their
    GL control account (e.g., Accounts Receivable control GL account).
    """
    __tablename__ = "subledger_reconciliations"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Sub-ledger identification
    subledger_type: SubLedgerType = Field(index=True)
    control_account_id: str = Field(index=True)  # GL control account
    
    # Reconciliation details
    reconciliation_date: datetime = Field(index=True)
    reconciliation_status: SubLedgerStatus = Field(default=SubLedgerStatus.IN_PROGRESS)
    
    # Detail account summary
    total_detail_records: int = 0  # Total detail account records
    detail_total_balance: float = 0.0  # Sum of all detail record balances
    
    # GL control account details
    gl_control_balance: float = 0.0  # Balance in GL control account
    
    # Reconciliation matching
    matched_records: int = 0  # Records matched to GL
    unmatched_records: int = 0  # Detail records with no GL match
    variance_records: int = 0  # Records with GL amount mismatch
    
    # Variance/differences
    total_variance: float = 0.0  # Difference (detail - GL)
    variance_reason: Optional[str] = None
    
    # Aging summary (for AR/AP)
    current_balance: float = 0.0  # 0-30 days
    thirty_to_sixty_balance: float = 0.0  # 30-60 days
    sixty_to_ninety_balance: float = 0.0  # 60-90 days
    over_ninety_balance: float = 0.0  # 90+ days
    
    # Audit
    reconciled_by: str
    approved_by: Optional[str] = None
    approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_date: Optional[datetime] = None
    rejected_by: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SubLedgerDetail(SQLModel, table=True):
    """Sub-Ledger Detail - Individual record in sub-ledger
    
    Represents a single detail account record (e.g., a student's AR balance).
    """
    __tablename__ = "subledger_details"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    subledger_reconciliation_id: str = Field(index=True)  # FK to SubLedgerReconciliation
    detail_reference_id: str = Field(index=True)  # ID of detail record (e.g., student_id, vendor_id)
    reference_type: str  # Type of reference (STUDENT, VENDOR, EMPLOYEE, etc.)
    
    # Detail record info
    detail_description: str  # Description (e.g., student name, vendor name)
    detail_balance: float  # Balance of this detail record
    
    # Last transaction date (for aging)
    last_transaction_date: datetime = Field(index=True)
    
    # GL posting references (if matched)
    journal_entry_id: Optional[str] = None  # FK to JournalEntry that posted this
    gl_posted_date: Optional[datetime] = None
    gl_posted_amount: Optional[float] = None
    
    # Matching status
    match_status: DetailItemStatus = Field(index=True)
    
    # If variance, track difference
    variance_amount: float = 0.0  # detail_balance - gl_posted_amount
    variance_reason: Optional[str] = None
    
    # Aging bucket (calculated from last_transaction_date)
    aging_bucket: Optional[AgeingBucket] = None
    days_outstanding: int = 0  # Number of days since last transaction
    
    # Audit
    matched_by: str  # User who matched/reviewed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SubLedgerMatch(SQLModel, table=True):
    """Sub-Ledger Match - Links detail record to GL posting
    
    Represents the matching of a sub-ledger detail record to GL postings.
    """
    __tablename__ = "subledger_matches"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    subledger_reconciliation_id: str = Field(index=True)
    subledger_detail_id: str = Field(index=True)  # FK to SubLedgerDetail
    journal_entry_id: str = Field(index=True)  # FK to JournalEntry
    
    # Match details
    detail_amount: float  # Amount on detail record
    gl_amount: float  # Amount posted to GL
    variance_amount: float = 0.0  # Difference
    
    # Dates
    detail_date: datetime
    gl_date: datetime
    days_variance: int = 0  # gl_date - detail_date
    
    # Match quality
    is_exact_match: bool = False  # Amount matches exactly
    requires_review: bool = False  # Needs manual review
    review_notes: Optional[str] = None
    
    # Audit
    matched_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SubLedgerAdjustment(SQLModel, table=True):
    """Sub-Ledger Adjustment - GL adjustment entry for unmatched items
    
    When sub-ledger reconciliation finds unmatched items, create GL adjustment
    entries to correct the GL control account balance.
    """
    __tablename__ = "subledger_adjustments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    subledger_reconciliation_id: str = Field(index=True)
    subledger_detail_id: Optional[str] = None  # FK to detail record being adjusted
    journal_entry_id: Optional[str] = None  # FK to JournalEntry created for adjustment
    
    # Adjustment details
    description: str  # Reason for adjustment
    adjustment_amount: float  # Amount to adjust
    
    # Status
    is_posted: bool = Field(default=False)
    posted_date: Optional[datetime] = None
    posted_by: Optional[str] = None
    
    # Audit
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Request/Response Models ====================

class SubLedgerDetailCreate(SQLModel):
    """Validation model for creating sub-ledger detail records"""
    detail_reference_id: str
    reference_type: str
    detail_description: str
    detail_balance: float
    last_transaction_date: datetime


class SubLedgerReconciliationCreate(SQLModel):
    """Validation model for creating sub-ledger reconciliation"""
    subledger_type: SubLedgerType
    control_account_id: str
    reconciled_by: str
    notes: Optional[str] = None


class SubLedgerReconciliationResponse(SQLModel):
    """Response model for sub-ledger reconciliation"""
    id: str
    subledger_type: SubLedgerType
    control_account_id: str
    reconciliation_date: datetime
    reconciliation_status: SubLedgerStatus
    detail_total_balance: float
    gl_control_balance: float
    total_variance: float
    matched_records: int
    unmatched_records: int
    variance_records: int


class SubLedgerDetailResponse(SQLModel):
    """Response model for sub-ledger detail"""
    id: str
    detail_reference_id: str
    reference_type: str
    detail_description: str
    detail_balance: float
    match_status: DetailItemStatus
    variance_amount: float
    aging_bucket: Optional[AgeingBucket]
    days_outstanding: int


class AgingReportResponse(SQLModel):
    """Response model for aging report"""
    subledger_type: SubLedgerType
    current_balance: float  # 0-30 days
    thirty_to_sixty_balance: float
    sixty_to_ninety_balance: float
    over_ninety_balance: float
    total_balance: float
    total_records: int
