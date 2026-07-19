"""Schools router"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import select, SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional
from models.school import School, SchoolCreate, SchoolUpdate, SchoolType, AcademicTerm, AcademicTermCreate, AcademicTermUpdate
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from services.coa_initialization import seed_default_chart_of_accounts
from services.fiscal_period_initialization import seed_default_fiscal_periods
from services.audit_service import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schools", tags=["Schools"])


@router.post("", response_model=dict)
async def create_school(
    school_data: SchoolCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new school (super admin only)"""
    result = await session.execute(select(School).where(School.code == school_data.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="School code already exists")
    
    school = School(**school_data.model_dump())
    session.add(school)
    await session.commit()
    await session.refresh(school)

    # Capture the response before seeding — seed_default_chart_of_accounts commits once per
    # account, which expires this ORM object's attributes and would otherwise force a refetch.
    response = {
        "id": school.id,
        "name": school.name,
        "code": school.code,
        "school_type": school.school_type,
        "address": school.address,
        "city": school.city,
        "region": school.region,
        "phone": school.phone,
        "email": school.email,
        "logo_url": school.logo_url,
        "motto": school.motto,
        "is_active": school.is_active,
        "enable_hostel": school.enable_hostel,
        "created_at": school.created_at.isoformat()
    }

    # Best-effort: a missing/partial Chart of Accounts shouldn't block school creation,
    # but without it the Finance module has nothing to post fee payments against.
    try:
        seed_result = await seed_default_chart_of_accounts(session, response["id"], created_by=current_user.id)
        if not seed_result["success"]:
            logger.warning(f"CoA seeding had failures for new school {response['id']}: {seed_result['errors']}")
    except Exception as e:
        logger.error(f"Failed to seed default Chart of Accounts for new school {response['id']}: {e}")

    # Best-effort: without an open fiscal period, postings have nowhere to land until
    # a school_admin manually creates one via the Fiscal Periods tab.
    try:
        period_result = await seed_default_fiscal_periods(session, response["id"], created_by=current_user.id)
        if not period_result["success"]:
            logger.warning(f"Fiscal period seeding had failures for new school {response['id']}: {period_result['errors']}")
    except Exception as e:
        logger.error(f"Failed to seed default fiscal periods for new school {response['id']}: {e}")

    await log_event(
        session, actor=current_user, action="school.created", entity_type="school",
        entity_id=response["id"], school_id=response["id"],
        summary=f"{current_user.email} created school: {school.name} ({school.code})",
        ip_address=request.client.host if request.client else None,
    )

    return response


@router.get("/terms/list", response_model=dict)
async def list_all_academic_terms(
    academic_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List academic terms for current user's school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(AcademicTerm).where(AcademicTerm.school_id == school_id)
    
    if academic_year:
        query = query.where(AcademicTerm.academic_year == academic_year)
    
    query = query.order_by(AcademicTerm.start_date.desc())
    
    result = await session.execute(query)
    terms = result.scalars().all()
    
    return {
        "items": [
            {
                "id": t.id,
                "school_id": t.school_id,
                "academic_year": t.academic_year,
                "term": t.term,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "is_current": t.is_current
            }
            for t in terms
        ]
    }


@router.get("", response_model=list[dict])
async def list_schools(
    is_active: Optional[bool] = None,
    school_type: Optional[SchoolType] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all schools"""
    query = select(School)
    
    if is_active is not None:
        query = query.where(School.is_active == is_active)
    if school_type:
        query = query.where(School.school_type == school_type)
    
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(School.id == current_user.school_id)
    
    result = await session.execute(query)
    schools = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "school_type": s.school_type,
            "address": s.address,
            "city": s.city,
            "region": s.region,
            "phone": s.phone,
            "email": s.email,
            "logo_url": s.logo_url,
            "motto": s.motto,
            "is_active": s.is_active,
            "enable_hostel": s.enable_hostel,
            "created_at": s.created_at.isoformat()
        }
        for s in schools
    ]


@router.get("/{school_id}", response_model=dict)
async def get_school(
    school_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get school details"""
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    return {
        "id": school.id,
        "name": school.name,
        "code": school.code,
        "school_type": school.school_type,
        "address": school.address,
        "city": school.city,
        "region": school.region,
        "phone": school.phone,
        "email": school.email,
        "logo_url": school.logo_url,
        "motto": school.motto,
        "is_active": school.is_active,
        "enable_hostel": school.enable_hostel,
        "created_at": school.created_at.isoformat()
    }


@router.get("/{school_id}/detail", response_model=dict)
async def get_school_detail(
    school_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """School info plus every user account at that school, with roles.
    Super admin can view any school; a school admin can only view their own."""
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    users_result = await session.execute(
        select(User).where(User.school_id == school_id).order_by(User.role, User.first_name)
    )
    users = users_result.scalars().all()

    role_counts: dict[str, int] = {}
    for u in users:
        role_value = u.role.value if hasattr(u.role, "value") else str(u.role)
        role_counts[role_value] = role_counts.get(role_value, 0) + 1

    return {
        "school": {
            "id": school.id,
            "name": school.name,
            "code": school.code,
            "school_type": school.school_type,
            "address": school.address,
            "city": school.city,
            "region": school.region,
            "phone": school.phone,
            "email": school.email,
            "motto": school.motto,
            "is_active": school.is_active,
            "enable_hostel": school.enable_hostel,
            "created_at": school.created_at.isoformat(),
        },
        "role_counts": role_counts,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone": u.phone,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ],
    }


@router.delete("/{school_id}", response_model=dict)
async def delete_school(
    school_id: str,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Remove a school. Super admin only. This is a soft delete (is_active=False)
    — the school and every record referencing it (students, staff, fees,
    grades, ...) stay in place, since there's no DB-level cascade to safely
    hard-delete against. A deactivated school disappears from active lists
    but its historical data remains intact."""
    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    if not school.is_active:
        raise HTTPException(status_code=400, detail="School is already removed")

    school.is_active = False
    school.updated_at = datetime.utcnow()
    session.add(school)
    await session.commit()

    await log_event(
        session, actor=current_user, action="school.deleted", entity_type="school",
        entity_id=school_id, school_id=school_id,
        summary=f"{current_user.email} removed school: {school.name} ({school.code})",
        old_values={"is_active": True},
        ip_address=request.client.host if request.client else None,
    )

    return {"message": f"School {school.name} removed"}


class UpdateSchoolAccessRequest(SQLModel):
    suspended: bool
    reason: Optional[str] = None


@router.put("/{school_id}/access", response_model=dict)
async def update_school_access(
    school_id: str,
    body: UpdateSchoolAccessRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Suspend or restore a school's access to every module (billing enforcement).
    Enforced centrally in auth.py::get_current_user — every non-super-admin
    request for this school's users gets blocked while suspended is True."""
    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    was_suspended = school.access_suspended
    school.access_suspended = body.suspended
    school.access_suspended_reason = body.reason if body.suspended else None
    school.access_suspended_at = datetime.utcnow() if body.suspended else None
    school.updated_at = datetime.utcnow()
    session.add(school)
    await session.commit()

    action = "school.access_suspended" if body.suspended else "school.access_restored"
    summary = (
        f"{current_user.email} suspended access for {school.name} ({school.code})"
        + (f" — {body.reason}" if body.reason else "")
    ) if body.suspended else f"{current_user.email} restored access for {school.name} ({school.code})"

    await log_event(
        session, actor=current_user, action=action, entity_type="school",
        entity_id=school_id, school_id=school_id, summary=summary,
        old_values={"access_suspended": was_suspended}, new_values={"access_suspended": body.suspended},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "message": f"School {school.name} access {'suspended' if body.suspended else 'restored'}",
        "access_suspended": school.access_suspended,
    }


# Academic Terms
@router.post("/{school_id}/terms", response_model=dict)
async def create_academic_term(
    school_id: str,
    term_data: AcademicTermCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new academic term"""
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if term_data.is_current:
        result = await session.execute(
            select(AcademicTerm).where(
                AcademicTerm.school_id == school_id,
                AcademicTerm.is_current == True
            )
        )
        for term in result.scalars().all():
            term.is_current = False
            session.add(term)
    
    term = AcademicTerm(school_id=school_id, **term_data.model_dump())
    session.add(term)
    await session.commit()
    await session.refresh(term)
    
    return {
        "id": term.id,
        "school_id": term.school_id,
        "academic_year": term.academic_year,
        "term": term.term,
        "start_date": term.start_date,
        "end_date": term.end_date,
        "is_current": term.is_current
    }


@router.get("/{school_id}/terms", response_model=list[dict])
async def list_academic_terms(
    school_id: str,
    academic_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List academic terms for a school"""
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = select(AcademicTerm).where(AcademicTerm.school_id == school_id)
    
    if academic_year:
        query = query.where(AcademicTerm.academic_year == academic_year)
    
    query = query.order_by(AcademicTerm.start_date.desc())
    
    result = await session.execute(query)
    terms = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "school_id": t.school_id,
            "academic_year": t.academic_year,
            "term": t.term,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "is_current": t.is_current
        }
        for t in terms
    ]


@router.get("/{school_id}/terms/current", response_model=dict)
async def get_current_term(
    school_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get current academic term"""
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current == True
        )
    )
    term = result.scalar_one_or_none()
    
    if not term:
        raise HTTPException(status_code=404, detail="No current term set")
    
    return {
        "id": term.id,
        "school_id": term.school_id,
        "academic_year": term.academic_year,
        "term": term.term,
        "start_date": term.start_date,
        "end_date": term.end_date,
        "is_current": term.is_current
    }


@router.put("/{school_id}/terms/{term_id}/set-current", response_model=dict)
async def set_current_term(
    school_id: str,
    term_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Set a term as current"""
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Unset all current terms
    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current == True
        )
    )
    for term in result.scalars().all():
        term.is_current = False
        session.add(term)
    
    # Set the specified term as current
    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.school_id == school_id
        )
    )
    term = result.scalar_one_or_none()
    
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    
    term.is_current = True
    session.add(term)
    await session.commit()
    
    return {"message": "Current term updated successfully"}


# School Update
@router.put("/{school_id}", response_model=dict)
async def update_school(
    school_id: str,
    school_data: SchoolUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update school details"""
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Update only provided fields
    update_data = school_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(school, field, value)
    
    school.updated_at = datetime.utcnow()
    session.add(school)
    await session.commit()
    await session.refresh(school)
    
    return {
        "id": school.id,
        "name": school.name,
        "code": school.code,
        "school_type": school.school_type,
        "address": school.address,
        "city": school.city,
        "region": school.region,
        "phone": school.phone,
        "email": school.email,
        "logo_url": school.logo_url,
        "motto": school.motto,
        "is_active": school.is_active,
        "enable_hostel": school.enable_hostel,
        "created_at": school.created_at.isoformat(),
        "updated_at": school.updated_at.isoformat()
    }


# Academic Term Update
@router.put("/{school_id}/terms/{term_id}", response_model=dict)
async def update_academic_term(
    school_id: str,
    term_id: str,
    term_data: AcademicTermUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update an academic term"""
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.school_id == school_id
        )
    )
    term = result.scalar_one_or_none()
    
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    
    # If setting is_current to True, unset other current terms
    if term_data.is_current:
        result = await session.execute(
            select(AcademicTerm).where(
                AcademicTerm.school_id == school_id,
                AcademicTerm.is_current == True
            )
        )
        for t in result.scalars().all():
            t.is_current = False
            session.add(t)
    
    # Update only provided fields
    update_data = term_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(term, field, value)
    
    session.add(term)
    await session.commit()
    await session.refresh(term)
    
    return {
        "id": term.id,
        "school_id": term.school_id,
        "academic_year": term.academic_year,
        "term": term.term,
        "start_date": term.start_date,
        "end_date": term.end_date,
        "is_current": term.is_current
    }


# Tables that get permanently deleted (CASCADE) when an academic term is deleted.
TERM_CASCADE_TABLES = [
    ("assignments", "assignments"),
    ("learning_materials", "learning materials"),
    ("attendance", "attendance records"),
    ("class_subjects", "class-subject assignments"),
    ("grades", "grades"),
    ("report_cards", "report cards"),
    ("teacher_assignments", "teacher assignments"),
    ("timetables", "timetable entries"),
]

# Tables that just get unlinked (SET NULL) — the records themselves are kept.
TERM_PRESERVED_TABLES = [
    ("classes", "classes"),
    ("fees", "fee records"),
    ("fee_structures", "fee structures"),
    ("platform_subscriptions", "billing/subscription records"),
]


@router.get("/{school_id}/terms/{term_id}/delete-impact", response_model=dict)
async def get_term_delete_impact(
    school_id: str,
    term_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Preview what deleting this academic term would affect, before actually deleting it.

    Academic/operational data (grades, attendance, assignments, etc.) is permanently
    deleted along with the term. Financial data (fees, billing records) is never deleted —
    it's preserved with its term reference cleared.
    """
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.school_id == school_id
        )
    )
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    will_be_deleted = {}
    for table, label in TERM_CASCADE_TABLES:
        count_result = await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE academic_term_id = :tid"),
            {"tid": term_id}
        )
        count = count_result.scalar()
        if count:
            will_be_deleted[label] = count

    will_be_preserved = {}
    for table, label in TERM_PRESERVED_TABLES:
        count_result = await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE academic_term_id = :tid"),
            {"tid": term_id}
        )
        count = count_result.scalar()
        if count:
            will_be_preserved[label] = count

    return {
        "term_id": term_id,
        "will_be_deleted": will_be_deleted,
        "total_to_be_deleted": sum(will_be_deleted.values()),
        "will_be_preserved": will_be_preserved,
    }


# Academic Term Delete
@router.delete("/{school_id}/terms/{term_id}", response_model=dict)
async def delete_academic_term(
    school_id: str,
    term_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete an academic term.

    Academic/operational records tied to this term (grades, attendance, assignments,
    report cards, timetables, teacher assignments, class-subject links) are permanently
    deleted along with it via DB-level CASCADE. Financial records (fees, fee structures,
    billing/subscription records) are never deleted — they're preserved with their term
    reference cleared via DB-level SET NULL. Call GET .../delete-impact first to show the
    user what this will affect before they confirm.
    """
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await session.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.school_id == school_id
        )
    )
    term = result.scalar_one_or_none()

    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    await session.delete(term)
    await session.commit()

    return {"message": "Academic term deleted successfully"}
