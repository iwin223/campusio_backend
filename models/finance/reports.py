"""Financial Reports Models - Data structures for financial statement generation

Report Types:
1. Trial Balance - Lists all GL accounts with debit/credit balances (debits must equal credits)
2. Balance Sheet - Shows Assets = Liabilities + Equity as of a date
3. Profit & Loss Statement - Shows Revenue - Expenses = Net Income for a period
4. Cash Flow Statement - Shows movement of cash (Operating, Investing, Financing activities)

All reports are read-only and generated from journal entries for the specified period.
"""
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field
from sqlmodel import SQLModel


class ReportPeriodType(str, Enum):
    """Type of reporting period"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    CUSTOM = "custom"


# ==================== Trial Balance Report ====================

class TrialBalanceLineItem(SQLModel):
    """Single line in trial balance report"""
    account_code: str = Field(description="GL account code (e.g., 1010)")
    account_name: str = Field(description="GL account name (e.g., Business Checking Account)")
    account_type: str = Field(description="Account type (asset, liability, equity, revenue, expense)")
    normal_balance: str = Field(description="Normal balance direction (debit or credit)")
    
    debit_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Total debits for period")
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Total credits for period")
    balance: Decimal = Field(description="Net balance (debit or credit depending on account type)")
    
    opening_balance: Optional[Decimal] = Field(default=None, description="Balance at start of period")
    closing_balance: Decimal = Field(description="Balance at end of period")


class TrialBalanceReport(SQLModel):
    """Trial Balance - All accounts with balances at a point in time
    
    Purpose: Verify that debits = credits (ensures posting accuracy)
    
    Properties:
    - total_debits: Sum of all debit balances
    - total_credits: Sum of all credit balances
    - difference: Should be 0 if balanced
    - is_balanced: True if total_debits == total_credits
    """
    school_id: str = Field(description="School identifier")
    as_of_date: datetime = Field(description="Report date")
    
    line_items: List[TrialBalanceLineItem] = Field(default=[], description="All accounts with balances")
    
    total_debits: Decimal = Field(default=Decimal("0"), description="Sum of all debit balances")
    total_credits: Decimal = Field(default=Decimal("0"), description="Sum of all credit balances")
    difference: Decimal = Field(default=Decimal("0"), description="Difference (0 if balanced)")
    is_balanced: bool = Field(default=True, description="True if total_debits == total_credits")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")
    period_type: ReportPeriodType = Field(default=ReportPeriodType.CUSTOM)


# ==================== Balance Sheet Report ====================

class BalanceSheetSectionItem(SQLModel):
    """Item within a balance sheet section (assets, liabilities, equity)"""
    account_code: str = Field(description="GL account code")
    account_name: str = Field(description="GL account name")
    amount: Decimal = Field(ge=0, description="Amount for this account")


class BalanceSheetSection(SQLModel):
    """A major section of the balance sheet"""
    section_name: str = Field(description="Section name (Assets, Liabilities, Equity)")
    section_type: str = Field(description="Type: assets, liabilities, equity")
    
    items: List[BalanceSheetSectionItem] = Field(default=[], description="Accounts in this section")
    section_total: Decimal = Field(default=Decimal("0"), description="Total for this section")


class BalanceSheetReport(SQLModel):
    """Balance Sheet - Assets = Liabilities + Equity
    
    Shows the financial position at a point in time.
    
    Structure:
    ASSETS
      Current Assets
      Fixed Assets
      Other Assets
    Total Assets = X
    
    LIABILITIES
      Current Liabilities
      Long-term Liabilities
    Total Liabilities = Y
    
    EQUITY
      Capital
      Retained Earnings
    Total Equity = Z
    
    Verify: Total Assets = Total Liabilities + Total Equity
    """
    school_id: str = Field(description="School identifier")
    as_of_date: datetime = Field(description="Report date")
    
    assets: BalanceSheetSection = Field(description="Asset section")
    liabilities: BalanceSheetSection = Field(description="Liability section")
    equity: BalanceSheetSection = Field(description="Equity section")
    
    total_assets: Decimal = Field(default=Decimal("0"), description="Total assets")
    total_liabilities: Decimal = Field(default=Decimal("0"), description="Total liabilities")
    total_equity: Decimal = Field(default=Decimal("0"), description="Total equity")
    
    is_balanced: bool = Field(default=True, description="True if Assets = Liabilities + Equity")
    balance_difference: Decimal = Field(default=Decimal("0"), description="Difference (0 if balanced)")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")


# ==================== Profit & Loss Report ====================

class ProfitLossSection(SQLModel):
    """Section of P&L statement (Revenue, Expenses, etc.)"""
    section_name: str = Field(description="Section name (Revenue, Expenses, etc.)")
    section_type: str = Field(description="Type: revenue, cost_of_goods, operating_expenses, other")
    
    items: List[BalanceSheetSectionItem] = Field(default=[], description="Accounts in section")
    section_total: Decimal = Field(default=Decimal("0"), description="Total for section")


class ProfitLossReport(SQLModel):
    """Profit & Loss Statement (Income Statement) for a period
    
    Shows Revenue - Expenses = Net Income
    
    Structure:
    REVENUE
      Tuition Fees (4100)
      Exam Fees (4110)
      Sports Fees (4120)
      ...
    Total Revenue = A
    
    OPERATING EXPENSES
      Salaries (5100)
      Utilities (6100)
      Supplies (6200)
      ...
    Total Operating Expenses = B
    
    OTHER INCOME/EXPENSES
      Interest Income (4500)
      Interest Expense (6500)
    Total Other = C
    
    Net Income = A - B + C
    """
    school_id: str = Field(description="School identifier")
    period_start_date: datetime = Field(description="Period start date")
    period_end_date: datetime = Field(description="Period end date")
    
    revenue_section: ProfitLossSection = Field(description="Revenue accounts")
    operating_expenses_section: ProfitLossSection = Field(description="Operating expense accounts")
    other_income_section: Optional[ProfitLossSection] = Field(default=None, description="Other income accounts")
    other_expenses_section: Optional[ProfitLossSection] = Field(default=None, description="Other expense accounts")
    
    total_revenue: Decimal = Field(default=Decimal("0"), description="Total revenue for period")
    total_operating_expenses: Decimal = Field(default=Decimal("0"), description="Total operating expenses")
    operating_income: Decimal = Field(default=Decimal("0"), description="Revenue - Operating Expenses")
    
    total_other_income: Decimal = Field(default=Decimal("0"), description="Total other income")
    total_other_expenses: Decimal = Field(default=Decimal("0"), description="Total other expenses")
    
    net_income: Decimal = Field(default=Decimal("0"), description="Bottom line: Revenue - Expenses")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")


# ==================== Cash Flow Report ====================

class CashFlowActivityItem(SQLModel):
    """Item within a cash flow activity section"""
    description: str = Field(description="Activity description")
    amount: Decimal = Field(description="Cash impact (positive or negative)")


class CashFlowActivity(SQLModel):
    """Activity section in cash flow (Operating, Investing, Financing)"""
    activity_type: str = Field(description="Type: operating, investing, financing")
    activity_name: str = Field(description="Name: Operating Activities, Investing Activities, etc.")
    
    items: List[CashFlowActivityItem] = Field(default=[], description="Activities in this section")
    activity_subtotal: Decimal = Field(default=Decimal("0"), description="Subtotal for this activity")


class CashFlowReport(SQLModel):
    """Cash Flow Statement - Shows movement of cash for a period
    
    Structure:
    OPERATING ACTIVITIES
      Net Income: X
      Add: Depreciation: Y
      Changes in Working Capital: Z
    Cash from Operations = A
    
    INVESTING ACTIVITIES
      Purchase of Equipment: -B
      Sale of Assets: C
    Cash from Investing = D
    
    FINANCING ACTIVITIES
      Borrowing: E
      Loan Repayment: -F
      Owner Contribution: G
    Cash from Financing = H
    
    Net Change in Cash = A + D + H
    Beginning Cash Balance = I
    Ending Cash Balance = I + (A + D + H)
    """
    school_id: str = Field(description="School identifier")
    period_start_date: datetime = Field(description="Period start date")
    period_end_date: datetime = Field(description="Period end date")
    
    operating_activities: CashFlowActivity = Field(description="Operating activities section")
    investing_activities: Optional[CashFlowActivity] = Field(default=None, description="Investing activities")
    financing_activities: Optional[CashFlowActivity] = Field(default=None, description="Financing activities")
    
    cash_from_operations: Decimal = Field(default=Decimal("0"), description="Net cash from operations")
    cash_from_investing: Decimal = Field(default=Decimal("0"), description="Net cash from investing")
    cash_from_financing: Decimal = Field(default=Decimal("0"), description="Net cash from financing")
    
    net_change_in_cash: Decimal = Field(default=Decimal("0"), description="Total change in cash")
    beginning_cash_balance: Decimal = Field(default=Decimal("0"), description="Opening cash balance")
    ending_cash_balance: Decimal = Field(default=Decimal("0"), description="Closing cash balance")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")


# ==================== Request Models ====================

class ReportDateRangeRequest(SQLModel):
    """Request for reports requiring a date range"""
    start_date: datetime = Field(description="Period start date")
    end_date: datetime = Field(description="Period end date")
    period_type: Optional[ReportPeriodType] = Field(default=ReportPeriodType.CUSTOM, description="Period classification")


class ReportAsOfDateRequest(SQLModel):
    """Request for reports as of a specific date (Balance Sheet, Trial Balance)"""
    as_of_date: datetime = Field(description="Report date")
    period_type: Optional[ReportPeriodType] = Field(default=ReportPeriodType.CUSTOM, description="Period classification")
