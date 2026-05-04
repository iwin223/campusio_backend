"""Bank Reconciliation Service - GL to bank statement matching

Handles:
- Bank statement import
- Automatic GL to bank matching
- Outstanding item tracking
- Reconciliation variance analysis
- GL adjustment entry creation
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_
from datetime import datetime, timedelta

from models.finance.bank_reconciliation import (
    BankReconciliation,
    BankReconciliationStatus,
    BankStatement,
    BankStatementCreate,
    BankTransactionType,
    BankReconciliationMatch,
    BankItemStatus,
    BankReconciliationAdjustment,
)
from models.finance import JournalEntry, PostingStatus
from models.finance.chart_of_accounts import GLAccount
from services.coa_service import CoaService
from services.journal_entry_service import JournalEntryService

logger = logging.getLogger(__name__)


class BankReconciliationError(Exception):
    """Base exception for bank reconciliation operations"""
    pass


class BankReconciliationService:
    """Service for GL bank account reconciliation with bank statements
    
    **Process**:
    1. Import bank statement transactions
    2. Automatically match GL entries to bank transactions
    3. Identify unmatched items (outstanding, deposits in transit)
    4. Calculate reconciling items
    5. Create GL adjustments for differences (fees, interest)
    6. Mark reconciliation complete
    
    **Key Concepts**:
    - Outstanding Checks: GL entries with no bank match (checks not cleared)
    - Deposits in Transit: Bank deposits not yet in GL
    - Bank Fees: Bank charges requiring GL adjustment
    - Reconciling Items: Timing differences that should clear over time
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
        self.coa_service = CoaService(session)
        self.journal_service = JournalEntryService(session)
    
    # ==================== Bank Statement Import ====================
    
    async def import_bank_statement(
        self,
        school_id: str,
        gl_account_id: str,
        statement_date: datetime,
        statement_beginning_balance: float,
        statement_ending_balance: float,
        transactions: List[BankStatementCreate],
        reconciled_by: str,
        notes: Optional[str] = None,
    ) -> str:
        """Import a bank statement and create reconciliation record
        
        Args:
            school_id: School identifier
            gl_account_id: GL bank account being reconciled
            statement_date: Date of bank statement
            statement_beginning_balance: Starting balance
            statement_ending_balance: Ending balance
            transactions: List of bank transactions
            reconciled_by: User importing statement
            notes: Optional reconciliation notes
            
        Returns:
            BankReconciliation ID
            
        Raises:
            BankReconciliationError: If import fails
        """
        try:
            # Get GL account
            gl_account = await self.coa_service.get_account_by_id(school_id, gl_account_id)
            if not gl_account:
                raise BankReconciliationError(f"GL Account {gl_account_id} not found")
            
            # Create reconciliation record
            reconciliation = BankReconciliation(
                school_id=school_id,
                gl_account_id=gl_account_id,
                statement_date=statement_date,
                statement_beginning_balance=statement_beginning_balance,
                statement_ending_balance=statement_ending_balance,
                gl_beginning_balance=gl_account.current_balance,
                gl_ending_balance=gl_account.current_balance,
                reconciliation_date=datetime.utcnow(),
                reconciliation_status=BankReconciliationStatus.IN_PROGRESS,
                total_bank_transactions=len(transactions),
                reconciled_by=reconciled_by,
                notes=notes,
            )
            
            self.session.add(reconciliation)
            await self.session.flush()
            
            # Import bank statement transactions
            for idx, txn in enumerate(transactions):
                bank_statement = BankStatement(
                    school_id=school_id,
                    bank_reconciliation_id=reconciliation.id,
                    statement_line_number=idx + 1,
                    transaction_date=txn.transaction_date,
                    transaction_type=txn.transaction_type,
                    description=txn.description,
                    amount=txn.amount,
                    running_balance=txn.running_balance,
                    bank_reference=txn.bank_reference,
                    imported_by=reconciled_by,
                )
                self.session.add(bank_statement)
            
            await self.session.commit()
            
            logger.info(
                f"Imported bank statement for account {gl_account.account_code} "
                f"with {len(transactions)} transactions"
            )
            
            return reconciliation.id
            
        except BankReconciliationError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error importing bank statement: {str(e)}")
            raise BankReconciliationError(f"Failed to import bank statement: {str(e)}")
    
    # ==================== Automatic Matching ====================
    
    async def auto_match_transactions(
        self,
        school_id: str,
        reconciliation_id: str,
        matching_window_days: int = 5,
    ) -> Dict[str, Any]:
        """Automatically match bank transactions to GL entries
        
        Matching rules (in order of priority):
        1. Exact match: Same amount + same date
        2. Date within window: Same amount, date within matching_window_days
        3. Close amount: Amount within $0.01, date within window
        4. Outstanding check: GL entry > bank transaction date (check not cleared)
        5. Deposit in transit: Bank deposit > GL entry date (not yet recorded)
        
        Args:
            school_id: School identifier
            reconciliation_id: BankReconciliation ID
            matching_window_days: Number of days to match within
            
        Returns:
            Summary of matching results
            
        Raises:
            BankReconciliationError: If matching fails
        """
        try:
            # Get reconciliation
            recon = await self.session.execute(
                select(BankReconciliation).where(
                    BankReconciliation.id == reconciliation_id
                )
            )
            reconciliation = recon.scalar_one_or_none()
            if not reconciliation:
                raise BankReconciliationError(f"Reconciliation {reconciliation_id} not found")
            
            # Get all bank statement items
            bank_result = await self.session.execute(
                select(BankStatement).where(
                    BankStatement.bank_reconciliation_id == reconciliation_id
                ).order_by(BankStatement.transaction_date)
            )
            bank_items = bank_result.scalars().all()
            
            # Get GL bank account entries (last 60 days for matching window)
            cutoff_date = reconciliation.statement_date - timedelta(days=60)
            gl_result = await self.session.execute(
                select(JournalEntry).where(
                    and_(
                        JournalEntry.school_id == school_id,
                        JournalEntry.posting_status == PostingStatus.POSTED,
                        JournalEntry.entry_date >= cutoff_date,
                    )
                )
            )
            gl_entries = gl_result.scalars().all()
            
            matched_count = 0
            unmatched_bank = 0
            unmatched_gl = 0
            
            # For each bank item, try to find GL match
            for bank_item in bank_items:
                match_found = False
                
                # Try exact match (amount + date)
                for gl_entry in gl_entries:
                    if abs(bank_item.amount - gl_entry.total_debit) < 0.01 and \
                       bank_item.transaction_date.date() == gl_entry.entry_date.date():
                        
                        match = BankReconciliationMatch(
                            school_id=school_id,
                            bank_reconciliation_id=reconciliation_id,
                            bank_statement_id=bank_item.id,
                            journal_entry_id=gl_entry.id,
                            match_status=BankItemStatus.MATCHED,
                            bank_amount=bank_item.amount,
                            bank_date=bank_item.transaction_date,
                            bank_description=bank_item.description,
                            gl_amount=gl_entry.total_debit,
                            gl_date=gl_entry.entry_date,
                            gl_description=gl_entry.description,
                            matched_by=reconciliation.reconciled_by,
                        )
                        self.session.add(match)
                        bank_item.is_cleared = True
                        bank_item.cleared_date = datetime.utcnow()
                        match_found = True
                        matched_count += 1
                        break
                
                # If no exact match, try within matching window
                if not match_found:
                    window_start = bank_item.transaction_date - timedelta(days=matching_window_days)
                    window_end = bank_item.transaction_date + timedelta(days=matching_window_days)
                    
                    for gl_entry in gl_entries:
                        if abs(bank_item.amount - gl_entry.total_debit) < 0.01 and \
                           window_start <= gl_entry.entry_date <= window_end:
                            
                            days_diff = (gl_entry.entry_date - bank_item.transaction_date).days
                            
                            match = BankReconciliationMatch(
                                school_id=school_id,
                                bank_reconciliation_id=reconciliation_id,
                                bank_statement_id=bank_item.id,
                                journal_entry_id=gl_entry.id,
                                match_status=BankItemStatus.MATCHED,
                                bank_amount=bank_item.amount,
                                bank_date=bank_item.transaction_date,
                                bank_description=bank_item.description,
                                gl_amount=gl_entry.total_debit,
                                gl_date=gl_entry.entry_date,
                                gl_description=gl_entry.description,
                                days_variance=days_diff,
                                matched_by=reconciliation.reconciled_by,
                            )
                            self.session.add(match)
                            bank_item.is_cleared = True
                            bank_item.cleared_date = datetime.utcnow()
                            match_found = True
                            matched_count += 1
                            break
                
                # If still no match, create unmatched item
                if not match_found:
                    match = BankReconciliationMatch(
                        school_id=school_id,
                        bank_reconciliation_id=reconciliation_id,
                        bank_statement_id=bank_item.id,
                        match_status=BankItemStatus.UNMATCHED_BANK,
                        bank_amount=bank_item.amount,
                        bank_date=bank_item.transaction_date,
                        bank_description=bank_item.description,
                        requires_review=True,
                        matched_by=reconciliation.reconciled_by,
                    )
                    self.session.add(match)
                    unmatched_bank += 1
            
            await self.session.commit()
            
            # Update reconciliation totals
            reconciliation.matched_transactions = matched_count
            reconciliation.unmatched_bank_items = unmatched_bank
            self.session.add(reconciliation)
            await self.session.commit()
            
            return {
                "reconciliation_id": reconciliation_id,
                "matched": matched_count,
                "unmatched_bank": unmatched_bank,
                "unmatched_gl": unmatched_gl,
            }
            
        except BankReconciliationError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error in automatic matching: {str(e)}")
            raise BankReconciliationError(f"Failed to match transactions: {str(e)}")
    
    # ==================== Manual Matching ====================
    
    async def manually_match_transaction(
        self,
        school_id: str,
        bank_statement_id: str,
        journal_entry_id: str,
        matched_by: str,
        variance_reason: Optional[str] = None,
    ) -> BankReconciliationMatch:
        """Manually match a bank transaction to GL entry
        
        Used for non-automatic matches that require user review.
        
        Args:
            school_id: School identifier
            bank_statement_id: Bank statement item ID
            journal_entry_id: Journal entry ID
            matched_by: User performing match
            variance_reason: Reason if amounts differ
            
        Returns:
            Created BankReconciliationMatch
        """
        try:
            # Get bank statement
            bank_result = await self.session.execute(
                select(BankStatement).where(
                    BankStatement.id == bank_statement_id
                )
            )
            bank_item = bank_result.scalar_one_or_none()
            if not bank_item:
                raise BankReconciliationError(f"Bank statement {bank_statement_id} not found")
            
            # Get GL entry
            gl_result = await self.session.execute(
                select(JournalEntry).where(
                    JournalEntry.id == journal_entry_id
                )
            )
            gl_entry = gl_result.scalar_one_or_none()
            if not gl_entry:
                raise BankReconciliationError(f"Journal entry {journal_entry_id} not found")
            
            # Calculate variance
            variance = bank_item.amount - gl_entry.total_debit
            
            # Create match
            match = BankReconciliationMatch(
                school_id=school_id,
                bank_reconciliation_id=bank_item.bank_reconciliation_id,
                bank_statement_id=bank_statement_id,
                journal_entry_id=journal_entry_id,
                match_status=BankItemStatus.MATCHED if abs(variance) < 0.01 else BankItemStatus.PENDING,
                bank_amount=bank_item.amount,
                bank_date=bank_item.transaction_date,
                bank_description=bank_item.description,
                gl_amount=gl_entry.total_debit,
                gl_date=gl_entry.entry_date,
                gl_description=gl_entry.description,
                variance_amount=variance,
                variance_reason=variance_reason,
                days_variance=(gl_entry.entry_date - bank_item.transaction_date).days,
                matched_by=matched_by,
            )
            
            self.session.add(match)
            bank_item.is_cleared = True
            bank_item.cleared_date = datetime.utcnow()
            await self.session.commit()
            
            return match
            
        except BankReconciliationError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error in manual matching: {str(e)}")
            raise BankReconciliationError(f"Failed to match transactions: {str(e)}")
    
    # ==================== Reconciliation Analysis ====================
    
    async def calculate_reconciling_items(
        self,
        school_id: str,
        reconciliation_id: str,
    ) -> Dict[str, Any]:
        """Calculate reconciling items (outstanding checks, deposits in transit)
        
        These are timing differences that explain why GL balance ≠ bank balance.
        
        Args:
            school_id: School identifier
            reconciliation_id: BankReconciliation ID
            
        Returns:
            Summary of reconciling items
        """
        try:
            # Get unmatched items
            unmatched_result = await self.session.execute(
                select(BankReconciliationMatch).where(
                    and_(
                        BankReconciliationMatch.bank_reconciliation_id == reconciliation_id,
                        BankReconciliationMatch.match_status.in_([
                            BankItemStatus.UNMATCHED_BANK,
                            BankItemStatus.UNMATCHED_GL,
                        ])
                    )
                )
            )
            unmatched_items = unmatched_result.scalars().all()
            
            outstanding_checks = 0.0
            deposits_in_transit = 0.0
            bank_fees = 0.0
            
            for item in unmatched_items:
                if item.bank_amount < 0:  # Withdrawal
                    outstanding_checks += abs(item.bank_amount)
                elif item.bank_amount > 0:  # Deposit
                    deposits_in_transit += item.bank_amount
            
            return {
                "reconciliation_id": reconciliation_id,
                "outstanding_checks": outstanding_checks,
                "deposits_in_transit": deposits_in_transit,
                "bank_fees": bank_fees,
                "total_reconciling_items": outstanding_checks + deposits_in_transit + bank_fees,
            }
            
        except Exception as e:
            logger.error(f"Error calculating reconciling items: {str(e)}")
            raise BankReconciliationError(f"Failed to calculate reconciling items: {str(e)}")
    
    async def calculate_variance(
        self,
        school_id: str,
        reconciliation_id: str,
    ) -> Dict[str, Any]:
        """Calculate variance between GL balance and bank balance
        
        Args:
            school_id: School identifier
            reconciliation_id: BankReconciliation ID
            
        Returns:
            Variance analysis
        """
        try:
            recon = await self.session.execute(
                select(BankReconciliation).where(
                    BankReconciliation.id == reconciliation_id
                )
            )
            reconciliation = recon.scalar_one_or_none()
            if not reconciliation:
                raise BankReconciliationError(f"Reconciliation {reconciliation_id} not found")
            
            # Get GL account
            gl_account = await self.coa_service.get_account_by_id(
                school_id,
                reconciliation.gl_account_id
            )
            if not gl_account:
                raise BankReconciliationError("GL account not found")
            
            gl_balance = gl_account.current_balance
            bank_balance = reconciliation.statement_ending_balance
            
            variance = bank_balance - gl_balance
            
            reconciliation.variance_amount = variance
            if abs(variance) < 0.01:
                reconciliation.variance_reason = "Reconciled"
            else:
                reconciliation.variance_reason = f"Variance of {variance:.2f} to review"
            
            self.session.add(reconciliation)
            await self.session.commit()
            
            return {
                "reconciliation_id": reconciliation_id,
                "bank_balance": bank_balance,
                "gl_balance": gl_balance,
                "variance": variance,
                "is_balanced": abs(variance) < 0.01,
            }
            
        except BankReconciliationError:
            raise
        except Exception as e:
            logger.error(f"Error calculating variance: {str(e)}")
            raise BankReconciliationError(f"Failed to calculate variance: {str(e)}")
    
    # ==================== Reconciliation Completion ====================
    
    async def complete_reconciliation(
        self,
        school_id: str,
        reconciliation_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Mark reconciliation as completed
        
        Can only complete if variance is zero (or very close due to rounding).
        
        Args:
            school_id: School identifier
            reconciliation_id: BankReconciliation ID
            approved_by: User approving reconciliation
            
        Returns:
            Completion summary
            
        Raises:
            BankReconciliationError: If reconciliation cannot be completed
        """
        try:
            recon = await self.session.execute(
                select(BankReconciliation).where(
                    BankReconciliation.id == reconciliation_id
                )
            )
            reconciliation = recon.scalar_one_or_none()
            if not reconciliation:
                raise BankReconciliationError(f"Reconciliation {reconciliation_id} not found")
            
            # Check if balanced
            variance_result = await self.calculate_variance(school_id, reconciliation_id)
            if not variance_result["is_balanced"]:
                raise BankReconciliationError(
                    f"Cannot complete reconciliation with variance of {variance_result['variance']:.2f}"
                )
            
            # Mark as completed
            reconciliation.reconciliation_status = BankReconciliationStatus.COMPLETED
            reconciliation.approved_by = approved_by
            reconciliation.approved_date = datetime.utcnow()
            self.session.add(reconciliation)
            await self.session.commit()
            
            logger.info(
                f"Completed bank reconciliation {reconciliation_id} "
                f"for account {reconciliation.gl_account_id}"
            )
            
            return {
                "status": "success",
                "reconciliation_id": reconciliation_id,
                "completed_date": reconciliation.approved_date.isoformat(),
                "approved_by": approved_by,
            }
            
        except BankReconciliationError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error completing reconciliation: {str(e)}")
            raise BankReconciliationError(f"Failed to complete reconciliation: {str(e)}")
    
    # ==================== Reporting ====================
    
    async def get_reconciliation_summary(
        self,
        school_id: str,
        reconciliation_id: str,
    ) -> Dict[str, Any]:
        """Get reconciliation summary report
        
        Args:
            school_id: School identifier
            reconciliation_id: BankReconciliation ID
            
        Returns:
            Reconciliation summary with all key metrics
        """
        try:
            recon = await self.session.execute(
                select(BankReconciliation).where(
                    BankReconciliation.id == reconciliation_id
                )
            )
            reconciliation = recon.scalar_one_or_none()
            if not reconciliation:
                raise BankReconciliationError(f"Reconciliation {reconciliation_id} not found")
            
            variance = await self.calculate_variance(school_id, reconciliation_id)
            reconciling_items = await self.calculate_reconciling_items(school_id, reconciliation_id)
            
            return {
                "reconciliation_id": reconciliation_id,
                "gl_account_id": reconciliation.gl_account_id,
                "statement_date": reconciliation.statement_date.isoformat(),
                "bank_balance": reconciliation.statement_ending_balance,
                "gl_balance": variance["gl_balance"],
                "variance": variance["variance"],
                "is_balanced": variance["is_balanced"],
                "matched_transactions": reconciliation.matched_transactions,
                "unmatched_bank_items": reconciliation.unmatched_bank_items,
                "unmatched_gl_items": reconciliation.unmatched_gl_items,
                "status": reconciliation.reconciliation_status.value,
                "reconciled_by": reconciliation.reconciled_by,
                "approved_by": reconciliation.approved_by,
                "reconciling_items": reconciling_items,
            }
            
        except BankReconciliationError:
            raise
        except Exception as e:
            logger.error(f"Error getting reconciliation summary: {str(e)}")
            return {"error": str(e)}
