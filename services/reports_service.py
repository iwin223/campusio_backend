"""Financial Reports Service - Generate standard financial statements from GL data

Generates four key financial reports:
1. Trial Balance - Verification that debits = credits
2. Balance Sheet - Financial position at a point in time
3. Profit & Loss Statement - Income for a period
4. Cash Flow Statement - Cash movement for a period

All reports query GL accounts and journal entries posted within the specified period.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from decimal import Decimal
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.finance import (
    GLAccount,
    JournalEntry,
    JournalLineItem,
    PostingStatus,
    AccountType,
    AccountCategory,
)
from models.finance.reports import (
    TrialBalanceReport,
    TrialBalanceLineItem,
    BalanceSheetReport,
    BalanceSheetSection,
    BalanceSheetSectionItem,
    ProfitLossReport,
    ProfitLossSection,
    CashFlowReport,
    CashFlowActivity,
    CashFlowActivityItem,
)

logger = logging.getLogger(__name__)


class ReportsServiceError(Exception):
    """Base exception for reports service"""
    pass


class ReportsValidationError(ReportsServiceError):
    """Validation error in reports service"""
    pass


class ReportsService:
    """Service for generating financial reports from GL data"""
    
    def __init__(self, session: AsyncSession):
        """Initialize reports service with database session
        
        Args:
            session: AsyncSession for database queries
        """
        self.session = session
    
    # ==================== Trial Balance Report ====================
    
    async def generate_trial_balance(
        self,
        school_id: str,
        as_of_date: datetime,
    ) -> TrialBalanceReport:
        """Generate Trial Balance report
        
        Lists all GL accounts with their debit and credit balances as of a specific date.
        Debits must equal credits (if balanced, posting was correct).
        
        Args:
            school_id: School identifier
            as_of_date: Report date (all postings up to this date)
        
        Returns:
            TrialBalanceReport with all accounts and verification
        
        Raises:
            ReportsServiceError: If GL query fails
        """
        try:
            # Get all active GL accounts for school
            query = select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.is_active == True,
                )
            )
            result = await self.session.execute(query)
            accounts = result.scalars().all()
            
            line_items: List[TrialBalanceLineItem] = []
            total_debits = Decimal("0")
            total_credits = Decimal("0")
            
            # For each account, calculate balance from journal entries
            for account in accounts:
                # Get all posted journal entries for this account before as_of_date
                line_query = select(func.sum(JournalLineItem.debit_amount).label("total_debits"),
                                   func.sum(JournalLineItem.credit_amount).label("total_credits")
                                   ).join(JournalEntry, JournalLineItem.journal_entry_id == JournalEntry.id).where(
                    and_(
                        JournalLineItem.gl_account_id == account.id,
                        JournalEntry.school_id == school_id,
                        JournalEntry.posting_status == PostingStatus.POSTED,
                        JournalEntry.entry_date <= as_of_date,
                    )
                )
                line_result = await self.session.execute(line_query)
                row = line_result.first()
                
                debit_total = Decimal(str(row.total_debits)) if row.total_debits else Decimal("0")
                credit_total = Decimal(str(row.total_credits)) if row.total_credits else Decimal("0")
                
                # Calculate balance based on normal_balance direction
                if account.normal_balance == "debit":
                    balance = debit_total - credit_total
                else:  # credit
                    balance = credit_total - debit_total
                
                total_debits += debit_total
                total_credits += credit_total
                
                # Only include accounts with activity or non-zero balance
                if debit_total > 0 or credit_total > 0 or balance != 0:
                    line_items.append(
                        TrialBalanceLineItem(
                            account_code=account.account_code,
                            account_name=account.account_name,
                            account_type=account.account_type.value,
                            normal_balance=account.normal_balance,
                            debit_amount=debit_total,
                            credit_amount=credit_total,
                            balance=balance,
                            opening_balance=Decimal("0"),  # Could be calculated from prior periods
                            closing_balance=balance,
                        )
                    )
            
            # Verify balance
            difference = total_debits - total_credits
            is_balanced = difference == Decimal("0")
            
            if not is_balanced:
                logger.warning(
                    f"Trial balance not balanced for school {school_id} as of {as_of_date}: "
                    f"difference = {difference}"
                )
            
            return TrialBalanceReport(
                school_id=school_id,
                as_of_date=as_of_date,
                line_items=sorted(line_items, key=lambda x: x.account_code),
                total_debits=total_debits,
                total_credits=total_credits,
                difference=difference,
                is_balanced=is_balanced,
            )
            
        except Exception as e:
            logger.error(f"Error generating trial balance: {str(e)}")
            raise ReportsServiceError(f"Failed to generate trial balance: {str(e)}")
    
    # ==================== Balance Sheet Report ====================
    
    async def generate_balance_sheet(
        self,
        school_id: str,
        as_of_date: datetime,
    ) -> BalanceSheetReport:
        """Generate Balance Sheet report
        
        Shows financial position: Assets = Liabilities + Equity
        
        Args:
            school_id: School identifier
            as_of_date: Report date
        
        Returns:
            BalanceSheetReport with sections and verification
        """
        try:
            # Get account balances using same logic as trial balance
            trial_balance = await self.generate_trial_balance(school_id, as_of_date)
            
            # Organize accounts into balance sheet sections
            assets_items: List[BalanceSheetSectionItem] = []
            liabilities_items: List[BalanceSheetSectionItem] = []
            equity_items: List[BalanceSheetSectionItem] = []
            
            total_assets = Decimal("0")
            total_liabilities = Decimal("0")
            total_equity = Decimal("0")
            
            for line in trial_balance.line_items:
                item = BalanceSheetSectionItem(
                    account_code=line.account_code,
                    account_name=line.account_name,
                    amount=abs(line.balance),  # Use absolute value for display
                )
                
                if line.account_type == AccountType.ASSET.value:
                    assets_items.append(item)
                    total_assets += abs(line.balance)
                elif line.account_type == AccountType.LIABILITY.value:
                    liabilities_items.append(item)
                    total_liabilities += abs(line.balance)
                elif line.account_type == AccountType.EQUITY.value:
                    equity_items.append(item)
                    total_equity += abs(line.balance)
            
            # Verify balance sheet equation
            balance_difference = total_assets - (total_liabilities + total_equity)
            is_balanced = balance_difference == Decimal("0")
            
            if not is_balanced:
                logger.warning(
                    f"Balance sheet not balanced for school {school_id} as of {as_of_date}: "
                    f"Assets ({total_assets}) != Liabilities ({total_liabilities}) + Equity ({total_equity})"
                )
            
            return BalanceSheetReport(
                school_id=school_id,
                as_of_date=as_of_date,
                assets=BalanceSheetSection(
                    section_name="Assets",
                    section_type="assets",
                    items=sorted(assets_items, key=lambda x: x.account_code),
                    section_total=total_assets,
                ),
                liabilities=BalanceSheetSection(
                    section_name="Liabilities",
                    section_type="liabilities",
                    items=sorted(liabilities_items, key=lambda x: x.account_code),
                    section_total=total_liabilities,
                ),
                equity=BalanceSheetSection(
                    section_name="Equity",
                    section_type="equity",
                    items=sorted(equity_items, key=lambda x: x.account_code),
                    section_total=total_equity,
                ),
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
                is_balanced=is_balanced,
                balance_difference=balance_difference,
            )
            
        except ReportsServiceError:
            raise
        except Exception as e:
            logger.error(f"Error generating balance sheet: {str(e)}")
            raise ReportsServiceError(f"Failed to generate balance sheet: {str(e)}")
    
    # ==================== Profit & Loss Report ====================
    
    async def generate_profit_loss(
        self,
        school_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> ProfitLossReport:
        """Generate Profit & Loss Statement (Income Statement)
        
        Shows: Revenue - Expenses = Net Income for the period
        
        Args:
            school_id: School identifier
            start_date: Period start date
            end_date: Period end date
        
        Returns:
            ProfitLossReport with revenue and expenses
        """
        try:
            # Get all active GL accounts
            query = select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.is_active == True,
                    GLAccount.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE]),
                )
            )
            result = await self.session.execute(query)
            accounts = result.scalars().all()
            
            revenue_items: List[BalanceSheetSectionItem] = []
            operating_expense_items: List[BalanceSheetSectionItem] = []
            other_income_items: List[BalanceSheetSectionItem] = []
            other_expense_items: List[BalanceSheetSectionItem] = []
            
            total_revenue = Decimal("0")
            total_operating_expenses = Decimal("0")
            total_other_income = Decimal("0")
            total_other_expenses = Decimal("0")
            
            # Calculate balance for each revenue/expense account in period
            for account in accounts:
                line_query = select(func.sum(JournalLineItem.debit_amount).label("total_debits"),
                                   func.sum(JournalLineItem.credit_amount).label("total_credits")
                                   ).join(JournalEntry, JournalLineItem.journal_entry_id == JournalEntry.id).where(
                    and_(
                        JournalLineItem.gl_account_id == account.id,
                        JournalEntry.school_id == school_id,
                        JournalEntry.posting_status == PostingStatus.POSTED,
                        JournalEntry.entry_date >= start_date,
                        JournalEntry.entry_date <= end_date,
                    )
                )
                line_result = await self.session.execute(line_query)
                row = line_result.first()
                
                debit_total = Decimal(str(row.total_debits)) if row.total_debits else Decimal("0")
                credit_total = Decimal(str(row.total_credits)) if row.total_credits else Decimal("0")
                
                # Revenue accounts normally credit, so amount = credit_total
                # Expense accounts normally debit, so amount = debit_total
                if account.account_type == AccountType.REVENUE:
                    amount = credit_total
                else:  # EXPENSE
                    amount = debit_total
                
                if amount > 0:
                    item = BalanceSheetSectionItem(
                        account_code=account.account_code,
                        account_name=account.account_name,
                        amount=amount,
                    )
                    
                    # Categorize based on account category
                    if account.account_type == AccountType.REVENUE:
                        revenue_items.append(item)
                        total_revenue += amount
                    else:  # EXPENSE
                        # Check if other (usually 6400+)
                        if account.account_code.startswith(("64", "65")) or account.account_category in ["interest_expense", "other_expense"]:
                            other_expense_items.append(item)
                            total_other_expenses += amount
                        else:
                            operating_expense_items.append(item)
                            total_operating_expenses += amount
            
            operating_income = total_revenue - total_operating_expenses
            net_income = operating_income + (total_other_income - total_other_expenses)
            
            return ProfitLossReport(
                school_id=school_id,
                period_start_date=start_date,
                period_end_date=end_date,
                revenue_section=ProfitLossSection(
                    section_name="Revenue",
                    section_type="revenue",
                    items=sorted(revenue_items, key=lambda x: x.account_code),
                    section_total=total_revenue,
                ),
                operating_expenses_section=ProfitLossSection(
                    section_name="Operating Expenses",
                    section_type="operating_expenses",
                    items=sorted(operating_expense_items, key=lambda x: x.account_code),
                    section_total=total_operating_expenses,
                ),
                other_income_section=ProfitLossSection(
                    section_name="Other Income",
                    section_type="other_income",
                    items=sorted(other_income_items, key=lambda x: x.account_code),
                    section_total=total_other_income,
                ) if other_income_items else None,
                other_expenses_section=ProfitLossSection(
                    section_name="Other Expenses",
                    section_type="other_expenses",
                    items=sorted(other_expense_items, key=lambda x: x.account_code),
                    section_total=total_other_expenses,
                ) if other_expense_items else None,
                total_revenue=total_revenue,
                total_operating_expenses=total_operating_expenses,
                operating_income=operating_income,
                total_other_income=total_other_income,
                total_other_expenses=total_other_expenses,
                net_income=net_income,
            )
            
        except Exception as e:
            logger.error(f"Error generating P&L: {str(e)}")
            raise ReportsServiceError(f"Failed to generate P&L statement: {str(e)}")
    
    # ==================== Cash Flow Report ====================
    
    async def generate_cash_flow(
        self,
        school_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> CashFlowReport:
        """Generate Cash Flow Statement
        
        Shows movement of cash in three categories:
        - Operating Activities (income/expenses from operations)
        - Investing Activities (asset purchases/sales)
        - Financing Activities (debt, owner contributions)
        
        Args:
            school_id: School identifier
            start_date: Period start date
            end_date: Period end date
        
        Returns:
            CashFlowReport with cash movements
        """
        try:
            # Get P&L for operating income
            pl_report = await self.generate_profit_loss(school_id, start_date, end_date)
            
            # Operating activities start with net income
            cash_from_operations = pl_report.net_income
            
            # In simple cash flow, operating activities = net income
            # (In complex scenario, would add back depreciation, track AR/AP changes)
            operating_items = [
                CashFlowActivityItem(
                    description="Net Income",
                    amount=pl_report.net_income,
                )
            ]
            
            # Get cash balance changes from GL
            # Query 1010 (Cash) for period
            cash_query = select(
                func.sum(JournalLineItem.debit_amount).label("cash_debits"),
                func.sum(JournalLineItem.credit_amount).label("cash_credits")
            ).join(JournalEntry, JournalLineItem.journal_entry_id == JournalEntry.id).where(
                and_(
                    JournalLineItem.gl_account_id == (
                        select(GLAccount.id).where(
                            and_(
                                GLAccount.school_id == school_id,
                                GLAccount.account_code == "1010",
                            )
                        ).scalar_subquery()
                    ),
                    JournalEntry.school_id == school_id,
                    JournalEntry.posting_status == PostingStatus.POSTED,
                    JournalEntry.entry_date >= start_date,
                    JournalEntry.entry_date <= end_date,
                )
            )
            cash_result = await self.session.execute(cash_query)
            cash_row = cash_result.first()
            
            # Ensure values are Decimal type (func.sum can return float)
            cash_debits = Decimal(str(cash_row.cash_debits)) if cash_row.cash_debits is not None else Decimal("0")
            cash_credits = Decimal(str(cash_row.cash_credits)) if cash_row.cash_credits is not None else Decimal("0")
            net_change_in_cash = cash_debits - cash_credits
            
            # Get opening and closing cash balance
            opening_cash = Decimal("0")  # Could be calculated from prior period
            ending_cash = opening_cash + net_change_in_cash
            
            return CashFlowReport(
                school_id=school_id,
                period_start_date=start_date,
                period_end_date=end_date,
                operating_activities=CashFlowActivity(
                    activity_type="operating",
                    activity_name="Operating Activities",
                    items=operating_items,
                    activity_subtotal=cash_from_operations,
                ),
                investing_activities=None,  # Simplified; could be detailed with fixed asset purchases
                financing_activities=None,  # Simplified
                cash_from_operations=cash_from_operations,
                cash_from_investing=Decimal("0"),
                cash_from_financing=Decimal("0"),
                net_change_in_cash=net_change_in_cash,
                beginning_cash_balance=opening_cash,
                ending_cash_balance=ending_cash,
            )
            
        except ReportsServiceError:
            raise
        except Exception as e:
            logger.error(f"Error generating cash flow: {str(e)}")
            raise ReportsServiceError(f"Failed to generate cash flow statement: {str(e)}")
