"""Students router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import re
import secrets
from models.student import Student, StudentCreate, StudentStatus, Parent, ParentCreate, StudentParent
from models.classroom import Class
from models.school import School
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles, get_password_hash
from services.csv_import_service import CSVImportService

router = APIRouter(prefix="/students", tags=["Students"])


def _normalize_name(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = re.sub(r'[^a-z0-9]+', '', cleaned)
    return cleaned


async def _get_school_short_code(school_id: str, session: AsyncSession) -> str:
    if not school_id:
        return 'school'
    result = await session.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school or not getattr(school, 'code', None):
        return 'school'
    return str(school.code).strip().lower()


async def _create_portal_user(
    first_name: str,
    last_name: str,
    school_id: str,
    role: UserRole,
    session: AsyncSession
):
    from sqlalchemy.exc import IntegrityError
    
    school_short = await _get_school_short_code(school_id, session)
    base_local_part = f"{_normalize_name(first_name)}.{_normalize_name(last_name)}"

    email = f"{base_local_part}@{school_short}.school.edu.gh"
    suffix = 1

    while True:
        user_exists = await session.execute(select(User).where(User.email == email))
        if not user_exists.scalar_one_or_none():
            break
        email = f"{base_local_part}{suffix}@{school_short}.school.edu.gh"
        suffix += 1

    password = secrets.token_urlsafe(10)
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        plain_text_password=password,  # Store plain text for admin access
        first_name=first_name,
        last_name=last_name,
        role=role,
        school_id=school_id,
        is_active=True
    )
    
    try:
        session.add(user)
        await session.flush()
    except IntegrityError:
        # Handle race condition - email already exists, fetch it instead
        await session.rollback()
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            return existing_user, existing_user.plain_text_password or "N/A"
        # If still not found, try with suffix
        email = f"{base_local_part}{suffix}@{school_short}.school.edu.gh"
        user.email = email
        session.add(user)
        await session.flush()

    return user, password


@router.post("", response_model=dict)
async def create_student(
    student_data: StudentCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    result = await session.execute(
        select(Student).where(
            Student.school_id == school_id,
            Student.student_id == student_data.student_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Student ID already exists")
    
    student = Student(school_id=school_id, **student_data.model_dump())
    session.add(student)
    await session.flush()

    portal_user, portal_password = await _create_portal_user(
        first_name=student.first_name,
        last_name=student.last_name,
        school_id=school_id,
        role=UserRole.STUDENT,
        session=session
    )

    student.user_id = portal_user.id
    session.add(student)
    await session.commit()
    await session.refresh(student)

    return {
        "id": student.id,
        "school_id": student.school_id,
        "student_id": student.student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "status": student.status,
        "created_at": student.created_at.isoformat(),
        "portal_account": {
            "email": portal_user.email,
            "password": portal_password
        }
    }


@router.post("/import", response_model=dict)
async def import_students_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Import students from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    # Read file content
    content = await file.read()
    
    # Import students
    import_service = CSVImportService(session, school_id, current_user)
    result = await import_service.import_students(content) 

    # 🔹 DEBUG: Print all row-level errors
    print("CSV Import Errors:", result.get("errors"))
    
    if not result['success'] and result['success_count'] == 0:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.get("", response_model=dict)
async def list_students(
    class_id: Optional[str] = None,
    status: Optional[StudentStatus] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List students with pagination"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Student)
    count_query = select(func.count(Student.id))
    
    if school_id:
        query = query.where(Student.school_id == school_id)
        count_query = count_query.where(Student.school_id == school_id)
    
    if class_id:
        query = query.where(Student.class_id == class_id)
        count_query = count_query.where(Student.class_id == class_id)
    
    if status:
        query = query.where(Student.status == status)
        count_query = count_query.where(Student.status == status)
    
    if search:
        search_filter = (
            Student.first_name.ilike(f"%{search}%") |
            Student.last_name.ilike(f"%{search}%") |
            Student.student_id.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Student.first_name)
    
    result = await session.execute(query)
    students = result.scalars().all()
    
    class_ids = [s.class_id for s in students if s.class_id]
    class_names = {}
    if class_ids:
        class_result = await session.execute(select(Class).where(Class.id.in_(class_ids)))
        for c in class_result.scalars().all():
            class_names[c.id] = c.name
    
    return {
        "items": [
            {
                "id": s.id,
                "school_id": s.school_id,
                "student_id": s.student_id,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "full_name": f"{s.first_name} {s.last_name}",
                "date_of_birth": s.date_of_birth,
                "gender": s.gender,
                "admission_date": s.admission_date,
                "class_id": s.class_id,
                "class_name": class_names.get(s.class_id, "Unassigned"),
                "status": s.status,
                "photo_url": s.photo_url
            }
            for s in students
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/{student_id}", response_model=dict)
async def get_student(
    student_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get student details"""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")

    portal_account = None
    if student.user_id:
        result_user = await session.execute(select(User).where(User.id == student.user_id))
        portal_user = result_user.scalar_one_or_none()
        if portal_user:
            portal_account = {
                "email": portal_user.email,
                "password": portal_user.plain_text_password
            }
    else:
        portal_user, portal_password = await _create_portal_user(
            first_name=student.first_name,
            last_name=student.last_name,
            school_id=student.school_id,
            role=UserRole.STUDENT,
            session=session
        )
        student.user_id = portal_user.id
        session.add(student)
        await session.commit()
        portal_account = {
            "email": portal_user.email,
            "password": portal_password
        }
    
    class_name = "Unassigned"
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        if cls:
            class_name = cls.name
    
    parent_links = await session.execute(
        select(StudentParent).where(StudentParent.student_id == student_id)
    )
    parent_ids = [p.parent_id for p in parent_links.scalars().all()]
    
    parents = []
    if parent_ids:
        parent_result = await session.execute(select(Parent).where(Parent.id.in_(parent_ids)))
        parent_objects = parent_result.scalars().all()

        for p in parent_objects:
            parent_portal = None
            if p.user_id:
                user_result = await session.execute(select(User).where(User.id == p.user_id))
                user_obj = user_result.scalar_one_or_none()
                if user_obj:
                    parent_portal = {"email": user_obj.email, "password": user_obj.plain_text_password}
            else:
                portal_user, portal_password = await _create_portal_user(
                    first_name=p.first_name,
                    last_name=p.last_name,
                    school_id=p.school_id,
                    role=UserRole.PARENT,
                    session=session
                )
                p.user_id = portal_user.id
                session.add(p)
                await session.commit()
                parent_portal = {"email": portal_user.email, "password": portal_password}

            parents.append({
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "relationship": p.relationship,
                "phone": p.phone,
                "email": p.email,
                "is_emergency_contact": p.is_emergency_contact,
                "portal_account": parent_portal
            })
    
    return {
        "id": student.id,
        "school_id": student.school_id,
        "student_id": student.student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "full_name": f"{student.first_name} {student.last_name}",
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "admission_date": student.admission_date,
        "class_id": student.class_id,
        "class_name": class_name,
        "address": student.address,
        "nationality": student.nationality,
        "religion": student.religion,
        "blood_group": student.blood_group,
        "medical_conditions": student.medical_conditions,
        "status": student.status,
        "photo_url": student.photo_url,
        "portal_account": portal_account,
        "parents": parents,
        "created_at": student.created_at.isoformat()
    }


@router.put("/{student_id}", response_model=dict)
async def update_student(
    student_id: str,
    student_data: StudentCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update student details"""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in student_data.model_dump().items():
        setattr(student, key, value)
    
    student.updated_at = datetime.utcnow()
    session.add(student)
    await session.commit()
    
    return {"message": "Student updated successfully"}


@router.put("/{student_id}/class", response_model=dict)
async def assign_student_to_class(
    student_id: str,
    class_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Assign student to a class"""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    student.class_id = class_id
    student.updated_at = datetime.utcnow()
    session.add(student)
    await session.commit()
    
    return {"message": f"Student assigned to {cls.name}"}


@router.get("/{student_id}/parents", response_model=list)
async def get_student_parents(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Get parents linked to a student"""
    # Verify student exists
    try:
        result = await session.execute(select(Student).where(Student.id == student_id))
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get student-parent relationships
        result = await session.execute(
            select(StudentParent).where(StudentParent.student_id == student_id)
        )
        student_parents = result.scalars().all()
        
        if not student_parents:
            return []
        
        # Get parent details
        parent_ids = [sp.parent_id for sp in student_parents]
        result = await session.execute(
            select(Parent).where(Parent.id.in_(parent_ids))
        )
        parents = result.scalars().all()

        parent_payload = []
        for p in parents:
            parent_portal = None
            if p.user_id:
                user_result = await session.execute(select(User).where(User.id == p.user_id))
                user_obj = user_result.scalar_one_or_none()
                if user_obj:
                    parent_portal = {
                        "email": user_obj.email,
                        "password": user_obj.plain_text_password
                    }
            else:
                portal_user, portal_password = await _create_portal_user(
                    first_name=p.first_name,
                    last_name=p.last_name,
                    school_id=student.school_id,
                    role=UserRole.PARENT,
                    session=session
                )
                p.user_id = portal_user.id
                session.add(p)
                await session.commit()
                parent_portal = {
                    "email": portal_user.email,
                    "password": portal_password
                }

            parent_payload.append({
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "relationship": p.relationship,
                "phone": p.phone,
                "email": p.email,
                "occupation": p.occupation,
                "address": p.address,
                "is_emergency_contact": p.is_emergency_contact,
                "portal_account": parent_portal
            })

        return parent_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{student_id}/parents", response_model=dict)
async def add_parent(
    student_id: str,
    parent_data: ParentCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Add a parent/guardian to a student"""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    parent = Parent(school_id=student.school_id, **parent_data.model_dump())
    session.add(parent)
    await session.flush()

    portal_user, portal_password = await _create_portal_user(
        first_name=parent.first_name,
        last_name=parent.last_name,
        school_id=student.school_id,
        role=UserRole.PARENT,
        session=session
    )

    parent.user_id = portal_user.id
    link = StudentParent(student_id=student_id, parent_id=parent.id)
    session.add(link)
    session.add(parent)
    await session.commit()
    await session.refresh(parent)

    return {
        "id": parent.id,
        "first_name": parent.first_name,
        "last_name": parent.last_name,
        "message": "Parent added successfully",
        "portal_account": {
            "email": portal_user.email,
            "password": portal_password
        }
    }


@router.post("/{student_id}/parents/{parent_id}/link", response_model=dict)
async def link_existing_parent(
    student_id: str,
    parent_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Link an existing parent to another student"""
    # Verify student exists
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Verify parent exists
    result = await session.execute(select(Parent).where(Parent.id == parent_id))
    parent = result.scalar_one_or_none()
    
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    
    # Check if parent is already linked to this student
    result = await session.execute(
        select(StudentParent).where(
            StudentParent.student_id == student_id,
            StudentParent.parent_id == parent_id
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Parent is already linked to this student")
    
    # Create the link
    link = StudentParent(student_id=student_id, parent_id=parent_id)
    session.add(link)
    await session.commit()
    
    return {
        "message": "Parent linked to student successfully",
        "student_id": student_id,
        "parent_id": parent_id
    }


@router.post("/{student_id}/portal-credentials", response_model=dict)
async def regenerate_student_portal_credentials(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Regenerate portal credentials for a student"""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete existing user if exists
    if student.user_id:
        existing_user_result = await session.execute(select(User).where(User.id == student.user_id))
        existing_user = existing_user_result.scalar_one_or_none()
        if existing_user:
            await session.delete(existing_user)
    
    # Create new user
    portal_user, portal_password = await _create_portal_user(
        first_name=student.first_name,
        last_name=student.last_name,
        school_id=student.school_id,
        role=UserRole.STUDENT,
        session=session
    )
    
    student.user_id = portal_user.id
    session.add(student)
    await session.commit()
    
    return {
        "portal_account": {
            "email": portal_user.email,
            "password": portal_password
        }
    }


@router.post("/{student_id}/parents/{parent_id}/portal-credentials", response_model=dict)
async def regenerate_parent_portal_credentials(
    student_id: str,
    parent_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Regenerate portal credentials for a parent"""
    # Verify student exists and access
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Verify parent exists and is linked to student
    parent_result = await session.execute(select(Parent).where(Parent.id == parent_id))
    parent = parent_result.scalar_one_or_none()
    
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    
    link_result = await session.execute(
        select(StudentParent).where(
            StudentParent.student_id == student_id,
            StudentParent.parent_id == parent_id
        )
    )
    link = link_result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Parent not linked to this student")
    
    # Delete existing user if exists
    if parent.user_id:
        existing_user_result = await session.execute(select(User).where(User.id == parent.user_id))
        existing_user = existing_user_result.scalar_one_or_none()
        if existing_user:
            await session.delete(existing_user)
    
    # Create new user
    portal_user, portal_password = await _create_portal_user(
        first_name=parent.first_name,
        last_name=parent.last_name,
        school_id=parent.school_id,
        role=UserRole.PARENT,
        session=session
    )
    
    parent.user_id = portal_user.id
    session.add(parent)
    await session.commit()
    
    return {
        "portal_account": {
            "email": portal_user.email,
            "password": portal_password
        }
    }

