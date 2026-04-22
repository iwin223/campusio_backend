"""Expense Service - Management of school expenses with approval workflow

Handles expense CRUD, approval workflow, GL posting, and payment tracking.
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_
from datetime import datetime

from models.finance import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    PaymentStatus,
    JournalEntryCreate,
    JournalLineItemCreate,
    ReferenceType,
)
from models.finance.chart_of_accounts import GLAccount

logger = logging.getLogger(__name__)


class ExpenseError(Exception):
    """Base exception for expense service errors"""
    pass


class ExpenseValidationError(ExpenseError):
    """Raised when expense validation fails"""
    pass


class ExpenseService:
    """Service for managing school expenses"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_expense(
        self,
        school_id: str,
        expense_data,
        created_by: str,
    ) -> Dict[str, Any]:
        """Create a new expense record in DRAFT status
        
        Args:
            school_id: School identifier
            expense_data: ExpenseCreate with expense details
            created_by: User creating the expense
            
        Returns:
            Expense as dictionary
            
        Raises:
            ExpenseValidationError: If validation fails
        """
        try:
            # Validate amount
            if expense_data.amount <= 0:
                raise ExpenseValidationError("Amount must be positive")
            
            # If GL account provided, validate it exists
            if expense_data.gl_account_id:
                result = await self.session.execute(
                    select(GLAccount).where(
                        and_(
                            GLAccount.id == expense_data.gl_account_id,
                            GLAccount.school_id == school_id,
                            GLAccount.is_active == True
                        )
                    )
                )
                gl_account = result.scalar_one_or_none()
                if not gl_account:
                    raise ExpenseValidationError(f"GL account {expense_data.gl_account_id} not found or inactive")
                gl_account_code = gl_account.account_code
            else:
                gl_account_code = expense_data.gl_account_code
            
            # Create expense
            expense = Expense(
                school_id=school_id,
                category=expense_data.category,
                description=expense_data.description,
                vendor_name=expense_data.vendor_name,
                amount=expense_data.amount,
                currency=expense_data.currency,
                gl_account_id=expense_data.gl_account_id,
                gl_account_code=gl_account_code,
                expense_date=expense_data.expense_date,
                status=ExpenseStatus.DRAFT,
                created_by=created_by,
                notes=expense_data.notes,
            )
            
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Created expense {expense.id} for school {school_id}")
            return await self._expense_to_dict(expense)
            
        except (ExpenseValidationError, ExpenseError):
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating expense: {str(e)}")
            raise ExpenseError(f"Error creating expense: {str(e)}")
    
    async def get_expense_by_id(
        self,
        school_id: str,
        expense_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get expense by ID
        
        Args:
            school_id: School identifier
            expense_id: Expense to retrieve
            
        Returns:
            Expense dictionary or None if not found
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            if not expense:
                return None
            return await self._expense_to_dict(expense)
        except Exception as e:
            logger.error(f"Error retrieving expense {expense_id}: {str(e)}")
            raise ExpenseError(f"Error retrieving expense: {str(e)}")
    
    async def get_expenses_filtered(
        self,
        school_id: str,
        category: Optional[ExpenseCategory] = None,
        status: Optional[ExpenseStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get filtered list of expenses with pagination
        
        Args:
            school_id: School identifier
            category: Optional filter by category
            status: Optional filter by status
            start_date: Optional start date filter
            end_date: Optional end date filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of expense dictionaries
        """
        try:
            query = select(Expense).where(
                Expense.school_id == school_id
            )
            
            if category:
                query = query.where(Expense.category == category)
            if status:
                query = query.where(Expense.status == status)
            if start_date:
                query = query.where(Expense.expense_date >= start_date)
            if end_date:
                query = query.where(Expense.expense_date <= end_date)
            
            query = query.order_by(Expense.expense_date.desc())
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            expenses = result.scalars().all()
            
            return [await self._expense_to_dict(exp) for exp in expenses]
        except Exception as e:
            logger.error(f"Error filtering expenses: {str(e)}")
            raise ExpenseError(f"Error filtering expenses: {str(e)}")
    
    async def update_expense(
        self,
        school_id: str,
        expense_id: str,
        update_data,
    ) -> Dict[str, Any]:
        """Update a DRAFT expense
        
        Args:
            school_id: School identifier
            expense_id: Expense to update
            update_data: ExpenseUpdate with new values
            
        Returns:
            Updated expense dictionary
            
        Raises:
            ExpenseError: If not in DRAFT status or not found
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if expense.status != ExpenseStatus.DRAFT:
                raise ExpenseError(
                    f"Cannot update expense in {expense.status} status (only DRAFT can be updated)"
                )
            
            # Update fields
            if update_data.category is not None:
                expense.category = update_data.category
            if update_data.description is not None:
                expense.description = update_data.description
            if update_data.vendor_name is not None:
                expense.vendor_name = update_data.vendor_name
            if update_data.amount is not None:
                if update_data.amount <= 0:
                    raise ExpenseValidationError("Amount must be positive")
                expense.amount = update_data.amount
            if update_data.gl_account_id is not None:
                result = await self.session.execute(
                    select(GLAccount).where(
                        and_(
                            GLAccount.id == update_data.gl_account_id,
                            GLAccount.school_id == school_id,
                            GLAccount.is_active == True
                        )
                    )
                )
                gl_account = result.scalar_one_or_none()
                if not gl_account:
                    raise ExpenseValidationError(f"GL account not found or inactive")
                expense.gl_account_id = update_data.gl_account_id
                expense.gl_account_code = gl_account.account_code
            if update_data.gl_account_code is not None:
                expense.gl_account_code = update_data.gl_account_code
            if update_data.expense_date is not None:
                expense.expense_date = update_data.expense_date
            if update_data.notes is not None:
                expense.notes = update_data.notes
            
            expense.updated_at = datetime.utcnow()
            self.session.add(expense)
            await self.session.commit()
            
            return await self._expense_to_dict(expense)
        except (ExpenseError, ExpenseValidationError):
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating expense: {str(e)}")
            raise ExpenseError(f"Error updating expense: {str(e)}")
    
    async def submit_expense(
        self,
        school_id: str,
        expense_id: str,
        submitted_by: str,
    ) -> Dict[str, Any]:
        """Submit expense for approval (DRAFT → PENDING)
        
        Args:
            school_id: School identifier
            expense_id: Expense to submit
            submitted_by: User submitting
            
        Returns:
            Updated expense dictionary
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if expense.status != ExpenseStatus.DRAFT:
                raise ExpenseError(
                    f"Cannot submit expense in {expense.status} status (only DRAFT can be submitted)"
                )
            
            expense.status = ExpenseStatus.PENDING
            expense.submitted_by = submitted_by
            expense.submitted_at = datetime.utcnow()
            expense.updated_at = datetime.utcnow()
            
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Submitted expense {expense_id} for approval")
            return await self._expense_to_dict(expense)
        except ExpenseError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error submitting expense: {str(e)}")
            raise ExpenseError(f"Error submitting expense: {str(e)}")
    
    async def approve_expense(
        self,
        school_id: str,
        expense_id: str,
        approved_by: str,
        approval_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve expense and create GL posting (PENDING → APPROVED)
        
        Note: GL posting is deferred until separate approval call
        
        Args:
            school_id: School identifier
            expense_id: Expense to approve
            approved_by: User approving
            approval_notes: Optional approval notes
            
        Returns:
            Updated expense dictionary
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if expense.status != ExpenseStatus.PENDING:
                raise ExpenseError(
                    f"Cannot approve expense in {expense.status} status (only PENDING can be approved)"
                )
            
            expense.status = ExpenseStatus.APPROVED
            expense.approved_by = approved_by
            expense.approved_date = datetime.utcnow()
            expense.updated_at = datetime.utcnow()
            if approval_notes:
                expense.notes = f"{expense.notes or ''}\n[APPROVAL] {approval_notes}".strip()
            
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Approved expense {expense_id}")
            return await self._expense_to_dict(expense)
        except ExpenseError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error approving expense: {str(e)}")
            raise ExpenseError(f"Error approving expense: {str(e)}")
    
    async def reject_expense(
        self,
        school_id: str,
        expense_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> Dict[str, Any]:
        """Reject expense (PENDING → REJECTED)
        
        Args:
            school_id: School identifier
            expense_id: Expense to reject
            rejected_by: User rejecting
            rejection_reason: Reason for rejection
            
        Returns:
            Updated expense dictionary
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if expense.status != ExpenseStatus.PENDING:
                raise ExpenseError(
                    f"Cannot reject expense in {expense.status} status (only PENDING can be rejected)"
                )
            
            expense.status = ExpenseStatus.REJECTED
            expense.rejected_by = rejected_by
            expense.rejected_reason = rejection_reason
            expense.updated_at = datetime.utcnow()
            
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Rejected expense {expense_id}: {rejection_reason}")
            return await self._expense_to_dict(expense)
        except ExpenseError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error rejecting expense: {str(e)}")
            raise ExpenseError(f"Error rejecting expense: {str(e)}")
    
    async def post_expense_to_gl(
        self,
        school_id: str,
        expense_id: str,
        posted_by: str,
    ) -> Dict[str, Any]:
        """Post approved expense to GL (APPROVED → POSTED)
        
        Creates a journal entry and posts it to GL.
        
        Args:
            school_id: School identifier
            expense_id: Expense to post
            posted_by: User posting
            
        Returns:
            Updated expense dictionary with journal_entry_id
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if expense.status != ExpenseStatus.APPROVED:
                raise ExpenseError(
                    f"Cannot post expense in {expense.status} status (only APPROVED can be posted)"
                )
            
            # Create GL journal entry
            journal_entry_id = await self._create_expense_journal_entry(
                school_id=school_id,
                expense=expense,
                posted_by=posted_by,
            )
            
            # Update expense
            expense.status = ExpenseStatus.POSTED
            expense.posted_date = datetime.utcnow()
            expense.journal_entry_id = journal_entry_id
            expense.updated_at = datetime.utcnow()
            
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Posted expense {expense_id} to GL (journal entry {journal_entry_id})")
            return await self._expense_to_dict(expense)
        except ExpenseError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error posting expense to GL: {str(e)}")
            raise ExpenseError(f"Error posting expense to GL: {str(e)}")
    
    async def record_payment(
        self,
        school_id: str,
        expense_id: str,
        amount_paid: float,
        paid_by: str,
        payment_date: datetime,
    ) -> Dict[str, Any]:
        """Record payment for an expense
        
        Args:
            school_id: School identifier
            expense_id: Expense to pay
            amount_paid: Amount being paid
            paid_by: User recording payment
            payment_date: Date of payment
            
        Returns:
            Updated expense dictionary
        """
        try:
            result = await self.session.execute(
                select(Expense).where(
                    and_(
                        Expense.id == expense_id,
                        Expense.school_id == school_id
                    )
                )
            )
            expense = result.scalar_one_or_none()
            
            if not expense:
                raise ExpenseError(f"Expense {expense_id} not found")
            
            if amount_paid <= 0:
                raise ExpenseValidationError("Payment amount must be positive")
            
            total_paid = expense.amount_paid + amount_paid
            if total_paid > expense.amount:
                raise ExpenseValidationError(
                    f"Payment exceeds expense amount (expense: {expense.amount}, total paid: {total_paid})"
                )
            
            expense.amount_paid = total_paid
            expense.paid_by = paid_by
            expense.payment_date = payment_date
            
            # Update payment status
            remaining = expense.amount - total_paid
            if remaining < 0.01:  # Account for rounding
                expense.payment_status = PaymentStatus.PAID.value
            elif total_paid > 0.01:
                expense.payment_status = PaymentStatus.PARTIAL.value
            else:
                expense.payment_status = PaymentStatus.OUTSTANDING.value
            
            expense.updated_at = datetime.utcnow()
            self.session.add(expense)
            await self.session.commit()
            
            logger.info(f"Recorded {amount_paid} payment for expense {expense_id}")
            return await self._expense_to_dict(expense)
        except (ExpenseError, ExpenseValidationError):
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error recording payment: {str(e)}")
            raise ExpenseError(f"Error recording payment: {str(e)}")
    
    async def get_expense_summary(
        self,
        school_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get expense summary statistics
        
        Args:
            school_id: School identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Summary dictionary with counts and totals
        """
        try:
            query = select(Expense).where(
                Expense.school_id == school_id
            )
            
            if start_date:
                query = query.where(Expense.expense_date >= start_date)
            if end_date:
                query = query.where(Expense.expense_date <= end_date)
            
            result = await self.session.execute(query)
            expenses = result.scalars().all()
            
            summary = {
                "total_expenses": len(expenses),
                "draft_count": 0,
                "pending_count": 0,
                "approved_count": 0,
                "posted_count": 0,
                "rejected_count": 0,
                "total_amount": 0.0,
                "total_paid": 0.0,
                "outstanding_amount": 0.0,
                "by_category": {}
            }
            
            for expense in expenses:
                # Count by status
                if expense.status == ExpenseStatus.DRAFT:
                    summary["draft_count"] += 1
                elif expense.status == ExpenseStatus.PENDING:
                    summary["pending_count"] += 1
                elif expense.status == ExpenseStatus.APPROVED:
                    summary["approved_count"] += 1
                elif expense.status == ExpenseStatus.POSTED:
                    summary["posted_count"] += 1
                elif expense.status == ExpenseStatus.REJECTED:
                    summary["rejected_count"] += 1
                
                # Totals
                summary["total_amount"] += expense.amount
                summary["total_paid"] += expense.amount_paid
                summary["outstanding_amount"] += (expense.amount - expense.amount_paid)
                
                # By category
                cat = expense.category.value
                if cat not in summary["by_category"]:
                    summary["by_category"][cat] = {
                        "count": 0,
                        "total_amount": 0.0,
                        "total_paid": 0.0
                    }
                summary["by_category"][cat]["count"] += 1
                summary["by_category"][cat]["total_amount"] += expense.amount
                summary["by_category"][cat]["total_paid"] += expense.amount_paid
            
            return summary
        except Exception as e:
            logger.error(f"Error generating expense summary: {str(e)}")
            raise ExpenseError(f"Error generating expense summary: {str(e)}")
    
    async def _create_expense_journal_entry(
        self,
        school_id: str,
        expense: Expense,
        posted_by: str,
    ) -> str:
        """Create and post GL journal entry for expense
        
        Posts:
        - Dr. Expense GL account: amount
        - Cr. Bank account (1010): amount
        
        Args:
            school_id: School identifier
            expense: Expense to post
            posted_by: User posting
            
        Returns:
            Journal entry ID
            
        Raises:
            Exception: If GL accounts not found
        """
        from services.journal_entry_service import JournalEntryService
        
        # Get expense GL account
        if not expense.gl_account_id:
            raise ExpenseError(f"Expense has no GL account assigned")
        
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.id == expense.gl_account_id,
                    GLAccount.school_id == school_id,
                    GLAccount.is_active == True
                )
            )
        )
        expense_account = result.scalar_one_or_none()
        
        if not expense_account:
            raise ExpenseError(f"GL account {expense.gl_account_id} not found or inactive")
        
        # Get bank account (1010)
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "1010",
                    GLAccount.is_active == True
                )
            )
        )
        bank_account = result.scalar_one_or_none()
        
        if not bank_account:
            raise ExpenseError("GL Account 1010 (Business Checking Account) not found or inactive")
        
        # Build journal entry
        journal_line_items = [
            # Debit: Expense account
            JournalLineItemCreate(
                gl_account_id=expense_account.id,
                debit_amount=float(expense.amount),
                credit_amount=0.0,
                description=f"{expense.category.value}: {expense.description}",
            ),
            # Credit: Bank account
            JournalLineItemCreate(
                gl_account_id=bank_account.id,
                debit_amount=0.0,
                credit_amount=float(expense.amount),
                description=f"Payment for {expense.description}",
            ),
        ]
        
        entry_data = JournalEntryCreate(
            entry_date=expense.expense_date,
            reference_type=ReferenceType.EXPENSE,
            reference_id=expense.id,
            description=f"Expense: {expense.description}",
            line_items=journal_line_items,
            notes=f"Expense from {expense.vendor_name or 'vendor'}" if expense.vendor_name else "Expense posting",
        )
        
        # Create and post entry
        journal_service = JournalEntryService(self.session)
        entry = await journal_service.create_entry(
            school_id=school_id,
            entry_data=entry_data,
            created_by="SYSTEM",
        )
        
        posted_entry = await journal_service.post_entry(
            school_id=school_id,
            entry_id=entry.id,
            posted_by="SYSTEM",
            approval_notes="Auto-posted from expense",
        )
        
        return posted_entry.id
    
    async def _expense_to_dict(self, expense: Expense) -> Dict[str, Any]:
        """Convert Expense object to dictionary"""
        return {
            "id": expense.id,
            "school_id": expense.school_id,
            "category": expense.category,
            "description": expense.description,
            "vendor_name": expense.vendor_name,
            "amount": expense.amount,
            "currency": expense.currency,
            "gl_account_id": expense.gl_account_id,
            "gl_account_code": expense.gl_account_code,
            "expense_date": expense.expense_date,
            "status": expense.status,
            "payment_status": expense.payment_status,
            "amount_paid": expense.amount_paid,
            "submitted_by": expense.submitted_by,
            "submitted_at": expense.submitted_at,
            "approved_by": expense.approved_by,
            "approved_date": expense.approved_date,
            "rejected_reason": expense.rejected_reason,
            "journal_entry_id": expense.journal_entry_id,
            "notes": expense.notes,
            "created_by": expense.created_by,
            "created_at": expense.created_at,
            "updated_at": expense.updated_at,
        }
