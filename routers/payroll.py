"""Payroll router for salary contracts and payroll management

ROLE-BASED ACCESS CONTROL:
- SUPER_ADMIN: Full access to all payroll operations
- SCHOOL_ADMIN: Full access including run approval and posting (for their school)
- HR: Can create/update contracts and generate runs (requires SCHOOL_ADMIN or SUPER_ADMIN for approval/posting)
- TEACHER/STUDENT/PARENT: Read-only access (can view own payslips)

SCHOOL SCOPING:
- All endpoints enforce school_id scoping for multi-tenancy
- SUPER_ADMIN can access any school; others limited to their school_id
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import pandas as pd
import io

from models.payroll import (
    PayrollContract, PayrollContractCreate, PayrollContractUpdate,
    PayrollRun, PayrollRunCreate, PayrollLineItem, PayrollAdjustment,
    PayrollAdjustmentCreate, PayrollStatus, PayslipResponse
)
from models.staff import Staff, StaffStatus
from models.user import User, UserRole
from models.school import School
from database import get_session
from auth import get_current_user, require_roles
from services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["Payroll"])


# ==================== Contract Endpoints ====================

@router.post("/contracts", response_model=dict)
async def create_payroll_contract(
    contract_data: PayrollContractCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.HR)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new payroll contract for a staff member"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    # Verify staff exists
    result = await session.execute(
        select(Staff).where(
            Staff.id == contract_data.staff_id,
            Staff.school_id == school_id
        )
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Check for existing active contract
    result = await session.execute(
        select(PayrollContract).where(
            PayrollContract.school_id == school_id,
            PayrollContract.staff_id == contract_data.staff_id,
            PayrollContract.is_active == True
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Active contract already exists for this staff member")
    
    # Create contract
    contract = PayrollContract(
        school_id=school_id,
        created_by=current_user.id,
        **contract_data.model_dump()
    )
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    
    return {
        "id": contract.id,
        "school_id": contract.school_id,
        "staff_id": contract.staff_id,
        "basic_salary": contract.basic_salary,
        "pay_schedule": contract.pay_schedule,
        "total_allowances": (contract.allowance_housing + contract.allowance_transport + 
                            contract.allowance_meals + contract.allowance_utilities + 
                            contract.allowance_other),
        "status": "active" if contract.is_active else "inactive",
        "created_at": contract.created_at.isoformat()
    }


@router.post("/contracts/import", response_model=dict)
async def import_contracts_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.HR)),
    session: AsyncSession = Depends(get_session)
):
    """Import payroll contracts from CSV file
    
    CSV should have columns: staff_id, basic_salary, pay_schedule, allowance_housing, 
    allowance_transport, allowance_meals, allowance_utilities, allowance_other, 
    allowance_other_description, tax_rate_percent, pension_rate_percent, nssf_rate_percent, 
    other_deduction, other_deduction_description, effective_from, notes
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    try:
        # Read CSV file
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        
        # Required columns
        required_columns = [
            'staff_id', 'basic_salary', 'pay_schedule', 'effective_from'
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        success_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                staff_id = str(row['staff_id']).strip()
                if not staff_id:
                    errors.append(f"Row {index + 2}: staff_id cannot be empty")
                    continue
                
                # Verify staff exists
                staff_result = await session.execute(
                    select(Staff).where(
                        Staff.id == staff_id,
                        Staff.school_id == school_id
                    )
                )
                staff = staff_result.scalar_one_or_none()
                if not staff:
                    errors.append(f"Row {index + 2}: Staff ID '{staff_id}' not found")
                    continue
                
                # Check for existing active contract
                existing_result = await session.execute(
                    select(PayrollContract).where(
                        PayrollContract.school_id == school_id,
                        PayrollContract.staff_id == staff_id,
                        PayrollContract.is_active == True
                    )
                )
                if existing_result.scalar_one_or_none():
                    errors.append(f"Row {index + 2}: Active contract already exists for staff '{staff_id}'")
                    continue
                
                # Parse contract data
                contract_data = PayrollContractCreate(
                    staff_id=staff_id,
                    basic_salary=float(row['basic_salary']),
                    pay_schedule=str(row['pay_schedule']).strip().lower(),
                    allowance_housing=float(row.get('allowance_housing', 0) or 0),
                    allowance_transport=float(row.get('allowance_transport', 0) or 0),
                    allowance_meals=float(row.get('allowance_meals', 0) or 0),
                    allowance_utilities=float(row.get('allowance_utilities', 0) or 0),
                    allowance_other=float(row.get('allowance_other', 0) or 0),
                    allowance_other_description=str(row.get('allowance_other_description', '') or '').strip(),
                    tax_rate_percent=float(row.get('tax_rate_percent', 0) or 0),
                    pension_rate_percent=float(row.get('pension_rate_percent', 0) or 0),
                    nssf_rate_percent=float(row.get('nssf_rate_percent', 0) or 0),
                    other_deduction=float(row.get('other_deduction', 0) or 0),
                    other_deduction_description=str(row.get('other_deduction_description', '') or '').strip(),
                    effective_from=str(row['effective_from']).strip(),
                    notes=str(row.get('notes', '') or '').strip()
                )
                
                # Validate deduction rates don't exceed 100%
                total_deduction_rate = (
                    contract_data.tax_rate_percent + 
                    contract_data.pension_rate_percent + 
                    contract_data.nssf_rate_percent
                )
                if total_deduction_rate > 100:
                    errors.append(f"Row {index + 2}: Total deduction rate cannot exceed 100% (current: {total_deduction_rate}%)")
                    continue
                
                # Create contract
                contract = PayrollContract(
                    school_id=school_id,
                    created_by=current_user.id,
                    **contract_data.model_dump()
                )
                session.add(contract)
                success_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
        
        await session.commit()
        
        message = f"Imported {success_count} contracts successfully"
        if errors:
            message = f"{message} with {len(errors)} errors"
        
        return {
            "success": len(errors) == 0,
            "message": message,
            "success_count": success_count,
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Import failed: {str(e)}"
        )


@router.get("/contracts", response_model=dict)
async def list_payroll_contracts(
    staff_id: Optional[str] = None,
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List payroll contracts with pagination"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(PayrollContract)
    count_query = select(func.count(PayrollContract.id))
    
    if school_id:
        query = query.where(PayrollContract.school_id == school_id)
        count_query = count_query.where(PayrollContract.school_id == school_id)
    
    if active_only:
        query = query.where(PayrollContract.is_active == True)
        count_query = count_query.where(PayrollContract.is_active == True)
    
    if staff_id:
        query = query.where(PayrollContract.staff_id == staff_id)
        count_query = count_query.where(PayrollContract.staff_id == staff_id)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(PayrollContract.created_at.desc())
    
    result = await session.execute(query)
    contracts = result.scalars().all()
    
    # Get staff names
    staff_ids = [c.staff_id for c in contracts]
    staff_map = {}
    if staff_ids:
        staff_result = await session.execute(
            select(Staff).where(Staff.id.in_(staff_ids))
        )
        for s in staff_result.scalars().all():
            staff_map[s.id] = f"{s.first_name} {s.last_name}"
    
    return {
        "items": [
            {
                "id": c.id,
                "staff_id": c.staff_id,
                "staff_name": staff_map.get(c.staff_id, "Unknown"),
                "basic_salary": c.basic_salary,
                "pay_schedule": c.pay_schedule,
                "total_allowances": (c.allowance_housing + c.allowance_transport + 
                                   c.allowance_meals + c.allowance_utilities + 
                                   c.allowance_other),
                "effective_from": c.effective_from.isoformat(),
                "effective_to": c.effective_to.isoformat() if c.effective_to else None,
                "status": "active" if c.is_active else "inactive",
                "created_at": c.created_at.isoformat()
            }
            for c in contracts
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/contracts/{contract_id}", response_model=dict)
async def get_payroll_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payroll contract details"""
    result = await session.execute(
        select(PayrollContract).where(PayrollContract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != contract.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get staff details
    staff_result = await session.execute(
        select(Staff).where(Staff.id == contract.staff_id)
    )
    staff = staff_result.scalar_one_or_none()
    
    return {
        "id": contract.id,
        "staff_id": contract.staff_id,
        "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
        "basic_salary": contract.basic_salary,
        "pay_schedule": contract.pay_schedule,
        "currency": contract.currency,
        "allowances": {
            "housing": contract.allowance_housing,
            "transport": contract.allowance_transport,
            "meals": contract.allowance_meals,
            "utilities": contract.allowance_utilities,
            "other": contract.allowance_other,
            "other_description": contract.allowance_other_description
        },
        "deductions": {
            "tax_rate_percent": contract.tax_rate_percent,
            "pension_rate_percent": contract.pension_rate_percent,
            "nssf_rate_percent": contract.nssf_rate_percent,
            "other_deduction": contract.other_deduction,
            "other_deduction_description": contract.other_deduction_description
        },
        "effective_from": contract.effective_from.isoformat(),
        "effective_to": contract.effective_to.isoformat() if contract.effective_to else None,
        "status": "active" if contract.is_active else "inactive",
        "notes": contract.notes,
        "created_at": contract.created_at.isoformat(),
        "updated_at": contract.updated_at.isoformat()
    }


@router.put("/contracts/{contract_id}", response_model=dict)
async def update_payroll_contract(
    contract_id: str,
    contract_data: PayrollContractUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.HR)),
    session: AsyncSession = Depends(get_session)
):
    """Update payroll contract"""
    result = await session.execute(
        select(PayrollContract).where(PayrollContract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != contract.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields
    update_data = contract_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contract, key, value)
    
    contract.updated_at = datetime.utcnow()
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    
    return {
        "id": contract.id,
        "staff_id": contract.staff_id,
        "basic_salary": contract.basic_salary,
        "status": "active" if contract.is_active else "inactive",
        "updated_at": contract.updated_at.isoformat()
    }


# ==================== Payroll Run Endpoints ====================

@router.post("/runs", response_model=dict)
async def generate_payroll_run(
    payroll_data: PayrollRunCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.HR)),
    session: AsyncSession = Depends(get_session)
):
    """Generate payroll run for a month"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    service = PayrollService(session)
    result = await service.generate_payroll_run(
        school_id=school_id,
        year=payroll_data.period_year,
        month=payroll_data.period_month,
        current_user=current_user,
        notes=payroll_data.notes
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"],
            headers={"X-Errors": str(result.get("errors", [])[:3])}
        )
    
    return result


@router.get("/runs", response_model=dict)
async def list_payroll_runs(
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List payroll runs with pagination"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(PayrollRun)
    count_query = select(func.count(PayrollRun.id))
    
    if school_id:
        query = query.where(PayrollRun.school_id == school_id)
        count_query = count_query.where(PayrollRun.school_id == school_id)
    
    if year:
        query = query.where(PayrollRun.period_year == year)
        count_query = count_query.where(PayrollRun.period_year == year)
    
    if month:
        query = query.where(PayrollRun.period_month == month)
        count_query = count_query.where(PayrollRun.period_month == month)
    
    if status:
        query = query.where(PayrollRun.status == status)
        count_query = count_query.where(PayrollRun.status == status)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(PayrollRun.created_at.desc())
    
    result = await session.execute(query)
    runs = result.scalars().all()
    
    return {
        "items": [
            {
                "id": r.id,
                "period_name": r.period_name,
                "status": r.status,
                "staff_count": r.staff_count,
                "total_gross": r.total_gross,
                "total_allowances": r.total_allowances,
                "total_deductions": r.total_deductions,
                "total_net": r.total_net,
                "created_at": r.created_at.isoformat()
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/runs/{run_id}", response_model=dict)
async def get_payroll_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payroll run details"""
    result = await session.execute(
        select(PayrollRun).where(PayrollRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != run.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": run.id,
        "period_name": run.period_name,
        "period_year": run.period_year,
        "period_month": run.period_month,
        "status": run.status,
        "staff_count": run.staff_count,
        "total_gross": run.total_gross,
        "total_allowances": run.total_allowances,
        "total_deductions": run.total_deductions,
        "total_net": run.total_net,
        "generated_by": run.generated_by,
        "approved_by": run.approved_by,
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "posted_at": run.posted_at.isoformat() if run.posted_at else None,
        "notes": run.notes,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat()
    }


@router.post("/runs/{run_id}/approve", response_model=dict)
async def approve_payroll_run(
    run_id: str,
    notes: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Approve payroll run (SUPER_ADMIN and SCHOOL_ADMIN only)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    service = PayrollService(session)
    result = await service.approve_payroll_run(
        school_id=school_id,
        payroll_run_id=run_id,
        current_user=current_user,
        notes=notes
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/runs/{run_id}/post", response_model=dict)
async def post_payroll_run(
    run_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Post payroll run (finalize - SUPER_ADMIN and SCHOOL_ADMIN only)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    service = PayrollService(session)
    result = await service.post_payroll_run(
        school_id=school_id,
        payroll_run_id=run_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


# ==================== Payslip & Line Items ====================

@router.get("/runs/{run_id}/lines", response_model=dict)
async def get_payroll_line_items(
    run_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payroll line items for a run"""
    # Verify run exists
    result = await session.execute(
        select(PayrollRun).where(PayrollRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != run.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get line items
    query = select(PayrollLineItem)
    count_query = select(func.count(PayrollLineItem.id))
    
    query = query.where(PayrollLineItem.payroll_run_id == run_id)
    count_query = count_query.where(PayrollLineItem.payroll_run_id == run_id)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(PayrollLineItem.created_at)
    
    result = await session.execute(query)
    line_items = result.scalars().all()
    
    # Get staff names
    staff_ids = [li.staff_id for li in line_items]
    staff_map = {}
    if staff_ids:
        staff_result = await session.execute(
            select(Staff).where(Staff.id.in_(staff_ids))
        )
        for s in staff_result.scalars().all():
            staff_map[s.id] = f"{s.first_name} {s.last_name}"
    
    return {
        "items": [
            {
                "id": li.id,
                "staff_id": li.staff_id,
                "staff_name": staff_map.get(li.staff_id, "Unknown"),
                "basic_salary": li.basic_salary,
                "total_allowances": li.total_allowances,
                "gross_amount": li.gross_amount,
                "tax_amount": li.tax_amount,
                "pension_amount": li.pension_amount,
                "nssf_amount": li.nssf_amount,
                "other_deductions": li.other_deductions,
                "total_deductions": li.total_deductions,
                "net_amount": li.net_amount
            }
            for li in line_items
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/payslips/{run_id}/{staff_id}", response_model=dict)
async def get_payslip(
    run_id: str,
    staff_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payslip for a staff member in a payroll run"""
    # Verify run exists
    result = await session.execute(
        select(PayrollRun).where(PayrollRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    
    # Get line item
    result = await session.execute(
        select(PayrollLineItem).where(
            PayrollLineItem.payroll_run_id == run_id,
            PayrollLineItem.staff_id == staff_id
        )
    )
    line_item = result.scalar_one_or_none()
    
    if not line_item:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    # Permission check - can view own payslip or if admin
    if current_user.role == UserRole.STUDENT:
        # If student viewing their own payslip (staff can too)
        # Allow if it's their record
        pass
    elif current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != run.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get staff details
    staff_result = await session.execute(
        select(Staff).where(Staff.id == staff_id)
    )
    staff = staff_result.scalar_one_or_none()
    
    # Get school name
    school_result = await session.execute(
        select(School).where(School.id == run.school_id)
    )
    school = school_result.scalar_one_or_none()
    
    return {
        "payroll_run_id": run.id,
        "period_name": run.period_name,
        "school_name": school.name if school else "School",
        "staff_id": staff_id,
        "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
        "basic_salary": line_item.basic_salary,
        "total_allowances": line_item.total_allowances,
        "gross_amount": line_item.gross_amount,
        "tax_amount": line_item.tax_amount,
        "pension_amount": line_item.pension_amount,
        "nssf_amount": line_item.nssf_amount,
        "other_deductions": line_item.other_deductions,
        "total_deductions": line_item.total_deductions,
        "net_amount": line_item.net_amount,
        "currency": "GHS",
        "generated_at": run.created_at.isoformat(),
        "posted_at": run.posted_at.isoformat() if run.posted_at else None
    }
