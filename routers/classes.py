"""Classes and Subjects router"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from models.classroom import Class, ClassCreate, ClassLevel, Subject, SubjectCreate, SubjectCategory, ClassSubject
from models.student import Student
from models.staff import Staff, TeacherAssignment
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/classes", tags=["Classes & Subjects"])


@router.post("", response_model=dict)
async def create_class(
    class_data: ClassCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new class"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    cls = Class(school_id=school_id, **class_data.model_dump())
    session.add(cls)
    await session.commit()
    await session.refresh(cls)
    
    return {
        "id": cls.id,
        "school_id": cls.school_id,
        "name": cls.name,
        "level": cls.level,
        "section": cls.section,
        "capacity": cls.capacity,
        "room_number": cls.room_number,
        "is_active": cls.is_active,
        "created_at": cls.created_at.isoformat()
    }


@router.get("", response_model=list[dict])
async def list_classes(
    level: Optional[ClassLevel] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all classes"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Class)
    
    if school_id:
        query = query.where(Class.school_id == school_id)
    
    if level:
        query = query.where(Class.level == level)
    
    if is_active is not None:
        query = query.where(Class.is_active == is_active)
    
    query = query.order_by(Class.level, Class.name)
    
    result = await session.execute(query)
    classes = result.scalars().all()
    
    class_student_counts = {}
    for cls in classes:
        count_result = await session.execute(
            select(func.count(Student.id)).where(Student.class_id == cls.id)
        )
        class_student_counts[cls.id] = count_result.scalar()
    
    return [
        {
            "id": c.id,
            "school_id": c.school_id,
            "name": c.name,
            "level": c.level,
            "section": c.section,
            "capacity": c.capacity,
            "room_number": c.room_number,
            "is_active": c.is_active,
            "student_count": class_student_counts.get(c.id, 0)
        }
        for c in classes
    ]


@router.get("/{class_id}", response_model=dict)
async def get_class(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get class details with students and teachers"""
    result = await session.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != cls.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    student_result = await session.execute(
        select(Student).where(Student.class_id == class_id).order_by(Student.first_name)
    )
    students = student_result.scalars().all()
    
    subject_links = await session.execute(
        select(ClassSubject).where(ClassSubject.class_id == class_id)
    )
    class_subjects_list = subject_links.scalars().all()
    
    class_subjects = []
    if class_subjects_list:
        for cs in class_subjects_list:
            subject_result = await session.execute(select(Subject).where(Subject.id == cs.subject_id))
            subject = subject_result.scalar_one_or_none()
            if subject:
                class_subjects.append({
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "subject_code": subject.code,
                    "subject_category": subject.category,
                    "academic_term_id": cs.academic_term_id
                })
    
    # Legacy subjects list for backward compatibility
    subjects = []
    if class_subjects_list:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_([cs.subject_id for cs in class_subjects_list])))
        subjects = [
            {"id": s.id, "name": s.name, "code": s.code, "category": s.category}
            for s in subject_result.scalars().all()
        ]
    
    # Get teacher assignments
    assignments_result = await session.execute(
        select(TeacherAssignment).where(TeacherAssignment.class_id == class_id)
    )
    assignments = []
    for assignment in assignments_result.scalars().all():
        staff_result = await session.execute(select(Staff).where(Staff.id == assignment.staff_id))
        staff = staff_result.scalar_one_or_none()
        
        subject_result = await session.execute(select(Subject).where(Subject.id == assignment.subject_id))
        subject = subject_result.scalar_one_or_none()
        
        if staff and subject:
            assignments.append({
                "id": assignment.id,
                "staff_id": assignment.staff_id,
                "teacher_name": f"{staff.first_name} {staff.last_name}",
                "subject_id": assignment.subject_id,
                "subject_name": subject.name,
                "academic_term_id": assignment.academic_term_id,
                "is_class_teacher": assignment.is_class_teacher
            })
    
    return {
        "id": cls.id,
        "school_id": cls.school_id,
        "name": cls.name,
        "level": cls.level,
        "section": cls.section,
        "capacity": cls.capacity,
        "room_number": cls.room_number,
        "is_active": cls.is_active,
        "students": [
            {
                "id": s.id,
                "student_id": s.student_id,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "gender": s.gender,
                "photo_url": s.photo_url
            }
            for s in students
        ],
        "class_subjects": class_subjects,
        "subjects": subjects,
        "teachers": assignments,
        "student_count": len(students)
    }


@router.get("/{class_id}/students", response_model=dict)
async def get_class_students(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all students in a specific class"""
    # Verify class exists
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != cls.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get students in this class
    student_result = await session.execute(
        select(Student).where(Student.class_id == class_id)
    )
    students = student_result.scalars().all()
    
    return {
        "items": [
            {
                "id": s.id,
                "student_id": s.student_id,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "photo_url": s.photo_url,
                "status": s.status
            }
            for s in students
        ],
        "total": len(students)
    }


@router.put("/{class_id}", response_model=dict)
async def update_class(
    class_id: str,
    class_data: ClassCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update class details"""
    result = await session.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != cls.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in class_data.model_dump().items():
        setattr(cls, key, value)
    
    cls.updated_at = datetime.utcnow()
    session.add(cls)
    await session.commit()
    
    return {"message": "Class updated successfully"}


# Subjects
@router.post("/subjects", response_model=dict)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new subject"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    subject = Subject(school_id=school_id, **subject_data.model_dump())
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    
    return {
        "id": subject.id,
        "school_id": subject.school_id,
        "name": subject.name,
        "code": subject.code,
        "category": subject.category,
        "description": subject.description,
        "credit_hours": subject.credit_hours,
        "is_active": subject.is_active
    }


@router.get("/subjects/all", response_model=list[dict])
async def list_subjects(
    category: Optional[SubjectCategory] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all subjects"""
    school_id = current_user.school_id
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Subject).where(Subject.school_id == school_id, Subject.is_active == True)
    
    if category:
        query = query.where(Subject.category == category)
    
    query = query.order_by(Subject.name)
    
    result = await session.execute(query)
    subjects = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "school_id": s.school_id,
            "name": s.name,
            "code": s.code,
            "category": s.category,
            "description": s.description,
            "credit_hours": s.credit_hours,
            "is_active": s.is_active
        }
        for s in subjects
    ]


@router.post("/{class_id}/subjects/{subject_id}", response_model=dict)
async def assign_subject_to_class(
    class_id: str,
    subject_id: str,
    academic_term_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Assign a subject to a class"""
    school_id = current_user.school_id
    
    existing = await session.execute(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.academic_term_id == academic_term_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Subject already assigned to this class")
    
    link = ClassSubject(
        school_id=school_id,
        class_id=class_id,
        subject_id=subject_id,
        academic_term_id=academic_term_id
    )
    session.add(link)
    await session.commit()
    
    return {"message": "Subject assigned to class"}


@router.delete("/{class_id}/subjects/{subject_id}", response_model=dict)
async def remove_subject_from_class(
    class_id: str,
    subject_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Remove a subject from a class"""
    result = await session.execute(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id
        )
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Subject not assigned to this class")
    
    await session.delete(link)
    await session.commit()
    
    return {"message": "Subject removed from class"}
