"""Chart of Accounts models for general ledger management"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class AccountType(str, Enum):
    """Primary account classification for balance sheet and income statement"""
    ASSET = "asset"              # Bank, accounts receivable, inventory
    LIABILITY = "liability"       # Accounts payable, salaries payable
    EQUITY = "equity"             # Accumulated surplus/deficit
    REVENUE = "revenue"           # Income streams (tuition, donations)
    EXPENSE = "expense"           # Costs (salaries, utilities, supplies)


class AccountCategory(str, Enum):
    """Subcategories for better reporting and organization"""
    # Assets
    BANK_ACCOUNTS = "bank_accounts"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    PREPAID_EXPENSES = "prepaid_expenses"
    FIXED_ASSETS = "fixed_assets"
    
    # Liabilities
    ACCOUNTS_PAYABLE = "accounts_payable"
    SALARIES_PAYABLE = "salaries_payable"
    SHORT_TERM_DEBT = "short_term_debt"
    LONG_TERM_DEBT = "long_term_debt"
    
    # Equity
    ACCUMULATED_SURPLUS = "accumulated_surplus"
    RETAINED_EARNINGS = "retained_earnings"
    
    # Revenue
    STUDENT_FEES = "student_fees"
    DONATIONS = "donations"
    GRANTS = "grants"
    OTHER_INCOME = "other_income"
    
    # Expense
    SALARIES_WAGES = "salaries_wages"
    UTILITIES = "utilities"
    SUPPLIES = "supplies"
    REPAIRS_MAINTENANCE = "repairs_maintenance"
    TRANSPORT_COSTS = "transport_costs"
    CONTRACTED_SERVICES = "contracted_services"
    DEPRECIATION = "depreciation"
    OTHER_EXPENSES = "other_expenses"


class GLAccount(SQLModel, table=True):
    """General Ledger Account - fundamental accounting record
    
    Each account represents a specific financial item that can be debited or credited.
    Accounts must follow accounting equation: Assets = Liabilities + Equity
    And: Revenue - Expenses = Net Income
    
    The chart of accounts is hierarchical to support sub-ledgers.
    """
    __tablename__ = "gl_accounts"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Identification
    account_code: str = Field(index=True)  # e.g., "1010", "5100", "4000" - Unique per school
    account_name: str                      # e.g., "Business Checking Account"
    
    # Classification
    account_type: AccountType = Field(index=True)
    account_category: AccountCategory
    
    # Details
    description: Optional[str] = None
    normal_balance: str = Field(default="debit")  # "debit" or "credit" - which side increases the balance
    
    # Hierarchy (for sub-ledgers and reporting structure)
    parent_account_id: Optional[str] = None  # For creating hierarchical account structures
    
    # Status
    is_active: bool = Field(default=True, index=True)
    
    # ⭐ BALANCE TRACKING (CRITICAL FOR PERFORMANCE & ACCURACY)
    current_balance: float = Field(default=0.0)  # Denormalized balance for performance
    opening_balance: float = Field(default=0.0)  # Period opening balance (for comparisons)
    bank_reconciled_balance: Optional[float] = None  # Last reconciled balance
    last_balance_update: datetime = Field(default_factory=datetime.utcnow)  # When balance was last updated
    bank_reconciliation_date: Optional[datetime] = None  # When last reconciled to bank
    reconciliation_notes: Optional[str] = None  # Notes on bank reconciliation
    
    # Tracking
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """Ensure unique account codes per school"""
        # Note: Index created via migration for (school_id, account_code) composite key
        pass


class GLAccountCreate(SQLModel):
    """Validation model for creating GL accounts"""
    account_code: str
    account_name: str
    account_type: AccountType
    account_category: AccountCategory
    description: Optional[str] = None
    normal_balance: str = "debit"
    parent_account_id: Optional[str] = None


class GLAccountUpdate(SQLModel):
    """Validation model for updating GL accounts"""
    account_name: Optional[str] = None
    account_category: Optional[AccountCategory] = None
    description: Optional[str] = None
    normal_balance: Optional[str] = None
    is_active: Optional[bool] = None


class GLAccountResponse(SQLModel):
    """Response model for GL account queries"""
    id: str
    school_id: str
    account_code: str
    account_name: str
    account_type: AccountType
    account_category: AccountCategory
    description: Optional[str]
    normal_balance: str
    parent_account_id: Optional[str]
    is_active: bool
    # ⭐ BALANCE FIELDS (NEW)
    current_balance: float
    opening_balance: float
    bank_reconciled_balance: Optional[float]
    last_balance_update: datetime
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
