"""Payroll Service for salary calculation and payroll run generation"""
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
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
            try:
                await self.session.flush()
            except IntegrityError:
                # uq_payroll_run_school_period hit: a concurrent request
                # generated this exact period between our check above and
                # this insert. The check catches the sequential case; this
                # catches the race.
                await self.session.rollback()
                return {
                    "success": False,
                    "message": f"Payroll already exists for {period_name}",
                    "payroll_run": None,
                    "errors": ["Concurrent payroll generation detected"]
                }

            # Generate line items for each staff
            total_gross = 0.0
            total_allowances = 0.0
            total_deductions = 0.0
            total_net = 0.0
            line_items_created = 0
            errors = []
            
            # Initialize rules service for deduction rule evaluation
            rules_service = RulesEvaluationService(self.session, school_id)
            
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
                        rule_results, total_rule_deductions = await rules_service.evaluate_rules_for_staff(
                            staff_id=staff.id,
                            basic_salary=float(contract.basic_salary),
                            period_year=year,
                            period_month=month,
                            staff_metadata=staff_metadata
                        )
                        
                        for result in rule_results:
                            applied_rules.append({
                                "rule_id": result.rule_id,
                                "rule_name": result.rule_name,
                                "deduction_amount": result.deduction_amount,
                                "category": result.deduction_type
                            })
                        rule_deductions = total_rule_deductions
                    except Exception as e:
                        logger.warning(f"Error evaluating rules for staff {staff.id}: {str(e)}")
                        # Continue without rules if error occurs
                    
                    # Add rule deductions to total. Reapply the same zero-floor
                    # calculate_net_amount() used above — otherwise heavy rule
                    # deductions can push this staff member's net_amount
                    # negative, which then silently understates
                    # payroll_run.total_net (and the GL credit to Salaries
                    # Payable) by that same amount.
                    calculation["total_deductions"] += rule_deductions
                    calculation["net_amount"] = self.calculate_net_amount(
                        calculation["gross_amount"], calculation["total_deductions"]
                    )
                    calculation["breakdown"]["applied_rules"] = applied_rules
                    calculation["breakdown"]["rule_deductions"] = rule_deductions
                    
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
    
    # ==================== Payroll Adjustments ====================
    # Bonus/penalty/advance-recovery adjustments against a specific staff
    # member's line item on a specific run. Created as pending; only
    # approved adjustments affect net_amount, so an unreviewed bonus can
    # never accidentally hit take-home pay. Only allowed while the run is
    # still DRAFT/GENERATED — once a run is APPROVED its numbers are meant
    # to be final, matching why reject_payroll_run exists as the one way
    # back to an editable state.

    async def create_adjustment(
        self,
        school_id: str,
        payroll_run_id: str,
        staff_id: str,
        adjustment_type: str,
        amount: float,
        reason: str,
        created_by: str,
    ) -> Dict[str, Any]:
        """Create a pending adjustment against a staff member's line item."""
        try:
            run_result = await self.session.execute(
                select(PayrollRun).where(
                    PayrollRun.id == payroll_run_id, PayrollRun.school_id == school_id
                )
            )
            run = run_result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Payroll run not found"}

            if run.status not in (PayrollStatus.DRAFT, PayrollStatus.GENERATED):
                return {
                    "success": False,
                    "error": f"Cannot add adjustments to a run in {run.status} status — reject it back to draft first",
                }

            line_result = await self.session.execute(
                select(PayrollLineItem).where(
                    PayrollLineItem.payroll_run_id == payroll_run_id,
                    PayrollLineItem.staff_id == staff_id,
                )
            )
            if not line_result.scalar_one_or_none():
                return {"success": False, "error": "Staff member has no line item on this run"}

            adjustment = PayrollAdjustment(
                payroll_run_id=payroll_run_id,
                school_id=school_id,
                staff_id=staff_id,
                adjustment_type=adjustment_type,
                amount=amount,
                reason=reason,
                created_by=created_by,
            )
            self.session.add(adjustment)
            await self.session.commit()
            await self.session.refresh(adjustment)

            return {
                "success": True,
                "adjustment_id": adjustment.id,
                "message": "Adjustment created, pending approval",
            }

        except Exception as e:
            logger.error(f"Error creating payroll adjustment: {str(e)}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def list_adjustments(
        self,
        school_id: str,
        payroll_run_id: Optional[str] = None,
        staff_id: Optional[str] = None,
    ) -> List[PayrollAdjustment]:
        """List adjustments, optionally filtered by run and/or staff member."""
        query = select(PayrollAdjustment).where(PayrollAdjustment.school_id == school_id)
        if payroll_run_id:
            query = query.where(PayrollAdjustment.payroll_run_id == payroll_run_id)
        if staff_id:
            query = query.where(PayrollAdjustment.staff_id == staff_id)
        query = query.order_by(PayrollAdjustment.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def approve_adjustment(
        self,
        school_id: str,
        adjustment_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Approve a pending adjustment and fold it into the line item's
        net_amount immediately.

        Recomputes total_adjustments/net_amount from scratch off ALL
        approved adjustments for this (run, staff) pair rather than
        incrementing — idempotent and self-correcting regardless of
        approval order, and immune to drift if this is ever called twice.
        """
        try:
            adj_result = await self.session.execute(
                select(PayrollAdjustment).where(
                    PayrollAdjustment.id == adjustment_id,
                    PayrollAdjustment.school_id == school_id,
                )
            )
            adjustment = adj_result.scalar_one_or_none()
            if not adjustment:
                return {"success": False, "error": "Adjustment not found"}

            if adjustment.approved_by is not None:
                return {"success": False, "error": "Adjustment already approved"}

            run_result = await self.session.execute(
                select(PayrollRun).where(PayrollRun.id == adjustment.payroll_run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run or run.status not in (PayrollStatus.DRAFT, PayrollStatus.GENERATED):
                return {
                    "success": False,
                    "error": "Cannot approve an adjustment on a run that is no longer draft/generated",
                }

            # Lock the line item: two adjustments for the same staff member
            # being approved concurrently must not race each other's
            # from-scratch recomputation.
            line_result = await self.session.execute(
                select(PayrollLineItem).where(
                    PayrollLineItem.payroll_run_id == adjustment.payroll_run_id,
                    PayrollLineItem.staff_id == adjustment.staff_id,
                ).with_for_update()
            )
            line_item = line_result.scalar_one_or_none()
            if not line_item:
                return {"success": False, "error": "Staff member has no line item on this run"}

            adjustment.approved_by = approved_by
            adjustment.approved_at = datetime.utcnow()
            adjustment.updated_at = datetime.utcnow()
            self.session.add(adjustment)
            await self.session.flush()

            approved_result = await self.session.execute(
                select(PayrollAdjustment).where(
                    PayrollAdjustment.payroll_run_id == adjustment.payroll_run_id,
                    PayrollAdjustment.staff_id == adjustment.staff_id,
                    PayrollAdjustment.approved_by.is_not(None),
                )
            )
            total_adjustments = sum(float(a.amount) for a in approved_result.scalars().all())

            base_net = max(line_item.gross_amount - line_item.total_deductions, 0.0)
            line_item.total_adjustments = round(total_adjustments, 2)
            line_item.net_amount = round(max(base_net + total_adjustments, 0.0), 2)
            line_item.updated_at = datetime.utcnow()
            self.session.add(line_item)
            await self.session.flush()

            # Roll the run's total_net up from a fresh aggregation of every
            # line item, not an incremental delta — same self-correcting
            # reasoning as the line item recompute above.
            all_lines_result = await self.session.execute(
                select(PayrollLineItem).where(PayrollLineItem.payroll_run_id == adjustment.payroll_run_id)
            )
            run.total_net = round(sum(li.net_amount for li in all_lines_result.scalars().all()), 2)
            run.updated_at = datetime.utcnow()
            self.session.add(run)

            await self.session.commit()

            return {
                "success": True,
                "adjustment_id": adjustment.id,
                "line_item_net_amount": line_item.net_amount,
                "message": "Adjustment approved and applied",
            }

        except Exception as e:
            logger.error(f"Error approving payroll adjustment: {str(e)}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def delete_adjustment(
        self,
        school_id: str,
        adjustment_id: str,
    ) -> Dict[str, Any]:
        """Retract a pending (not yet approved) adjustment."""
        try:
            adj_result = await self.session.execute(
                select(PayrollAdjustment).where(
                    PayrollAdjustment.id == adjustment_id,
                    PayrollAdjustment.school_id == school_id,
                )
            )
            adjustment = adj_result.scalar_one_or_none()
            if not adjustment:
                return {"success": False, "error": "Adjustment not found"}

            if adjustment.approved_by is not None:
                return {"success": False, "error": "Cannot delete an already-approved adjustment"}

            await self.session.delete(adjustment)
            await self.session.commit()
            return {"success": True, "message": "Adjustment deleted"}

        except Exception as e:
            logger.error(f"Error deleting payroll adjustment: {str(e)}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

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

    async def reject_payroll_run(
        self,
        school_id: str,
        payroll_run_id: str,
        current_user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reject a payroll run, sending it back to DRAFT for revision.

        Args:
            school_id: School identifier
            payroll_run_id: Payroll run identifier
            current_user: User rejecting the payroll
            notes: Optional rejection reason

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
                    "message": f"Cannot reject payroll in {payroll_run.status} status"
                }

            payroll_run.status = PayrollStatus.REJECTED
            if notes:
                payroll_run.notes = notes
            payroll_run.updated_at = datetime.utcnow()

            self.session.add(payroll_run)
            await self.session.commit()

            return {
                "success": True,
                "message": "Payroll run rejected",
                "payroll_run_id": payroll_run.id,
                "status": payroll_run.status
            }

        except Exception as e:
            logger.error(f"Error rejecting payroll run: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "message": f"Error rejecting payroll: {str(e)}"
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
            # Get the payroll run. Locked FOR UPDATE so a concurrent second
            # "Post" click (or request retry) blocks here instead of both
            # racing past the status == APPROVED check below and each
            # creating their own GL journal entry for the same payroll run.
            result = await self.session.execute(
                select(PayrollRun)
                .where(
                    PayrollRun.id == payroll_run_id,
                    PayrollRun.school_id == school_id
                )
                .with_for_update()
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
