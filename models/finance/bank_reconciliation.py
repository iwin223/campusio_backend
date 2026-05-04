"""Bank Reconciliation Models

Handles GL bank account reconciliation with bank statements.

Supports:
- Bank statement upload/import
- GL to bank matching
- Outstanding items tracking
- Reconciling differences
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class BankReconciliationStatus(str, Enum):
    """Status of a bank reconciliation"""
    IN_PROGRESS = "in_progress"      # Reconciliation being worked on
    COMPLETED = "completed"          # Reconciliation completed and balanced
    REJECTED = "rejected"            # Reconciliation rejected


class BankItemStatus(str, Enum):
    """Status of a bank transaction vs GL entry"""
    MATCHED = "matched"              # Item matched to GL entry
    UNMATCHED_BANK = "unmatched_bank"  # Bank item with no GL match (deposits in transit, etc.)
    UNMATCHED_GL = "unmatched_gl"    # GL entry with no bank match (outstanding checks, etc.)
    PENDING = "pending"              # Awaiting manual review
    CLEARED = "cleared"              # Item cleared and reconciled


class BankTransactionType(str, Enum):
    """Type of bank transaction"""
    DEPOSIT = "deposit"              # Money in
    WITHDRAWAL = "withdrawal"        # Money out
    CHECK = "check"                  # Check cleared
    FEE = "fee"                      # Bank fee
    INTEREST = "interest"            # Interest earned
    TRANSFER = "transfer"            # Transfer in/out


class BankReconciliation(SQLModel, table=True):
    """Bank Reconciliation - Header record for GL vs bank statement reconciliation
    
    Tracks the reconciliation process of a GL bank account with a bank statement.
    """
    __tablename__ = "bank_reconciliations"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Bank account identification
    gl_account_id: str = Field(index=True)  # GL bank account being reconciled
    
    # Statement details
    statement_date: datetime = Field(index=True)  # Date on bank statement
    statement_beginning_balance: float  # Starting balance on statement
    statement_ending_balance: float  # Ending balance on statement
    statement_currency: str = Field(default="USD")
    
    # GL account details at reconciliation
    gl_beginning_balance: float  # GL balance at start date
    gl_ending_balance: float  # GL balance at end date
    
    # Reconciliation details
    reconciliation_date: datetime = Field(index=True)  # When reconciliation done
    reconciliation_status: BankReconciliationStatus = Field(default=BankReconciliationStatus.IN_PROGRESS)
    
    # Matched/unmatched summary
    total_bank_transactions: int = 0  # Total items on bank statement
    matched_transactions: int = 0  # Items matched to GL entries
    unmatched_bank_items: int = 0  # Bank items with no GL match
    unmatched_gl_items: int = 0  # GL items with no bank match
    
    # Variance/differences
    variance_amount: float = 0.0  # Difference between GL and bank (should be 0)
    variance_reason: Optional[str] = None  # Explanation of variance if not zero
    
    # Audit
    reconciled_by: str  # User who reconciled
    approved_by: Optional[str] = None  # User who approved
    approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_date: Optional[datetime] = None
    rejected_by: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BankStatement(SQLModel, table=True):
    """Bank Statement - List of transactions from bank
    
    Represents a bank statement import with individual transactions.
    """
    __tablename__ = "bank_statements"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Statement identification
    bank_reconciliation_id: str = Field(index=True)  # FK to BankReconciliation
    statement_line_number: int = Field(index=True)  # Line number on statement
    
    # Transaction details
    transaction_date: datetime = Field(index=True)
    transaction_type: BankTransactionType
    description: str  # Bank description (check #, deposit, etc.)
    amount: float  # Amount (positive for deposits, negative for withdrawals)
    running_balance: Optional[float] = None  # Running balance on statement
    
    # Clearing status
    is_cleared: bool = Field(default=False)  # Has cleared GL
    cleared_date: Optional[datetime] = None
    
    # Audit
    bank_reference: Optional[str] = None  # Bank's transaction reference
    imported_at: datetime = Field(default_factory=datetime.utcnow)
    imported_by: str  # User who imported statement


class BankReconciliationMatch(SQLModel, table=True):
    """Bank Reconciliation Match - Links bank transaction to GL entry
    
    Represents the matching of a bank statement item to a GL journal entry.
    """
    __tablename__ = "bank_reconciliation_matches"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    bank_reconciliation_id: str = Field(index=True)  # FK to BankReconciliation
    bank_statement_id: str = Field(index=True)  # FK to BankStatement
    journal_entry_id: Optional[str] = None  # FK to JournalEntry (if matched)
    
    # Match details
    match_status: BankItemStatus = Field(index=True)
    match_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Bank item amount
    bank_amount: float
    bank_date: datetime
    bank_description: str
    
    # GL item amount (if matched)
    gl_amount: Optional[float] = None
    gl_date: Optional[datetime] = None
    gl_description: Optional[str] = None
    
    # Variance if amounts don't match exactly
    variance_amount: float = 0.0  # Difference (bank_amount - gl_amount)
    variance_reason: Optional[str] = None  # Why amounts differ
    
    # Days variance (for timing differences)
    days_variance: Optional[int] = None  # bank_date - gl_date
    
    # Manual review if needed
    requires_review: bool = Field(default=False)
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_date: Optional[datetime] = None
    
    # Audit
    matched_by: str  # User who matched
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BankReconciliationAdjustment(SQLModel, table=True):
    """Bank Reconciliation Adjustment - GL entry created to reconcile difference
    
    When bank reconciliation shows a difference (e.g., bank fees, interest),
    create a GL adjustment entry to correct GL balance.
    """
    __tablename__ = "bank_reconciliation_adjustments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    bank_reconciliation_id: str = Field(index=True)  # FK to BankReconciliation
    journal_entry_id: Optional[str] = None  # FK to JournalEntry created for adjustment
    
    # Adjustment details
    description: str  # Reason for adjustment (bank fee, interest, etc.)
    amount: float  # Amount to adjust
    adjustment_type: str  # Type: BANK_FEE, INTEREST, SERVICE_CHARGE, OTHER
    
    # Status
    is_posted: bool = Field(default=False)  # Has been posted to GL
    posted_date: Optional[datetime] = None
    posted_by: Optional[str] = None
    
    # Audit
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Request/Response Models ====================

class BankStatementCreate(SQLModel):
    """Validation model for creating bank statement items"""
    transaction_date: datetime
    transaction_type: BankTransactionType
    description: str
    amount: float
    running_balance: Optional[float] = None
    bank_reference: Optional[str] = None


class BankReconciliationCreate(SQLModel):
    """Validation model for creating bank reconciliation"""
    gl_account_id: str
    statement_date: datetime
    statement_beginning_balance: float
    statement_ending_balance: float
    reconciled_by: str
    notes: Optional[str] = None


class BankReconciliationResponse(SQLModel):
    """Response model for bank reconciliation"""
    id: str
    gl_account_id: str
    statement_date: datetime
    statement_beginning_balance: float
    statement_ending_balance: float
    gl_beginning_balance: float
    gl_ending_balance: float
    reconciliation_date: datetime
    reconciliation_status: BankReconciliationStatus
    matched_transactions: int
    unmatched_bank_items: int
    unmatched_gl_items: int
    variance_amount: float
    reconciled_by: str


class BankReconciliationMatchResponse(SQLModel):
    """Response model for a match"""
    id: str
    match_status: BankItemStatus
    bank_amount: float
    bank_date: datetime
    gl_amount: Optional[float]
    gl_date: Optional[datetime]
    variance_amount: float
    days_variance: Optional[int]
