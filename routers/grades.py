"""Grades and Report Cards router"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
from io import BytesIO
import logging

logger = logging.getLogger(__name__)
from models.grade import Grade, GradeCreate, AssessmentType, GradeScale, ReportCard
from models.student import Student,StudentParent,Parent
from models.classroom import Class, Subject, SubjectCreate, SubjectCategory, ClassSubject
from models.school import AcademicTerm, School
from models.attendance import Attendance, AttendanceStatus
from models.user import User, UserRole
from models.report_template import ReportTemplate
from database import get_session
from auth import get_current_user, require_roles
from services.report_card_pdf_service import ReportCardPDFService

router = APIRouter(prefix="/grades", tags=["Grades & Report Cards"])


# GES Grading Scale
GES_GRADE_SCALE = [
    {"grade": "1", "min_score": 80, "max_score": 100, "description": "Excellent", "gpa_point": 1.0, "interpretation": "Highest"},
    {"grade": "2", "min_score": 70, "max_score": 79, "description": "Very Good", "gpa_point": 2.0, "interpretation": "Above Average"},
    {"grade": "3", "min_score": 60, "max_score": 69, "description": "Good", "gpa_point": 3.0, "interpretation": "Average"},
    {"grade": "4", "min_score": 55, "max_score": 59, "description": "Credit", "gpa_point": 4.0, "interpretation": "Below Average"},
    {"grade": "5", "min_score": 50, "max_score": 54, "description": "Pass", "gpa_point": 5.0, "interpretation": "Pass"},
    {"grade": "6", "min_score": 45, "max_score": 49, "description": "Weak Pass", "gpa_point": 6.0, "interpretation": "Weak Pass"},
    {"grade": "7", "min_score": 40, "max_score": 44, "description": "Very Weak", "gpa_point": 7.0, "interpretation": "Very Weak"},
    {"grade": "8", "min_score": 35, "max_score": 39, "description": "Poor", "gpa_point": 8.0, "interpretation": "Poor"},
    {"grade": "9", "min_score": 0, "max_score": 34, "description": "Fail", "gpa_point": 9.0, "interpretation": "Lowest/Fail"},
]


def get_letter_grade(percentage: float) -> dict:
    """Convert percentage to GES grade"""
    for grade in GES_GRADE_SCALE:
        if grade["min_score"] <= percentage <= grade["max_score"]:
            return grade
    return GES_GRADE_SCALE[-1]  # Return fail grade if below 0


@router.get("/ges-scale", response_model=List[dict])
async def get_ges_grade_scale():
    """Get the GES (Ghana Education Service) grading scale"""
    return GES_GRADE_SCALE


@router.post("", response_model=dict)
async def record_grade(
    grade_data: GradeCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Record a grade for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    grade = Grade(
        school_id=school_id,
        recorded_by=current_user.id,
        **grade_data.model_dump()
    )
    session.add(grade)
    await session.commit()
    await session.refresh(grade)
    
    return {
        "grade_id": grade.id,
        "id": grade.id,
        "student_id": grade.student_id,
        "subject_id": grade.subject_id,
        "class_id": grade.class_id,
        "assessment_type": grade.assessment_type,
        "score": grade.score,
        "max_score": grade.max_score,
        "weight": grade.weight,
        "percentage": round(grade.score / grade.max_score * 100, 1),
        "recorded_at": grade.created_at.isoformat(),
        "message": "Grade recorded"
    }


@router.patch("/{grade_id}", response_model=dict)
async def update_grade(
    grade_id: str,
    grade_data: GradeCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Update a grade"""
    result = await session.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != grade.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update grade fields
    update_data = grade_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(grade, key, value)
    
    grade.updated_at = datetime.utcnow()
    session.add(grade)
    await session.commit()
    await session.refresh(grade)
    
    return {
        "grade_id": grade.id,
        "id": grade.id,
        "student_id": grade.student_id,
        "subject_id": grade.subject_id,
        "class_id": grade.class_id,
        "assessment_type": grade.assessment_type,
        "score": grade.score,
        "max_score": grade.max_score,
        "weight": grade.weight,
        "percentage": round(grade.score / grade.max_score * 100, 1),
        "recorded_at": grade.created_at.isoformat(),
        "updated_at": grade.updated_at.isoformat(),
        "message": "Grade updated"
    }


@router.delete("/{grade_id}", response_model=dict)
async def delete_grade(
    grade_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a grade"""
    result = await session.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != grade.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await session.delete(grade)
    await session.commit()
    
    return {"message": "Grade deleted successfully"}


@router.get("/student/{student_id}", response_model=dict)
async def get_student_grades(
    student_id: str,
    academic_term_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all grades for a student"""
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = select(Grade).where(Grade.student_id == student_id)
    
    if academic_term_id:
        query = query.where(Grade.academic_term_id == academic_term_id)
    if subject_id:
        query = query.where(Grade.subject_id == subject_id)
    
    result = await session.execute(query)
    grades = result.scalars().all()
    
    subject_ids = list(set(g.subject_id for g in grades))
    subject_names = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        for s in subject_result.scalars().all():
            subject_names[s.id] = s.name
    
    return {
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "grades": [
            {
                "id": g.id,
                "subject_id": g.subject_id,
                "subject_name": subject_names.get(g.subject_id, "Unknown"),
                "assessment_type": g.assessment_type,
                "score": g.score,
                "max_score": g.max_score,
                "percentage": round(g.score / g.max_score * 100, 1),
                "weight": g.weight,
                "remarks": g.remarks,
                "created_at": g.created_at.isoformat()
            }
            for g in grades
        ]
    }


@router.post("/scales", response_model=dict)
async def create_grade_scale(
    grade: str,
    min_score: float,
    max_score: float,
    description: str,
    gpa_point: float,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a grade scale entry"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    scale = GradeScale(
        school_id=school_id,
        grade=grade,
        min_score=min_score,
        max_score=max_score,
        description=description,
        gpa_point=gpa_point
    )
    session.add(scale)
    await session.commit()
    
    return {"message": "Grade scale created"}


# Subject Management Endpoints
@router.get("/subjects", response_model=List[dict])
async def get_subjects(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all subjects for school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Subject).where(Subject.school_id == school_id, Subject.is_active == True)
        .order_by(Subject.category, Subject.name)
    )
    subjects = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "category": s.category,
            "credit_hours": s.credit_hours,
            "description": s.description
        }
        for s in subjects
    ]


@router.post("/subjects", response_model=dict)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new subject"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    subject = Subject(
        school_id=school_id,
        **subject_data.model_dump()
    )
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    
    return {
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "message": "Subject created successfully"
    }


@router.post("/subjects/seed-defaults", response_model=dict)
async def seed_default_subjects(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Seed default GES subjects for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Check if subjects already exist
    existing = await session.execute(
        select(Subject).where(Subject.school_id == school_id).limit(1)
    )
    if existing.scalar_one_or_none():
        return {"message": "Subjects already exist", "created": 0}
    
    default_subjects = [
        # Core Subjects
        {"name": "English Language", "code": "ENG", "category": "core", "credit_hours": 5},
        {"name": "Mathematics", "code": "MATH", "category": "core", "credit_hours": 5},
        {"name": "Integrated Science", "code": "SCI", "category": "core", "credit_hours": 4},
        {"name": "Social Studies", "code": "SOC", "category": "core", "credit_hours": 4},
        {"name": "Computing/ICT", "code": "ICT", "category": "core", "credit_hours": 2},
        {"name": "Ghanaian Language", "code": "GHL", "category": "core", "credit_hours": 2},
        {"name": "Religious & Moral Education", "code": "RME", "category": "core", "credit_hours": 2},
        {"name": "Creative Arts", "code": "CRA", "category": "core", "credit_hours": 2},
        {"name": "Physical Education", "code": "PE", "category": "core", "credit_hours": 2},
        # Elective Subjects
        {"name": "French", "code": "FRE", "category": "elective", "credit_hours": 2},
        {"name": "Agriculture", "code": "AGR", "category": "elective", "credit_hours": 2},
        {"name": "Home Economics", "code": "HME", "category": "elective", "credit_hours": 2},
        {"name": "Basic Design & Technology", "code": "BDT", "category": "elective", "credit_hours": 2},
    ]
    
    created_count = 0
    for subj in default_subjects:
        subject = Subject(
            school_id=school_id,
            name=subj["name"],
            code=subj["code"],
            category=SubjectCategory(subj["category"]),
            credit_hours=subj["credit_hours"]
        )
        session.add(subject)
        created_count += 1
    
    await session.commit()
    
    return {"message": f"Created {created_count} default subjects", "created": created_count}


# Grade Recording by Class
@router.get("/class/{class_id}", response_model=dict)
async def get_class_grades(
    class_id: str,
    subject_id: Optional[str] = None,
    assessment_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all grades for a class"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get class info
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    classroom = class_result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Get students in class
    students_result = await session.execute(
        select(Student).where(Student.class_id == class_id, Student.status == "active")
        .order_by(Student.last_name, Student.first_name)
    )
    students = students_result.scalars().all()
    
    # Get grades for these students
    student_ids = [s.id for s in students]
    query = select(Grade).where(Grade.student_id.in_(student_ids))
    
    if subject_id:
        query = query.where(Grade.subject_id == subject_id)
    if assessment_type:
        query = query.where(Grade.assessment_type == assessment_type)
    
    grades_result = await session.execute(query)
    grades = grades_result.scalars().all()
    
    # Build grades lookup
    grades_by_student = {}
    for g in grades:
        if g.student_id not in grades_by_student:
            grades_by_student[g.student_id] = []
        grades_by_student[g.student_id].append(g)
    
    # Get subjects
    subject_ids = list(set(g.subject_id for g in grades))
    subject_names = {}
    if subject_ids:
        subj_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        for s in subj_result.scalars().all():
            subject_names[s.id] = s.name
    
    # Build response
    students_data = []
    for student in students:
        student_grades = grades_by_student.get(student.id, [])
        total_score = sum(g.score for g in student_grades)
        total_max = sum(g.max_score for g in student_grades)
        avg_percentage = (total_score / total_max * 100) if total_max > 0 else 0
        letter_grade = get_letter_grade(avg_percentage)
        
        students_data.append({
            "student_id": student.id,
            "student_name": f"{student.first_name} {student.last_name}",
            "student_number": student.student_id,
            "grades": [
                {
                    "id": g.id,
                    "grade_id": g.id,
                    "subject_id": g.subject_id,
                    "subject_name": subject_names.get(g.subject_id, "Unknown"),
                    "assessment_type": g.assessment_type,
                    "score": g.score,
                    "max_score": g.max_score,
                    "weight": g.weight,
                    "percentage": round(g.score / g.max_score * 100, 1),
                    "recorded_at": g.created_at.isoformat(),
                    "letter_grade": get_letter_grade(g.score / g.max_score * 100)["grade"]
                }
                for g in student_grades
            ],
            "average_percentage": round(avg_percentage, 1),
            "letter_grade": letter_grade["grade"],
            "grade_description": letter_grade["description"]
        })
    
    return {
        "class_id": class_id,
        "class_name": classroom.name,
        "subject_id": subject_id,
        "student_count": len(students),
        "students": students_data
    }


@router.post("/bulk", response_model=dict)
async def record_bulk_grades(
    grades_data: List[GradeCreate],
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Record multiple grades at once (e.g., entire class for an assessment)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    created_count = 0
    for grade_data in grades_data:
        grade = Grade(
            school_id=school_id,
            recorded_by=current_user.id,
            **grade_data.model_dump()
        )
        session.add(grade)
        created_count += 1
    
    await session.commit()
    
    return {
        "message": f"Recorded {created_count} grades successfully",
        "count": created_count
    }


@router.get("/scales", response_model=list[dict])
async def get_grade_scales(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get grade scales for school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(GradeScale).where(GradeScale.school_id == school_id).order_by(GradeScale.min_score.desc())
    )
    scales = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "grade": s.grade,
            "min_score": s.min_score,
            "max_score": s.max_score,
            "description": s.description,
            "gpa_point": s.gpa_point
        }
        for s in scales
    ]


@router.post("/report-cards/generate", response_model=dict)
async def generate_report_card(
    student_id: str,
    academic_term_id: str,
    class_teacher_remarks: Optional[str] = None,
    head_teacher_remarks: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Generate a report card for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get grades
    grades_result = await session.execute(
        select(Grade).where(
            Grade.student_id == student_id,
            Grade.academic_term_id == academic_term_id
        )
    )
    grades = grades_result.scalars().all()
    
    total_score = sum(g.score for g in grades)
    total_max = sum(g.max_score for g in grades)
    average_score = (total_score / total_max * 100) if total_max > 0 else 0
    
    # Get class size
    class_count_result = await session.execute(
        select(func.count(Student.id)).where(Student.class_id == student.class_id)
    )
    class_size = class_count_result.scalar() or 0
    
    # Get attendance percentage
    attendance_result = await session.execute(
        select(Attendance).where(Attendance.student_id == student_id)
    )
    attendance_records = attendance_result.scalars().all()
    total_days = len(attendance_records)
    present_days = sum(1 for a in attendance_records if a.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE])
    attendance_percentage = round(present_days / total_days * 100, 1) if total_days > 0 else 0
    
    # Create report card
    report_card = ReportCard(
        school_id=school_id,
        student_id=student_id,
        class_id=student.class_id,
        academic_term_id=academic_term_id,
        total_score=total_score,
        average_score=average_score,
        class_size=class_size,
        attendance_percentage=attendance_percentage,
        class_teacher_remarks=class_teacher_remarks,
        head_teacher_remarks=head_teacher_remarks,
        generated_by=current_user.id
    )
    session.add(report_card)
    await session.commit()
    await session.refresh(report_card)
    
    return {
        "id": report_card.id,
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "total_score": round(total_score, 1),
        "average_score": round(average_score, 1),
        "class_size": class_size,
        "attendance_percentage": attendance_percentage,
        "message": "Report card generated"
    }


@router.get("/report-cards/{student_id}/{academic_term_id}", response_model=dict)
async def get_report_card(
    student_id: str,
    academic_term_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a student's report card"""
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await session.execute(
        select(ReportCard).where(
            ReportCard.student_id == student_id,
            ReportCard.academic_term_id == academic_term_id
        )
    )
    report_card = result.scalar_one_or_none()
    
    if not report_card:
        raise HTTPException(status_code=404, detail="Report card not found")
    
    return {
        "id": report_card.id,
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "total_score": report_card.total_score,
        "average_score": report_card.average_score,
        "position": report_card.position,
        "class_size": report_card.class_size,
        "attendance_percentage": report_card.attendance_percentage,
        "class_teacher_remarks": report_card.class_teacher_remarks,
        "head_teacher_remarks": report_card.head_teacher_remarks,
        "generated_at": report_card.generated_at.isoformat()
    }


@router.get("/report-cards/{student_id}/{academic_term_id}/preview")
async def preview_report_card_html(
    student_id: str,
    academic_term_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Preview a student's report card as HTML (for modal display)"""
    try:
        # Verify student access
        student_result = await session.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Check access control based on user role
        has_access = False
        
        if current_user.role == UserRole.SUPER_ADMIN or current_user.role == UserRole.SCHOOL_ADMIN:
            # Admins can view any student in their school
            has_access = current_user.school_id == student.school_id
        elif current_user.role == UserRole.TEACHER:
            # Teachers can view students they teach
            has_access = current_user.school_id == student.school_id
        elif current_user.role == UserRole.PARENT:
            # Parents can only view their own children
            # First get the Parent record associated with the current user
            parent_result = await session.execute(
                select(Parent).where(Parent.user_id == current_user.id)
            )
            parent = parent_result.scalar_one_or_none()
            
            if parent:
                # Check if the student is linked to this parent
                student_parent_result = await session.execute(
                    select(StudentParent).where(
                        StudentParent.parent_id == parent.id, 
                        StudentParent.student_id == student_id
                    )
                )
                has_access = student_parent_result.scalar_one_or_none() is not None
        elif current_user.role == UserRole.STUDENT:
            # Students can only view their own report card
            has_access = current_user.id == student.user_id
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Access control error in preview_report_card_html: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Access control error: {str(e)}")
    
    # Get grades first (may be empty - that's ok for preview)
    grades_result = await session.execute(
        select(Grade).where(
            Grade.student_id == student_id,
            Grade.academic_term_id == academic_term_id
        )
    )
    grades = grades_result.scalars().all()
    
    # Allow preview even without grades - show empty/template report card
    
    # Get report card OR generate on demand if not found
    report_card_result = await session.execute(
        select(ReportCard).where(
            ReportCard.student_id == student_id,
            ReportCard.academic_term_id == academic_term_id
        )
    )
    report_card = report_card_result.scalar_one_or_none()
    
    # Auto-generate report card if it doesn't exist
    if not report_card:
        # Handle case with no grades - set scores to 0
        if grades:
            total_score = sum(g.score for g in grades)
            total_max = sum(g.max_score for g in grades)
            average_score = (total_score / total_max * 100) if total_max > 0 else 0
        else:
            total_score = 0
            total_max = 0
            average_score = 0
        
        # Get class size
        class_count_result = await session.execute(
            select(func.count(Student.id)).where(Student.class_id == student.class_id)
        )
        class_size = class_count_result.scalar() or 0
        
        # Get attendance percentage
        attendance_result = await session.execute(
            select(Attendance).where(Attendance.student_id == student_id)
        )
        attendance_records = attendance_result.scalars().all()
        total_days = len(attendance_records)
        present_days = sum(1 for a in attendance_records if a.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        attendance_percentage = round(present_days / total_days * 100, 1) if total_days > 0 else 0
        
        # Create report card on the fly
        report_card = ReportCard(
            school_id=student.school_id,
            student_id=student_id,
            class_id=student.class_id,
            academic_term_id=academic_term_id,
            total_score=total_score,
            average_score=average_score,
            class_size=class_size,
            attendance_percentage=attendance_percentage,
            generated_by=current_user.id
        )
        session.add(report_card)
        await session.commit()
        await session.refresh(report_card)
    
    # Get subjects
    subject_ids = list(set(g.subject_id for g in grades))
    subject_result = await session.execute(
        select(Subject).where(Subject.id.in_(subject_ids))
    )
    subjects = {s.id: s for s in subject_result.scalars().all()}
    
    # Get academic term name
    academic_term_result = await session.execute(
        select(AcademicTerm).where(AcademicTerm.id == academic_term_id)
    )
    academic_term = academic_term_result.scalar_one_or_none()
    # term_name = academic_term.id if academic_term else f"Term {academic_term_id}"
    
    # Get class name
    class_name = "Not Assigned"
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        class_obj = class_result.scalar_one_or_none()
        if class_obj:
            class_name = class_obj.name
    
    # Get school name
    school_result = await session.execute(select(School).where(School.id == student.school_id))
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "School Name"
    
    # Create student data object with all required fields
    student_data = {
        "id": student.id,
        "student_id": student.student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "school_id": student.school_id,
        "class_id": student.class_id,
        "class_name": class_name,
        "school_name": school_name,
    }
    
    # Format data for rendering
    report_data = ReportCardPDFService.format_grade_data(
        report_card=report_card,
        grades=grades,
        subjects_map=subjects,
        student=student_data,
        academic_term_name=None
    )
    
    # Always use default file template (not custom database templates)
    pdf_service = ReportCardPDFService()
    try:
        html_content = pdf_service.render_html(report_data, template_html=None)
    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to render report card: {error_msg}")
    
    # Return HTML response with report data
    return {
        "html": html_content,
        "student_name": f"{student.first_name} {student.last_name}",
        "academic_term": None,
        "can_download": True,
        "report_data": report_data,
        "subjects": report_data.get("subjects", []),
        "overall_average": report_data.get("overall_average", 0),
        "overall_grade": report_data.get("overall_grade", "N/A"),
        "overall_description": report_data.get("overall_description", "")
    }


@router.get("/report-cards/{student_id}/{academic_term_id}/download")
async def download_report_card_pdf(
    student_id: str,
    academic_term_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Download a student's report card as PDF"""
    # Verify student access
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check access control
    if current_user.role == UserRole.PARENT:
        # Parent can only view their own children
        student_parent_result = await session.execute(
            select(StudentParent).where(StudentParent.parent_id == current_user.id, StudentParent.student_id == student_id)
        ) 
        result = student_parent_result.scalar_one_or_none() 
        if result: 
            parent_result = result.parent_id == current_user.id

        if not parent_result:
                raise HTTPException(status_code=403, detail="Access denied") 
  
    elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER]:
        if current_user.school_id != student.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get report card
    report_card_result = await session.execute(
        select(ReportCard).where(
            ReportCard.student_id == student_id,
            ReportCard.academic_term_id == academic_term_id
        )
    )
    report_card = report_card_result.scalar_one_or_none()
    
    if not report_card:
        raise HTTPException(status_code=404, detail="Report card not found for this student and term")
    
    # Get grades (may be empty - that's ok)
    grades_result = await session.execute(
        select(Grade).where(
            Grade.student_id == student_id,
            Grade.academic_term_id == academic_term_id
        )
    )
    grades = grades_result.scalars().all()
    
    # Get subjects
    subject_ids = list(set(g.subject_id for g in grades))
    subject_result = await session.execute(
        select(Subject).where(Subject.id.in_(subject_ids))
    )
    subjects = {s.id: s for s in subject_result.scalars().all()}
    
    # Get academic term name
    academic_term_result = await session.execute(
        select(AcademicTerm).where(AcademicTerm.id == academic_term_id)
    )
    academic_term = academic_term_result.scalar_one_or_none()
    term_name = academic_term.name if academic_term else f"Term {academic_term_id}"
    
    # Get class name
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        class_obj = class_result.scalar_one_or_none()
        student.class_name = class_obj.name if class_obj else "Not Assigned"
    else:
        student.class_name = "Not Assigned"
    
    # Get school name
    school_result = await session.execute(select(School).where(School.id == student.school_id))
    school = school_result.scalar_one_or_none()
    student.school_name = school.name if school else "School Name"
    
    # Format data for PDF
    report_data = ReportCardPDFService.format_grade_data(
        report_card=report_card,
        grades=grades,
        subjects_map=subjects,
        student=student,
        academic_term_name=term_name
    )
    
    # Always use default file template (not custom database templates)
    pdf_service = ReportCardPDFService()
    try:
        pdf_bytes = pdf_service.generate_pdf(report_data, template_html=None)
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise HTTPException(status_code=500, detail="PDF generation produced empty output")
    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {error_msg}")
    
    # Return as downloadable PDF
    filename = f"reportcard_{student.student_id}_{academic_term_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/report-cards/{student_id}/{academic_term_id}/regenerate-pdf")
async def regenerate_report_card_pdf(
    student_id: str,
    academic_term_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Regenerate and download a report card PDF (teacher action)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify student
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found in your school")
    
    # Get or create report card
    report_card_result = await session.execute(
        select(ReportCard).where(
            ReportCard.student_id == student_id,
            ReportCard.academic_term_id == academic_term_id
        )
    )
    report_card = report_card_result.scalar_one_or_none()
    
    if not report_card:
        # Create new report card (grades may be empty, that's ok)
        grades_result = await session.execute(
            select(Grade).where(
                Grade.student_id == student_id,
                Grade.academic_term_id == academic_term_id
            )
        )
        grades = grades_result.scalars().all()
        
        total_score = sum(g.score for g in grades)
        total_max = sum(g.max_score for g in grades)
        average_score = (total_score / total_max * 100) if total_max > 0 else 0
        
        # Get class size
        class_count_result = await session.execute(
            select(func.count(Student.id)).where(Student.class_id == student.class_id)
        )
        class_size = class_count_result.scalar() or 0
        
        # Get attendance
        attendance_result = await session.execute(
            select(Attendance).where(Attendance.student_id == student_id)
        )
        attendance_records = attendance_result.scalars().all()
        total_days = len(attendance_records)
        present_days = sum(1 for a in attendance_records if a.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        attendance_percentage = round(present_days / total_days * 100, 1) if total_days > 0 else 0
        
        report_card = ReportCard(
            school_id=school_id,
            student_id=student_id,
            class_id=student.class_id,
            academic_term_id=academic_term_id,
            total_score=total_score,
            average_score=average_score,
            class_size=class_size,
            attendance_percentage=attendance_percentage,
            generated_by=current_user.id
        )
        session.add(report_card)
        await session.commit()
        await session.refresh(report_card)
    
    return {
        "id": report_card.id,
        "message": "Report card ready for PDF download",
        "download_url": f"/api/grades/report-cards/{student_id}/{academic_term_id}/download"
    }

