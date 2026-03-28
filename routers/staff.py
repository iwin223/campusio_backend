"""Staff router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from models.staff import Staff, StaffCreate, StaffType, StaffStatus, TeacherAssignment
from models.classroom import Class, Subject
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from services.csv_import_service import CSVImportService

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.post("", response_model=dict)
async def create_staff(
    staff_data: StaffCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new staff member"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    result = await session.execute(
        select(Staff).where(
            Staff.school_id == school_id,
            Staff.staff_id == staff_data.staff_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Staff ID already exists")
    
    staff = Staff(school_id=school_id, **staff_data.model_dump())
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    
    return {
        "id": staff.id,
        "school_id": staff.school_id,
        "staff_id": staff.staff_id,
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "email": staff.email,
        "staff_type": staff.staff_type,
        "position": staff.position,
        "status": staff.status,
        "created_at": staff.created_at.isoformat()
    }


@router.post("/import", response_model=dict)
async def import_staff_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Import staff from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    # Read file content
    content = await file.read()
    
    # Import staff
    import_service = CSVImportService(session, school_id, current_user)
    result = await import_service.import_staff(content)
    
    if not result['success'] and result['success_count'] == 0:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.get("", response_model=dict)
async def list_staff(
    staff_type: Optional[StaffType] = None,
    status: Optional[StaffStatus] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List staff with pagination"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Staff)
    count_query = select(func.count(Staff.id))
    
    if school_id:
        query = query.where(Staff.school_id == school_id)
        count_query = count_query.where(Staff.school_id == school_id)
    
    if staff_type:
        query = query.where(Staff.staff_type == staff_type)
        count_query = count_query.where(Staff.staff_type == staff_type)
    
    if status:
        query = query.where(Staff.status == status)
        count_query = count_query.where(Staff.status == status)
    
    if search:
        search_filter = (
            Staff.first_name.ilike(f"%{search}%") |
            Staff.last_name.ilike(f"%{search}%") |
            Staff.staff_id.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Staff.first_name)
    
    result = await session.execute(query)
    staff_list = result.scalars().all()
    
    return {
        "items": [
            {
                "id": s.id,
                "school_id": s.school_id,
                "staff_id": s.staff_id,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "full_name": f"{s.first_name} {s.last_name}",
                "email": s.email,
                "phone": s.phone,
                "staff_type": s.staff_type,
                "position": s.position,
                "department": s.department,
                "status": s.status,
                "photo_url": s.photo_url
            }
            for s in staff_list
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/teachers", response_model=list[dict])
async def list_teachers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all teaching staff"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Staff).where(
            Staff.school_id == school_id,
            Staff.staff_type == StaffType.TEACHING,
            Staff.status == StaffStatus.ACTIVE
        ).order_by(Staff.first_name)
    )
    teachers = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "staff_id": t.staff_id,
            "first_name": t.first_name,
            "last_name": t.last_name,
            "full_name": f"{t.first_name} {t.last_name}",
            "email": t.email,
            "department": t.department,
            "qualification": t.qualification
        }
        for t in teachers
    ]


@router.get("/{staff_id}", response_model=dict)
async def get_staff(
    staff_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get staff details"""
    result = await session.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != staff.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    assignments = []
    if staff.staff_type == StaffType.TEACHING:
        assign_result = await session.execute(
            select(TeacherAssignment).where(TeacherAssignment.staff_id == staff.id)
        )
        for a in assign_result.scalars().all():
            class_result = await session.execute(select(Class).where(Class.id == a.class_id))
            cls = class_result.scalar_one_or_none()
            
            subject_result = await session.execute(select(Subject).where(Subject.id == a.subject_id))
            subject = subject_result.scalar_one_or_none()
            
            assignments.append({
                "id": a.id,
                "class_id": a.class_id,
                "class_name": cls.name if cls else "Unknown",
                "subject_id": a.subject_id,
                "subject_name": subject.name if subject else "Unknown",
                "is_class_teacher": a.is_class_teacher
            })
    
    return {
        "id": staff.id,
        "school_id": staff.school_id,
        "staff_id": staff.staff_id,
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "full_name": f"{staff.first_name} {staff.last_name}",
        "email": staff.email,
        "phone": staff.phone,
        "date_of_birth": staff.date_of_birth,
        "gender": staff.gender,
        "staff_type": staff.staff_type,
        "position": staff.position,
        "department": staff.department,
        "qualification": staff.qualification,
        "date_joined": staff.date_joined,
        "status": staff.status,
        "photo_url": staff.photo_url,
        "assignments": assignments,
        "created_at": staff.created_at.isoformat()
    }


@router.put("/{staff_id}", response_model=dict)
async def update_staff(
    staff_id: str,
    staff_data: StaffCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update staff details"""
    result = await session.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != staff.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in staff_data.model_dump().items():
        setattr(staff, key, value)
    
    staff.updated_at = datetime.utcnow()
    session.add(staff)
    await session.commit()
    
    return {"message": "Staff updated successfully"}


@router.post("/{staff_id}/assignments", response_model=dict)
async def assign_teacher(
    staff_id: str,
    class_id: str,
    subject_id: str,
    academic_term_id: str,
    is_class_teacher: bool = False,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Assign a teacher to a class and subject"""
    result = await session.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    if staff.staff_type != StaffType.TEACHING:
        raise HTTPException(status_code=400, detail="Staff is not a teacher")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != staff.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await session.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.staff_id == staff_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.academic_term_id == academic_term_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Assignment already exists")
    
    assignment = TeacherAssignment(
        school_id=staff.school_id,
        staff_id=staff_id,
        class_id=class_id,
        subject_id=subject_id,
        academic_term_id=academic_term_id,
        is_class_teacher=is_class_teacher
    )
    session.add(assignment)
    await session.commit()
    
    return {"message": "Teacher assigned successfully", "assignment_id": assignment.id}


@router.delete("/{staff_id}/assignments/{assignment_id}", response_model=dict)
async def remove_assignment(
    staff_id: str,
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Remove a teacher assignment"""
    result = await session.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.staff_id == staff_id
        )
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await session.delete(assignment)
    await session.commit()
    
    return {"message": "Assignment removed"}
