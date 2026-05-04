"""Retained Earnings Service - Auto-calculation at period close

Handles:
- Retained earnings calculation from P&L accounts
- Closing entry generation (revenue/expense → retained earnings)
- Opening balances for next period
- Equity account management
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func
from datetime import datetime
from decimal import Decimal

from models.finance import (
    JournalEntry,
    JournalLineItem,
    JournalEntryCreate,
    JournalLineItemCreate,
    PostingStatus,
    ReferenceType,
)
from models.finance.chart_of_accounts import GLAccount, AccountType, AccountCategory
from models.finance.fiscal_period import FiscalPeriod, FiscalPeriodStatus
from services.journal_entry_service import JournalEntryService, JournalEntryError
from services.coa_service import CoaService
from services.gl_audit_log_service import GLAuditLogService
from services.fiscal_period_service import FiscalPeriodService

logger = logging.getLogger(__name__)


class RetainedEarningsError(Exception):
    """Base exception for retained earnings operations"""
    pass


class RetainedEarningsService:
    """Service for managing retained earnings and period closing
    
    At period close:
    1. Calculate net income: Revenue - Expenses
    2. Close all P&L accounts to Retained Earnings
    3. Create opening balances for balance sheet accounts
    4. Generate post-closing trial balance (only balance sheet accounts)
    
    Ensures:
    - Equity = Assets - Liabilities (fundamental equation)
    - All revenue/expense accounts zero after close
    - Next period starts clean
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with database session
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
        self.journal_service = JournalEntryService(session)
        self.coa_service = CoaService(session)
        self.audit_service = GLAuditLogService(session)
        self.period_service = FiscalPeriodService(session)
    
    # ==================== Closing Procedures ====================
    
    async def calculate_net_income(
        self,
        school_id: str,
        period_id: str,
    ) -> Dict[str, Any]:
        """Calculate net income for a fiscal period
        
        Net Income = Revenue - Expenses
        
        Args:
            school_id: School identifier
            period_id: Fiscal period ID
            
        Returns:
            Dictionary with revenue, expenses, and net income
        """
        try:
            # Get period
            period = await self.period_service.get_period_by_id(school_id, period_id)
            if not period:
                raise RetainedEarningsError(f"Period {period_id} not found")
            
            # Calculate revenue (sum of all revenue accounts)
            revenue_result = await self.session.execute(
                select(func.sum(GLAccount.current_balance).label("total")).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type == AccountType.REVENUE,
                        GLAccount.is_active == True,
                    )
                )
            )
            total_revenue = float(revenue_result.scalar() or 0.0)
            
            # Calculate expenses (sum of all expense accounts - they have debit balance)
            expense_result = await self.session.execute(
                select(func.sum(GLAccount.current_balance).label("total")).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type == AccountType.EXPENSE,
                        GLAccount.is_active == True,
                    )
                )
            )
            total_expenses = float(expense_result.scalar() or 0.0)
            
            # Net income = Revenue - Expenses
            net_income = total_revenue - abs(total_expenses)
            
            return {
                "period_id": period_id,
                "period_name": period.period_name,
                "total_revenue": total_revenue,
                "total_expenses": abs(total_expenses),
                "net_income": net_income,
                "is_profit": net_income >= 0,
            }
        except RetainedEarningsError:
            raise
        except Exception as e:
            logger.error(f"Error calculating net income: {str(e)}")
            raise RetainedEarningsError(f"Failed to calculate net income: {str(e)}")
    
    async def close_period(
        self,
        school_id: str,
        period_id: str,
        closed_by: str,
        ip_address: Optional[str] = None,
        user_role: str = "finance",
    ) -> Dict[str, Any]:
        """Close a fiscal period and create closing entries
        
        **CRITICAL OPERATION** - Closes P&L accounts, calculates retained earnings,
        and transitions period to CLOSED status.
        
        Args:
            school_id: School identifier
            period_id: Period to close
            closed_by: User closing the period
            ip_address: IP address for audit
            user_role: User role for audit
            
        Returns:
            Dictionary with closing results
            
        Raises:
            RetainedEarningsError: If closing cannot be completed
        """
        try:
            # Get period
            period = await self.period_service.get_period_by_id(school_id, period_id)
            if not period:
                raise RetainedEarningsError(f"Period {period_id} not found")
            
            if period.status != FiscalPeriodStatus.LOCKED:
                raise RetainedEarningsError(
                    f"Can only close LOCKED periods. Current status: {period.status.value}"
                )
            
            # Calculate net income
            net_income_data = await self.calculate_net_income(school_id, period_id)
            net_income = net_income_data["net_income"]
            
            # Get revenue accounts (to close with credit balance)
            revenue_result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type == AccountType.REVENUE,
                        GLAccount.is_active == True,
                        GLAccount.current_balance != 0,
                    )
                )
            )
            revenue_accounts = revenue_result.scalars().all()
            
            # Get expense accounts (to close with debit balance)
            expense_result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type == AccountType.EXPENSE,
                        GLAccount.is_active == True,
                        GLAccount.current_balance != 0,
                    )
                )
            )
            expense_accounts = expense_result.scalars().all()
            
            # Get retained earnings account (usually in equity)
            retained_earnings_result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_code == "3100",  # Standard retained earnings code
                        GLAccount.is_active == True,
                    )
                )
            )
            retained_earnings_account = retained_earnings_result.scalar_one_or_none()
            
            if not retained_earnings_account:
                raise RetainedEarningsError(
                    "Retained Earnings account (3100) not found. Please create it first."
                )
            
            # Create closing entry journal lines
            closing_lines = []
            
            # Close revenue accounts (credit them with their balance)
            for revenue_account in revenue_accounts:
                # Revenue has credit balance, so we debit it to close
                closing_lines.append(
                    JournalLineItemCreate(
                        gl_account_id=revenue_account.id,
                        debit_amount=float(revenue_account.current_balance),  # Zero it out
                        credit_amount=0.0,
                        description=f"Closing: {revenue_account.account_name}",
                        line_number=len(closing_lines) + 1,
                    )
                )
            
            # Close expense accounts (debit them with their balance)
            for expense_account in expense_accounts:
                # Expense has debit balance, so we credit it to close
                closing_lines.append(
                    JournalLineItemCreate(
                        gl_account_id=expense_account.id,
                        debit_amount=0.0,
                        credit_amount=float(abs(expense_account.current_balance)),  # Zero it out
                        description=f"Closing: {expense_account.account_name}",
                        line_number=len(closing_lines) + 1,
                    )
                )
            
            # Post net income to retained earnings
            if net_income > 0:
                # Profit: credit retained earnings
                closing_lines.append(
                    JournalLineItemCreate(
                        gl_account_id=retained_earnings_account.id,
                        debit_amount=0.0,
                        credit_amount=float(net_income),
                        description=f"Net Income for {period.period_name}",
                        line_number=len(closing_lines) + 1,
                    )
                )
            elif net_income < 0:
                # Loss: debit retained earnings
                closing_lines.append(
                    JournalLineItemCreate(
                        gl_account_id=retained_earnings_account.id,
                        debit_amount=float(abs(net_income)),
                        credit_amount=0.0,
                        description=f"Net Loss for {period.period_name}",
                        line_number=len(closing_lines) + 1,
                    )
                )
            
            # Create closing entry
            closing_entry_data = JournalEntryCreate(
                entry_date=period.end_date,
                reference_type=ReferenceType.ADJUSTMENT,
                reference_id=period_id,
                description=f"Period Close - {period.period_name}",
                line_items=closing_lines,
                notes=f"Auto-closing entry. Net income: {net_income:.2f}",
            )
            
            # Create and post closing entry
            closing_entry = await self.journal_service.create_entry(
                school_id=school_id,
                entry_data=closing_entry_data,
                created_by="SYSTEM",
            )
            
            await self.journal_service.post_entry(
                school_id=school_id,
                entry_id=closing_entry.id,
                posted_by=closed_by,
                approval_notes=f"Period close for {period.period_name}",
                ip_address=ip_address,
                user_role=user_role,
            )
            
            # Update period status to CLOSED
            period.status = FiscalPeriodStatus.CLOSED
            period.closed_date = datetime.utcnow()
            period.closed_by = closed_by
            self.session.add(period)
            await self.session.commit()
            
            logger.info(
                f"Closed period {period.period_name} (net income: {net_income:.2f}, "
                f"closing entry: {closing_entry.id})"
            )
            
            return {
                "status": "success",
                "period_id": period_id,
                "period_name": period.period_name,
                "net_income": net_income,
                "closing_entry_id": closing_entry.id,
                "revenue_accounts_closed": len(revenue_accounts),
                "expense_accounts_closed": len(expense_accounts),
            }
            
        except RetainedEarningsError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error closing period: {str(e)}")
            raise RetainedEarningsError(f"Failed to close period: {str(e)}")
    
    # ==================== Opening Balances ====================
    
    async def set_opening_balances_for_period(
        self,
        school_id: str,
        from_period_id: str,
        to_period_id: str,
        created_by: str,
    ) -> Dict[str, Any]:
        """Set opening balances for next period from previous period close
        
        Balance sheet accounts carry forward their closing balance.
        
        Args:
            school_id: School identifier
            from_period_id: Previous period ID
            to_period_id: New period ID
            created_by: User creating opening balances
            
        Returns:
            Summary of opening balances set
        """
        try:
            # Get to_period
            to_period = await self.period_service.get_period_by_id(school_id, to_period_id)
            if not to_period:
                raise RetainedEarningsError(f"Period {to_period_id} not found")
            
            # Get balance sheet accounts (Asset, Liability, Equity)
            bs_result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type.in_([
                            AccountType.ASSET,
                            AccountType.LIABILITY,
                            AccountType.EQUITY,
                        ]),
                        GLAccount.is_active == True,
                    )
                )
            )
            bs_accounts = bs_result.scalars().all()
            
            # Set opening balance for each (from current_balance)
            for account in bs_accounts:
                await self.coa_service.set_opening_balance(
                    school_id=school_id,
                    account_id=account.id,
                    opening_balance=account.current_balance,
                )
            
            logger.info(
                f"Set opening balances for {len(bs_accounts)} balance sheet accounts "
                f"for period {to_period.period_name}"
            )
            
            return {
                "period_id": to_period_id,
                "accounts_updated": len(bs_accounts),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except RetainedEarningsError:
            raise
        except Exception as e:
            logger.error(f"Error setting opening balances: {str(e)}")
            raise RetainedEarningsError(f"Failed to set opening balances: {str(e)}")
    
    # ==================== Trial Balance & Analysis ====================
    
    async def get_post_closing_trial_balance(
        self,
        school_id: str,
        period_id: str,
    ) -> Dict[str, Any]:
        """Get post-closing trial balance (balance sheet accounts only)
        
        After period close, only balance sheet accounts should have balances.
        Revenue and expense accounts should be zero.
        
        Args:
            school_id: School identifier
            period_id: Period ID
            
        Returns:
            Post-closing trial balance
        """
        try:
            # Get balance sheet accounts with balances
            result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type.in_([
                            AccountType.ASSET,
                            AccountType.LIABILITY,
                            AccountType.EQUITY,
                        ]),
                        GLAccount.is_active == True,
                        GLAccount.current_balance != 0,
                    )
                ).order_by(GLAccount.account_type, GLAccount.account_code)
            )
            accounts = result.scalars().all()
            
            total_debits = 0.0
            total_credits = 0.0
            by_type = {}
            
            for account in accounts:
                account_type = account.account_type.value
                if account_type not in by_type:
                    by_type[account_type] = {
                        "accounts": [],
                        "debit": 0.0,
                        "credit": 0.0,
                    }
                
                if account.current_balance > 0:
                    debit = account.current_balance
                    credit = 0.0
                    total_debits += debit
                else:
                    debit = 0.0
                    credit = abs(account.current_balance)
                    total_credits += credit
                
                by_type[account_type]["accounts"].append({
                    "code": account.account_code,
                    "name": account.account_name,
                    "debit": debit,
                    "credit": credit,
                })
                by_type[account_type]["debit"] += debit
                by_type[account_type]["credit"] += credit
            
            # Verify trial balance is balanced
            balanced = abs(total_debits - total_credits) < 0.01
            
            return {
                "period_id": period_id,
                "total_debits": total_debits,
                "total_credits": total_credits,
                "balanced": balanced,
                "by_type": by_type,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting post-closing trial balance: {str(e)}")
            return {"error": str(e)}
    
    async def verify_period_closed(
        self,
        school_id: str,
        period_id: str,
    ) -> Dict[str, Any]:
        """Verify a period is properly closed
        
        Checks:
        - All revenue/expense accounts are zero
        - Trial balance is balanced
        - Period status is CLOSED
        
        Args:
            school_id: School identifier
            period_id: Period ID to verify
            
        Returns:
            Verification results
        """
        try:
            # Get period
            period = await self.period_service.get_period_by_id(school_id, period_id)
            if not period:
                return {"error": "Period not found"}
            
            # Check period is closed
            is_closed = period.status == FiscalPeriodStatus.CLOSED
            
            # Check P&L accounts are zero
            pl_result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_type.in_([
                            AccountType.REVENUE,
                            AccountType.EXPENSE,
                        ]),
                        GLAccount.is_active == True,
                        GLAccount.current_balance != 0,
                    )
                )
            )
            unclosed_accounts = pl_result.scalars().all()
            
            # Get trial balance
            tb = await self.get_post_closing_trial_balance(school_id, period_id)
            
            issues = []
            if not is_closed:
                issues.append("Period status is not CLOSED")
            if unclosed_accounts:
                issues.append(
                    f"{len(unclosed_accounts)} P&L accounts still have balances"
                )
            if not tb.get("balanced"):
                issues.append("Trial balance is not balanced")
            
            return {
                "period_id": period_id,
                "period_name": period.period_name,
                "status": period.status.value,
                "is_properly_closed": len(issues) == 0,
                "issues": issues,
                "trial_balance_balanced": tb.get("balanced"),
                "unclosed_accounts": len(unclosed_accounts),
            }
            
        except Exception as e:
            logger.error(f"Error verifying period close: {str(e)}")
            return {"error": str(e)}
    
    async def get_retained_earnings_balance(
        self,
        school_id: str,
    ) -> float:
        """Get current retained earnings balance
        
        Args:
            school_id: School identifier
            
        Returns:
            Retained earnings balance
        """
        try:
            result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_code == "3100",
                        GLAccount.is_active == True,
                    )
                )
            )
            account = result.scalar_one_or_none()
            return float(account.current_balance) if account else 0.0
        except Exception as e:
            logger.error(f"Error getting retained earnings balance: {str(e)}")
            return 0.0
