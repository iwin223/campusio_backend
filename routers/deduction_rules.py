"""Deduction Rules API Endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from models.payroll import (
    DeductionRule, DeductionRuleCreate, DeductionRuleUpdate, 
    DeductionRuleResponse, RuleType, RuleOperator
)
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from services.deduction_rules_service import RulesEvaluationService, RulePresetService

router = APIRouter(prefix="/payroll/rules", tags=["Payroll Rules"])


# ==================== Rule Management Endpoints ====================

@router.get("", response_model=dict)
async def list_deduction_rules(
    rule_type: Optional[str] = None,
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List deduction rules for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(DeductionRule).where(DeductionRule.school_id == school_id)
    count_query = select(func.count(DeductionRule.id)).where(DeductionRule.school_id == school_id)
    
    if active_only:
        query = query.where(DeductionRule.is_active == True)
        count_query = count_query.where(DeductionRule.is_active == True)
    
    if rule_type:
        query = query.where(DeductionRule.rule_type == rule_type)
        count_query = count_query.where(DeductionRule.rule_type == rule_type)
    
    # Count total
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Paginate and sort by priority
    offset = (page - 1) * limit
    query = query.order_by(DeductionRule.priority.desc()).offset(offset).limit(limit)
    
    result = await session.execute(query)
    rules = result.scalars().all()
    
    return {
        "items": [
            DeductionRuleResponse(
                id=r.id,
                school_id=r.school_id,
                name=r.name,
                description=r.description,
                rule_type=r.rule_type,
                operator=r.operator,
                condition_field=r.condition_field,
                condition_value_min=r.condition_value_min,
                condition_value_max=r.condition_value_max,
                deduction_type=r.deduction_type,
                deduction_amount=r.deduction_amount,
                deduction_category=r.deduction_category,
                priority=r.priority,
                is_active=r.is_active,
                created_at=r.created_at
            ).dict()
            for r in rules
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.post("", response_model=dict)
async def create_deduction_rule(
    rule_data: DeductionRuleCreate,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN, 
        UserRole.SCHOOL_ADMIN, 
        UserRole.HR
    )),
    session: AsyncSession = Depends(get_session)
):
    """Create a new deduction rule"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    rule = DeductionRule(
        school_id=school_id,
        created_by=current_user.id,
        **rule_data.dict()
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    
    return {
        "id": rule.id,
        "name": rule.name,
        "message": "Deduction rule created successfully"
    }


@router.get("/{rule_id}", response_model=dict)
async def get_deduction_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific deduction rule"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(DeductionRule).where(
            DeductionRule.id == rule_id,
            DeductionRule.school_id == school_id
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return DeductionRuleResponse(
        id=rule.id,
        school_id=rule.school_id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        operator=rule.operator,
        condition_field=rule.condition_field,
        condition_value_min=rule.condition_value_min,
        condition_value_max=rule.condition_value_max,
        deduction_type=rule.deduction_type,
        deduction_amount=rule.deduction_amount,
        deduction_category=rule.deduction_category,
        priority=rule.priority,
        is_active=rule.is_active,
        created_at=rule.created_at
    ).dict()


@router.put("/{rule_id}", response_model=dict)
async def update_deduction_rule(
    rule_id: str,
    rule_data: DeductionRuleUpdate,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN,
        UserRole.HR
    )),
    session: AsyncSession = Depends(get_session)
):
    """Update a deduction rule"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    result = await session.execute(
        select(DeductionRule).where(
            DeductionRule.id == rule_id,
            DeductionRule.school_id == school_id
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Update fields
    update_data = rule_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(rule, field, value)
    
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    
    return {
        "id": rule.id,
        "name": rule.name,
        "message": "Deduction rule updated successfully"
    }


@router.delete("/{rule_id}", response_model=dict)
async def delete_deduction_rule(
    rule_id: str,
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN
    )),
    session: AsyncSession = Depends(get_session)
):
    """Delete a deduction rule (soft delete)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    result = await session.execute(
        select(DeductionRule).where(
            DeductionRule.id == rule_id,
            DeductionRule.school_id == school_id
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.is_active = False
    session.add(rule)
    await session.commit()
    
    return {"message": "Deduction rule deleted successfully"}


# ==================== Preset Rules Endpoints ====================

@router.get("/presets/templates", response_model=dict)
async def get_preset_rules(
    current_user: User = Depends(get_current_user)
):
    """Get preset rule templates for quick setup"""
    presets = RulePresetService.get_preset_rules()
    
    return {
        "presets": presets,
        "total": len(presets),
        "message": "Available preset rules for payroll systems"
    }


@router.post("/presets/apply", response_model=dict)
async def apply_preset_rules(
    preset_names: List[str],
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN,
        UserRole.SCHOOL_ADMIN
    )),
    session: AsyncSession = Depends(get_session)
):
    """Apply multiple preset rules to the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    all_presets = {p["name"]: p for p in RulePresetService.get_preset_rules()}
    created_count = 0
    errors = []
    
    for preset_name in preset_names:
        if preset_name not in all_presets:
            errors.append(f"Preset '{preset_name}' not found")
            continue
        
        preset = all_presets[preset_name]
        
        # Check if rule already exists
        existing = await session.execute(
            select(DeductionRule).where(
                DeductionRule.school_id == school_id,
                DeductionRule.name == preset["name"]
            )
        )
        if existing.scalar_one_or_none():
            errors.append(f"Rule '{preset_name}' already exists")
            continue
        
        # Create rule from preset
        rule = DeductionRule(
            school_id=school_id,
            created_by=current_user.id,
            **preset
        )
        session.add(rule)
        created_count += 1
    
    await session.commit()
    
    return {
        "created": created_count,
        "errors": errors,
        "message": f"Applied {created_count} preset rules successfully"
    }


# ==================== Rule Testing Endpoints ====================

@router.post("/test", response_model=dict)
async def test_rule_evaluation(
    rule_id: str,
    staff_id: str,
    basic_salary: float,
    metadata: dict = {},
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Test a rule against sample staff data"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get the rule
    result = await session.execute(
        select(DeductionRule).where(
            DeductionRule.id == rule_id,
            DeductionRule.school_id == school_id
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Test evaluation
    service = RulesEvaluationService(session, school_id)
    matched, deduction = service._evaluate_rule(
        rule,
        {
            "staff_id": staff_id,
            "basic_salary": basic_salary,
            **metadata
        }
    )
    
    return {
        "rule_id": rule_id,
        "rule_name": rule.name,
        "matched": matched,
        "deduction_amount": deduction if matched else 0,
        "message": f"Rule {'matched' if matched else 'did not match'} for test data"
    }


@router.post("/test-all", response_model=dict)
async def test_all_rules(
    staff_id: str,
    basic_salary: float,
    period_year: int,
    period_month: int,
    metadata: dict = {},
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Test all applicable rules for a staff member"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    service = RulesEvaluationService(session, school_id)
    evaluation_results, total_deduction = await service.evaluate_rules_for_staff(
        staff_id=staff_id,
        basic_salary=basic_salary,
        period_year=period_year,
        period_month=period_month,
        staff_metadata=metadata
    )
    
    return {
        "staff_id": staff_id,
        "basic_salary": basic_salary,
        "matched_rules": [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "deduction_amount": r.deduction_amount,
                "deduction_type": r.deduction_type,
                "reason": r.reason
            }
            for r in evaluation_results
        ],
        "total_deduction": total_deduction,
        "total_matched_rules": len(evaluation_results),
        "message": f"Evaluated {len(evaluation_results)} matching rules"
    }
