"""Payroll Service for salary calculation and payroll run generation"""
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_
from decimal import Decimal

from models.payroll import (
    PayrollContract, PayrollRun, PayrollRunCreate, PayrollLineItem,
    PayrollAdjustment, PayrollStatus, PayrollCategory
)
from models.staff import Staff, StaffStatus
from models.user import User
from models.finance import (
    JournalEntryCreate, JournalLineItemCreate, ReferenceType
)
from services.deduction_rules_service import RulesEvaluationService

logger = logging.getLogger(__name__)


class PayrollCalculationError(Exception):
    """Raised when payroll calculation encounters an error"""
    pass


class PayrollService:
    """Service for payroll calculations and run generation"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ==================== Helper Methods ====================
    
    async def get_active_contract(self, school_id: str, staff_id: str) -> Optional[PayrollContract]:
        """
        Get the active payroll contract for a staff member on the current date.
        
        Args:
            school_id: School identifier
            staff_id: Staff member identifier
            
        Returns:
            PayrollContract if found and active, None otherwise
        """
        try:
            result = await self.session.execute(
                select(PayrollContract).where(
                    PayrollContract.school_id == school_id,
                    PayrollContract.staff_id == staff_id,
                    PayrollContract.is_active == True,
                    PayrollContract.effective_from <= datetime.utcnow(),
                    (PayrollContract.effective_to.is_(None) | 
                     (PayrollContract.effective_to >= datetime.utcnow()))
                ).order_by(PayrollContract.effective_from.desc())
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching active contract for staff {staff_id}: {str(e)}")
            return None
    
    async def get_staff_by_id(self, staff_id: str, school_id: str) -> Optional[Staff]:
        """Get staff member by ID and school"""
        try:
            result = await self.session.execute(
                select(Staff).where(
                    Staff.id == staff_id,
                    Staff.school_id == school_id
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching staff {staff_id}: {str(e)}")
            return None
    
    # ==================== Calculation Methods ====================
    
    def calculate_allowances(self, contract: PayrollContract) -> Tuple[float, Dict[str, float]]:
        """
        Calculate total allowances from contract.
        
        Args:
            contract: PayrollContract instance
            
        Returns:
            Tuple of (total_allowances, breakdown_dict)
        """
        breakdown = {
            "housing": float(contract.allowance_housing),
            "transport": float(contract.allowance_transport),
            "meals": float(contract.allowance_meals),
            "utilities": float(contract.allowance_utilities),
            "other": float(contract.allowance_other),
        }
        
        total = sum(breakdown.values())
        return total, breakdown
    
    def calculate_gross_amount(self, contract: PayrollContract) -> Tuple[float, Dict[str, float]]:
        """
        Calculate gross amount (basic + allowances).
        
        Args:
            contract: PayrollContract instance
            
        Returns:
            Tuple of (gross_amount, components_dict)
        """
        basic_salary = float(contract.basic_salary)
        total_allowances, allowance_breakdown = self.calculate_allowances(contract)
        
        gross = basic_salary + total_allowances
        
        components = {
            "basic_salary": basic_salary,
            "total_allowances": total_allowances,
            "allowances_breakdown": allowance_breakdown,
            "gross_amount": gross
        }
        
        return gross, components
    
    def calculate_tax(self, gross_amount: float, tax_rate_percent: float) -> float:
        """
        Calculate income tax based on gross amount and tax rate.
        
        Args:
            gross_amount: Total gross salary
            tax_rate_percent: Tax rate as percentage (e.g., 15.0 for 15%)
            
        Returns:
            Tax amount
        """
        if tax_rate_percent < 0 or tax_rate_percent > 100:
            raise PayrollCalculationError(f"Invalid tax rate: {tax_rate_percent}")
        
        return (gross_amount * tax_rate_percent) / 100.0
    
    def calculate_pension(self, gross_amount: float, pension_rate_percent: float) -> float:
        """
        Calculate pension contribution.
        
        Args:
            gross_amount: Total gross salary
            pension_rate_percent: Pension rate as percentage
            
        Returns:
            Pension amount
        """
        if pension_rate_percent < 0 or pension_rate_percent > 100:
            raise PayrollCalculationError(f"Invalid pension rate: {pension_rate_percent}")
        
        return (gross_amount * pension_rate_percent) / 100.0
    
    def calculate_nssf(self, gross_amount: float, nssf_rate_percent: float) -> float:
        """
        Calculate NSSF (National Social Security Fund) contribution.
        
        Args:
            gross_amount: Total gross salary
            nssf_rate_percent: NSSF rate as percentage
            
        Returns:
            NSSF amount
        """
        if nssf_rate_percent < 0 or nssf_rate_percent > 100:
            raise PayrollCalculationError(f"Invalid NSSF rate: {nssf_rate_percent}")
        
        return (gross_amount * nssf_rate_percent) / 100.0
    
    def calculate_deductions(
        self, 
        gross_amount: float, 
        contract: PayrollContract
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate total deductions (tax, pension, NSSF, other).
        
        Args:
            gross_amount: Total gross salary
            contract: PayrollContract with deduction rates
            
        Returns:
            Tuple of (total_deductions, breakdown_dict)
        """
        tax_amount = self.calculate_tax(gross_amount, contract.tax_rate_percent)
        pension_amount = self.calculate_pension(gross_amount, contract.pension_rate_percent)
        nssf_amount = self.calculate_nssf(gross_amount, contract.nssf_rate_percent)
        other_deductions = float(contract.other_deduction)
        
        total = tax_amount + pension_amount + nssf_amount + other_deductions
        
        breakdown = {
            "tax": tax_amount,
            "pension": pension_amount,
            "nssf": nssf_amount,
            "other": other_deductions,
        }
        
        return total, breakdown
    
    def calculate_net_amount(self, gross_amount: float, total_deductions: float) -> float:
        """
        Calculate net amount (gross - deductions).
        
        Args:
            gross_amount: Total gross salary
            total_deductions: Total deductions
            
        Returns:
            Net amount
        """
        net = gross_amount - total_deductions
        return max(net, 0.0)  # Ensure net is never negative
    
    def calculate_payroll_for_staff(
        self, 
        contract: PayrollContract,
        adjustments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete payroll for a staff member.
        
        Args:
            contract: PayrollContract for the staff
            adjustments: Optional list of adjustments (bonus/penalty)
            
        Returns:
            Dictionary with calculated payroll details
        """
        # Calculate components
        basic_salary = float(contract.basic_salary)
        total_allowances, allowance_breakdown = self.calculate_allowances(contract)
        gross_amount, gross_components = self.calculate_gross_amount(contract)
        total_deductions, deduction_breakdown = self.calculate_deductions(gross_amount, contract)
        net_amount = self.calculate_net_amount(gross_amount, total_deductions)
        
        # Apply adjustments if any
        total_adjustments = 0.0
        adjustment_details = {}
        if adjustments:
            for adj in adjustments:
                amount = float(adj.get("amount", 0.0))
                adj_type = adj.get("adjustment_type", "other")
                total_adjustments += amount
                adjustment_details[adj_type] = adjustment_details.get(adj_type, 0.0) + amount
        
        # Final net (after adjustments)
        final_net = net_amount + total_adjustments
        
        return {
            "basic_salary": basic_salary,
            "total_allowances": total_allowances,
            "allowance_breakdown": allowance_breakdown,
            "gross_amount": gross_amount,
            "tax_amount": deduction_breakdown["tax"],
            "pension_amount": deduction_breakdown["pension"],
            "nssf_amount": deduction_breakdown["nssf"],
            "other_deductions": deduction_breakdown["other"],
            "total_deductions": total_deductions,
            "net_amount": net_amount,
            "adjustments": adjustment_details,
            "total_adjustments": total_adjustments,
            "final_net": final_net,
            "breakdown": {
                "allowances": allowance_breakdown,
                "deductions": deduction_breakdown,
                "adjustments": adjustment_details
            }
        }
    
    # ==================== Payroll Run Generation ====================
    
    async def get_active_staff_for_school(
        self, 
        school_id: str
    ) -> List[Staff]:
        """
        Get all active staff members for a school.
        
        Args:
            school_id: School identifier
            
        Returns:
            List of active Staff members
        """
        try:
            result = await self.session.execute(
                select(Staff).where(
                    Staff.school_id == school_id,
                    Staff.status == StaffStatus.ACTIVE
                ).order_by(Staff.first_name)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching active staff for school {school_id}: {str(e)}")
            return []
    
    async def get_existing_payroll_run(
        self,
        school_id: str,
        year: int,
        month: int
    ) -> Optional[PayrollRun]:
        """
        Check if payroll run already exists for a period.
        
        Args:
            school_id: School identifier
            year: Payroll year
            month: Payroll month
            
        Returns:
            PayrollRun if exists, None otherwise
        """
        try:
            result = await self.session.execute(
                select(PayrollRun).where(
                    PayrollRun.school_id == school_id,
                    PayrollRun.period_year == year,
                    PayrollRun.period_month == month
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error checking existing payroll run: {str(e)}")
            return None
    
    def get_period_name(self, year: int, month: int) -> str:
        """Generate readable period name from year and month"""
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        try:
            month_name = months[month - 1] if 1 <= month <= 12 else f"Month {month}"
            return f"{month_name} {year}"
        except IndexError:
            return f"Period {month}/{year}"
    
    async def generate_payroll_run(
        self,
        school_id: str,
        year: int,
        month: int,
        current_user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate payroll run for a school for a given month.
        
        Args:
            school_id: School identifier
            year: Payroll year
            month: Payroll month (1-12)
            current_user: User generating the payroll
            notes: Optional notes for the payroll run
            
        Returns:
            Dictionary with payroll run details and status
        """
        try:
            # Validate month
            if not 1 <= month <= 12:
                raise PayrollCalculationError(f"Invalid month: {month}. Must be 1-12.")
            
            # Check if payroll already exists for this period
            existing = await self.get_existing_payroll_run(school_id, year, month)
            if existing:
                return {
                    "success": False,
                    "message": f"Payroll already exists for {self.get_period_name(year, month)}",
                    "payroll_run": None,
                    "errors": [f"Payroll run status: {existing.status}"]
                }
            
            # Get active staff
            staff_list = await self.get_active_staff_for_school(school_id)
            if not staff_list:
                return {
                    "success": False,
                    "message": "No active staff found for this school",
                    "payroll_run": None,
                    "errors": []
                }
            
            # Create payroll run
            period_name = self.get_period_name(year, month)
            payroll_run = PayrollRun(
                school_id=school_id,
                period_year=year,
                period_month=month,
                period_name=period_name,
                status=PayrollStatus.DRAFT,
                generated_by=current_user.id,
                notes=notes
            )
            self.session.add(payroll_run)
            await self.session.flush()
            
            # Generate line items for each staff
            total_gross = 0.0
            total_allowances = 0.0
            total_deductions = 0.0
            total_net = 0.0
            line_items_created = 0
            errors = []
            
            # Initialize rules service for deduction rule evaluation
            rules_service = RulesEvaluationService(self.session)
            
            for staff in staff_list:
                try:
                    # Get active contract for staff
                    contract = await self.get_active_contract(school_id, staff.id)
                    if not contract:
                        errors.append(f"No active contract for {staff.first_name} {staff.last_name}")
                        continue
                    
                    # Calculate payroll for this staff
                    calculation = self.calculate_payroll_for_staff(contract)
                    
                    # Prepare metadata for rule evaluation
                    staff_metadata = {
                        "staff_id": staff.id,
                        "basic_salary": float(contract.basic_salary),
                        "years_service": 0,  # TODO: Calculate from employment date
                        "absent_days": 0,  # TODO: Get from attendance records
                        "present_days": 0  # TODO: Get from attendance records
                    }
                    
                    # Apply deduction rules
                    applied_rules = []
                    rule_deductions = 0.0
                    try:
                        rule_results = await rules_service.evaluate_rules_for_staff(
                            staff_id=staff.id,
                            basic_salary=float(contract.basic_salary),
                            period_year=year,
                            period_month=month,
                            staff_metadata=staff_metadata
                        )
                        
                        for result in rule_results:
                            if result.matched:
                                applied_rules.append({
                                    "rule_id": result.rule_id,
                                    "rule_name": result.rule_name,
                                    "deduction_amount": result.deduction_amount,
                                    "category": result.deduction_category
                                })
                                rule_deductions += result.deduction_amount
                    except Exception as e:
                        logger.warning(f"Error evaluating rules for staff {staff.id}: {str(e)}")
                        # Continue without rules if error occurs
                    
                    # Add rule deductions to total
                    total_rule_deductions = rule_deductions
                    calculation["total_deductions"] += total_rule_deductions
                    calculation["net_amount"] = calculation["gross_amount"] - calculation["total_deductions"]
                    calculation["breakdown"]["applied_rules"] = applied_rules
                    calculation["breakdown"]["rule_deductions"] = total_rule_deductions
                    
                    # Create line item
                    line_item = PayrollLineItem(
                        payroll_run_id=payroll_run.id,
                        school_id=school_id,
                        staff_id=staff.id,
                        basic_salary=calculation["basic_salary"],
                        total_allowances=calculation["total_allowances"],
                        gross_amount=calculation["gross_amount"],
                        tax_amount=calculation["tax_amount"],
                        pension_amount=calculation["pension_amount"],
                        nssf_amount=calculation["nssf_amount"],
                        other_deductions=calculation["other_deductions"],
                        total_deductions=calculation["total_deductions"],
                        net_amount=calculation["net_amount"],
                        breakdown=json.dumps(calculation["breakdown"])
                    )
                    self.session.add(line_item)
                    
                    # Accumulate totals
                    total_gross += calculation["gross_amount"]
                    total_allowances += calculation["total_allowances"]
                    total_deductions += calculation["total_deductions"]
                    total_net += calculation["net_amount"]
                    line_items_created += 1
                    
                except Exception as e:
                    errors.append(f"Error calculating payroll for {staff.first_name} {staff.last_name}: {str(e)}")
                    logger.error(f"Error in payroll calculation: {str(e)}")
            
            # Update payroll run totals
            payroll_run.total_gross = total_gross
            payroll_run.total_allowances = total_allowances
            payroll_run.total_deductions = total_deductions
            payroll_run.total_net = total_net
            payroll_run.staff_count = line_items_created
            payroll_run.status = PayrollStatus.GENERATED if line_items_created > 0 else PayrollStatus.DRAFT
            
            self.session.add(payroll_run)
            await self.session.commit()
            
            return {
                "success": len(errors) == 0,
                "message": f"Payroll generated for {period_name} with {line_items_created} staff",
                "payroll_run": {
                    "id": payroll_run.id,
                    "school_id": payroll_run.school_id,
                    "period_name": payroll_run.period_name,
                    "status": payroll_run.status,
                    "staff_count": payroll_run.staff_count,
                    "total_gross": payroll_run.total_gross,
                    "total_allowances": payroll_run.total_allowances,
                    "total_deductions": payroll_run.total_deductions,
                    "total_net": payroll_run.total_net,
                    "created_at": payroll_run.created_at.isoformat()
                },
                "errors": errors,
                "success_count": line_items_created
            }
            
        except PayrollCalculationError as e:
            logger.error(f"Payroll calculation error: {str(e)}")
            return {
                "success": False,
                "message": f"Payroll generation failed: {str(e)}",
                "payroll_run": None,
                "errors": [str(e)]
            }
        except Exception as e:
            logger.error(f"Unexpected error generating payroll: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "message": f"Payroll generation failed: {str(e)}",
                "payroll_run": None,
                "errors": [str(e)]
            }
    
    # ==================== Payroll Run Management ====================
    
    async def approve_payroll_run(
        self,
        school_id: str,
        payroll_run_id: str,
        current_user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve a payroll run (move from GENERATED to APPROVED status).
        
        Args:
            school_id: School identifier
            payroll_run_id: Payroll run identifier
            current_user: User approving the payroll
            notes: Optional approval notes
            
        Returns:
            Status dictionary
        """
        try:
            result = await self.session.execute(
                select(PayrollRun).where(
                    PayrollRun.id == payroll_run_id,
                    PayrollRun.school_id == school_id
                )
            )
            payroll_run = result.scalar_one_or_none()
            
            if not payroll_run:
                return {
                    "success": False,
                    "message": "Payroll run not found"
                }
            
            if payroll_run.status != PayrollStatus.GENERATED:
                return {
                    "success": False,
                    "message": f"Cannot approve payroll in {payroll_run.status} status"
                }
            
            payroll_run.status = PayrollStatus.APPROVED
            payroll_run.approved_by = current_user.id
            payroll_run.approved_at = datetime.utcnow()
            if notes:
                payroll_run.notes = notes
            
            self.session.add(payroll_run)
            await self.session.commit()
            
            return {
                "success": True,
                "message": f"Payroll run approved",
                "payroll_run_id": payroll_run.id,
                "status": payroll_run.status
            }
            
        except Exception as e:
            logger.error(f"Error approving payroll run: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "message": f"Error approving payroll: {str(e)}"
            }
    
    async def post_payroll_run(
        self,
        school_id: str,
        payroll_run_id: str
    ) -> Dict[str, Any]:
        """
        Post a payroll run (move from APPROVED to POSTED status, final state).
        
        Also creates a journal entry to GL for the payroll posting:
        - Dr. 5100 (Salaries and Wages): Gross salary amount
        - Cr. 2100 (Salaries Payable): Net salary to be paid
        - Cr. 2110/2120/2130: Deductions (NSSF, Pension, Tax)
        
        Args:
            school_id: School identifier
            payroll_run_id: Payroll run identifier
            
        Returns:
            Status dictionary with payroll_run_id and journal_entry_id if successful
        """
        try:
            # Get the payroll run
            result = await self.session.execute(
                select(PayrollRun).where(
                    PayrollRun.id == payroll_run_id,
                    PayrollRun.school_id == school_id
                )
            )
            payroll_run = result.scalar_one_or_none()
            
            if not payroll_run:
                return {
                    "success": False,
                    "message": "Payroll run not found"
                }
            
            if payroll_run.status != PayrollStatus.APPROVED:
                return {
                    "success": False,
                    "message": f"Cannot post payroll in {payroll_run.status} status"
                }
            
            # Create GL journal entry for payroll posting
            journal_entry_id = None
            try:
                journal_entry_id = await self._create_payroll_journal_entry(
                    school_id=school_id,
                    payroll_run=payroll_run,
                )
                logger.info(f"Created journal entry {journal_entry_id} for payroll run {payroll_run_id}")
            except Exception as e:
                logger.error(f"Error creating journal entry for payroll: {str(e)}")
                # Continue posting even if GL entry fails (data consistency is paramount)
                # But log the error for manual reconciliation
            
            # Update payroll run status
            payroll_run.status = PayrollStatus.POSTED
            payroll_run.posted_at = datetime.utcnow()
            
            self.session.add(payroll_run)
            await self.session.commit()
            
            response = {
                "success": True,
                "message": "Payroll run posted successfully",
                "payroll_run_id": payroll_run.id,
                "status": payroll_run.status
            }
            
            if journal_entry_id:
                response["journal_entry_id"] = journal_entry_id
            
            return response
            
        except Exception as e:
            logger.error(f"Error posting payroll run: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "message": f"Error posting payroll: {str(e)}"
            }
    
    async def _create_payroll_journal_entry(
        self,
        school_id: str,
        payroll_run: PayrollRun,
    ) -> str:
        """
        Create a journal entry for payroll posting to GL.
        
        Posts:
        - Dr. 5100 (Salaries and Wages): total_gross
        - Cr. 2100 (Salaries Payable): total_net
        - Cr. 2110 (NSSF Payable): NSSF portion of total_deductions
        - Cr. 2120 (Pension Payable): Pension portion of total_deductions
        - Cr. 2130 (Income Tax Withheld Payable): Tax portion of total_deductions
        
        Args:
            school_id: School identifier
            payroll_run: PayrollRun instance with totals
            
        Returns:
            Journal entry ID
            
        Raises:
            Exception: If GL account not found or other GL errors
        """
        from services.journal_entry_service import JournalEntryService
        from models.finance.chart_of_accounts import GLAccount
        
        # Get GL accounts needed for payroll posting
        # Debit: 5100 (Salaries and Wages)
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "5100",
                    GLAccount.is_active == True
                )
            )
        )
        salary_expense_account = result.scalar_one_or_none()
        
        if not salary_expense_account:
            raise Exception("GL Account 5100 (Salaries and Wages) not found or inactive")
        
        # Credit accounts needed
        # 2100 (Salaries Payable) - for net payable
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "2100",
                    GLAccount.is_active == True
                )
            )
        )
        salaries_payable_account = result.scalar_one_or_none()
        
        if not salaries_payable_account:
            raise Exception("GL Account 2100 (Salaries Payable) not found or inactive")
        
        # 2110 (NSSF Payable)
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "2110",
                    GLAccount.is_active == True
                )
            )
        )
        nssf_payable_account = result.scalar_one_or_none()
        
        if not nssf_payable_account:
            raise Exception("GL Account 2110 (NSSF Payable) not found or inactive")
        
        # 2120 (Pension Payable)
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "2120",
                    GLAccount.is_active == True
                )
            )
        )
        pension_payable_account = result.scalar_one_or_none()
        
        if not pension_payable_account:
            raise Exception("GL Account 2120 (Pension Payable) not found or inactive")
        
        # 2130 (Income Tax Withheld Payable)
        result = await self.session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == "2130",
                    GLAccount.is_active == True
                )
            )
        )
        tax_payable_account = result.scalar_one_or_none()
        
        if not tax_payable_account:
            raise Exception("GL Account 2130 (Income Tax Withheld Payable) not found or inactive")
        
        # Get payroll line items to calculate deduction breakdown by type
        result = await self.session.execute(
            select(PayrollLineItem).where(
                PayrollLineItem.payroll_run_id == payroll_run.id,
                PayrollLineItem.school_id == school_id
            )
        )
        line_items = result.scalars().all()
        
        # Calculate deduction breakdown from line items
        total_nssf = 0.0
        total_pension = 0.0
        total_tax = 0.0
        total_other = 0.0
        
        for line_item in line_items:
            total_nssf += float(line_item.nssf_amount or 0.0)
            total_pension += float(line_item.pension_amount or 0.0)
            total_tax += float(line_item.tax_amount or 0.0)
            total_other += float(line_item.other_deductions or 0.0)
        
        # Verify calculation: all deductions should sum to total_deductions
        calculated_total_deductions = total_nssf + total_pension + total_tax + total_other
        
        # Build line items for journal entry
        journal_line_items = [
            # Debit: Salary Expense
            JournalLineItemCreate(
                gl_account_id=salary_expense_account.id,
                debit_amount=float(payroll_run.total_gross),
                credit_amount=0.0,
                description=f"Payroll for {payroll_run.period_name}: Salaries",
            ),
            # Credit: Salaries Payable (net to be paid to staff)
            # Note: This includes all deductions, including other_deductions
            JournalLineItemCreate(
                gl_account_id=salaries_payable_account.id,
                debit_amount=0.0,
                credit_amount=float(payroll_run.total_net),
                description=f"Payroll for {payroll_run.period_name}: Net salary payable",
            ),
        ]
        
        # Add deduction credits for known accounts
        # These represent liabilities to be paid to third parties
        remaining_deductions = calculated_total_deductions  # Sum of all deductions
        
        if total_nssf > 0.01:
            journal_line_items.append(
                JournalLineItemCreate(
                    gl_account_id=nssf_payable_account.id,
                    debit_amount=0.0,
                    credit_amount=total_nssf,
                    description=f"Payroll for {payroll_run.period_name}: NSSF contributions",
                )
            )
            remaining_deductions -= total_nssf
        
        if total_pension > 0.01:
            journal_line_items.append(
                JournalLineItemCreate(
                    gl_account_id=pension_payable_account.id,
                    debit_amount=0.0,
                    credit_amount=total_pension,
                    description=f"Payroll for {payroll_run.period_name}: Pension contributions",
                )
            )
            remaining_deductions -= total_pension
        
        if total_tax > 0.01:
            journal_line_items.append(
                JournalLineItemCreate(
                    gl_account_id=tax_payable_account.id,
                    debit_amount=0.0,
                    credit_amount=total_tax,
                    description=f"Payroll for {payroll_run.period_name}: Income tax withheld",
                )
            )
            remaining_deductions -= total_tax
        
        # Any remaining deductions (other_deductions) are retained/internal adjustments
        # They reduce the expense posting
        if remaining_deductions > 0.01:
            # Reduce the initial salary expense debit by the unaccounted deductions
            journal_line_items[0].debit_amount = float(journal_line_items[0].debit_amount) - remaining_deductions
        
        # Create the journal entry
        entry_data = JournalEntryCreate(
            entry_date=payroll_run.posted_at or datetime.utcnow(),
            reference_type=ReferenceType.PAYROLL_RUN,
            reference_id=payroll_run.id,
            description=f"Payroll posting for {payroll_run.period_name}",
            line_items=journal_line_items,
            notes=f"Auto-posted from payroll run {payroll_run.id}",
        )
        
        # Use JournalEntryService to create and post the entry
        journal_service = JournalEntryService(self.session)
        entry = await journal_service.create_entry(
            school_id=school_id,
            entry_data=entry_data,
            created_by="SYSTEM",  # Mark as system-generated
        )
        
        # Post the entry immediately (auto-posting)
        posted_entry = await journal_service.post_entry(
            school_id=school_id,
            entry_id=entry.id,
            posted_by="SYSTEM",
            approval_notes="Auto-posted from payroll run",
        )
        
        return posted_entry.id
