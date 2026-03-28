"""Parent Portal Router - API endpoints for parents to view their children's information"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
from models.user import User, UserRole
from models.student import StudentParent, Parent,Student
from models.grade import Grade
from models.fee import Fee, FeePayment, FeeStructure, PaymentStatus
from models.attendance import Attendance, AttendanceStatus
from models.classroom import Class, Subject
from models.communication import Announcement
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/parent", tags=["Parent Portal"])


async def get_parent_children_ids(current_user: User, session: AsyncSession) -> List[str]:
    """Helper function to get student IDs for a parent's children"""
    # Get parent record linked to current user
    parent_result = await session.execute(
        select(Parent).where(Parent.user_id == current_user.id)
    )
    parent = parent_result.scalar_one_or_none()

    if not parent:
        return []

    # Get student-parent relationships
    student_parent_result = await session.execute(
        select(StudentParent).where(StudentParent.parent_id == parent.id)
    )
    student_parents = student_parent_result.scalars().all()

    return [sp.student_id for sp in student_parents]


async def verify_child_access(student_id: str, current_user: User, session: AsyncSession) -> Student:
    """Helper function to verify parent has access to a specific child"""
    children_ids = await get_parent_children_ids(current_user, session)

    if student_id not in children_ids:
        raise HTTPException(status_code=404, detail="Student not found or access denied")

    # Get student
    student_result = await session.execute(
        select(Student).where(Student.id == student_id)
    )
    student = student_result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return student


# GES Grading Scale
GES_GRADE_SCALE = [
    {"grade": "1", "min_score": 80, "max_score": 100, "description": "Excellent"},
    {"grade": "2", "min_score": 70, "max_score": 79, "description": "Very Good"},
    {"grade": "3", "min_score": 60, "max_score": 69, "description": "Good"},
    {"grade": "4", "min_score": 55, "max_score": 59, "description": "Credit"},
    {"grade": "5", "min_score": 50, "max_score": 54, "description": "Pass"},
    {"grade": "6", "min_score": 45, "max_score": 49, "description": "Weak Pass"},
    {"grade": "7", "min_score": 40, "max_score": 44, "description": "Very Weak"},
    {"grade": "8", "min_score": 35, "max_score": 39, "description": "Poor"},
    {"grade": "9", "min_score": 0, "max_score": 34, "description": "Fail"},
]


def get_letter_grade(percentage: float) -> dict:
    for grade in GES_GRADE_SCALE:
        if grade["min_score"] <= percentage <= grade["max_score"]:
            return grade
    return GES_GRADE_SCALE[-1]


@router.get("/children", response_model=List[dict])
async def get_my_children(
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get list of children linked to parent"""
    children_ids = await get_parent_children_ids(current_user, session)

    if not children_ids:
        return []

    # Get students
    students_result = await session.execute(
        select(Student).where(Student.id.in_(children_ids))
    )
    students = students_result.scalars().all()

    # Get class info
    class_ids = [s.class_id for s in students if s.class_id]
    classes = {}
    if class_ids:
        class_result = await session.execute(select(Class).where(Class.id.in_(class_ids)))
        classes = {c.id: c for c in class_result.scalars().all()}

    return [
        {
            "id": s.id,
            "student_id": s.student_id,
            "name": f"{s.first_name} {s.last_name}",
            "class_id": s.class_id,
            "class_name": classes.get(s.class_id, {}).name if s.class_id and classes.get(s.class_id) else None,
            "status": s.status,
            "admission_date": s.admission_date if s.admission_date else None
        }
        for s in students
    ]


@router.get("/child/{student_id}/overview", response_model=dict)
async def get_child_overview(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get overview of a child's information"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Get class info
    class_name = None
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        class_name = cls.name if cls else None
    
    # Get recent attendance (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.created_at >= thirty_days_ago
        )
    )
    attendance_records = attendance_result.scalars().all()
    
    present_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.LATE)
    total_days = len(attendance_records)
    attendance_rate = round((present_count / total_days * 100) if total_days > 0 else 0, 1)
    
    # Get fee balance
    fee_result = await session.execute(
        select(Fee).where(Fee.student_id == student_id)
    )
    fees = fee_result.scalars().all()
    total_due = sum(f.amount_due for f in fees)
    total_paid = sum(f.amount_paid for f in fees)
    fee_balance = total_due - total_paid
    
    # Get recent grades count
    grades_result = await session.execute(
        select(Grade).where(Grade.student_id == student_id)
    )
    grades = grades_result.scalars().all()
    
    return {
        "student": {
            "id": student.id,
            "student_id": student.student_id,
            "name": f"{student.first_name} {student.last_name}",
            "class_name": class_name,
            "status": student.status
        },
        "attendance": {
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "total_days": total_days,
            "attendance_rate": attendance_rate
        },
        "fees": {
            "total_due": total_due,
            "total_paid": total_paid,
            "balance": fee_balance,
            "status": "paid" if fee_balance <= 0 else "outstanding"
        },
        "academics": {
            "total_grades_recorded": len(grades)
        }
    }


@router.get("/child/{student_id}/grades", response_model=dict)
async def get_child_grades(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's grades"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Get grades
    grades_result = await session.execute(
        select(Grade).where(Grade.student_id == student_id)
    )
    grades = grades_result.scalars().all()
    
    # Get subjects
    subject_ids = list(set(g.subject_id for g in grades))
    subjects = {}
    if subject_ids:
        subj_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subj_result.scalars().all()}
    
    # Group by subject
    grades_by_subject = {}
    for grade in grades:
        subject = subjects.get(grade.subject_id)
        subject_name = subject.name if subject else "Unknown"
        
        if subject_name not in grades_by_subject:
            grades_by_subject[subject_name] = {
                "subject_id": grade.subject_id,
                "subject_name": subject_name,
                "grades": [],
                "total_score": 0,
                "total_max": 0
            }
        
        percentage = round(grade.score / grade.max_score * 100, 1)
        letter = get_letter_grade(percentage)
        
        grades_by_subject[subject_name]["grades"].append({
            "assessment_type": grade.assessment_type,
            "score": grade.score,
            "max_score": grade.max_score,
            "percentage": percentage,
            "grade": letter["grade"],
            "description": letter["description"],
            "date": grade.created_at.isoformat()
        })
        grades_by_subject[subject_name]["total_score"] += grade.score
        grades_by_subject[subject_name]["total_max"] += grade.max_score
    
    # Calculate averages
    subjects_list = []
    for name, data in grades_by_subject.items():
        avg = round((data["total_score"] / data["total_max"] * 100) if data["total_max"] > 0 else 0, 1)
        letter = get_letter_grade(avg)
        subjects_list.append({
            "subject_name": name,
            "grades_count": len(data["grades"]),
            "average_percentage": avg,
            "average_grade": letter["grade"],
            "average_description": letter["description"],
            "grades": data["grades"]
        })
    
    # Calculate overall average
    total_score = sum(g.score for g in grades)
    total_max = sum(g.max_score for g in grades)
    overall_avg = round((total_score / total_max * 100) if total_max > 0 else 0, 1)
    overall_grade = get_letter_grade(overall_avg)
    
    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "overall_average": overall_avg,
        "overall_grade": overall_grade["grade"],
        "overall_description": overall_grade["description"],
        "subjects": subjects_list
    }


@router.get("/child/{student_id}/fees", response_model=dict)
async def get_child_fees(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's fee details"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Get fees
    fee_result = await session.execute(
        select(Fee).where(Fee.student_id == student_id)
    )
    fees = fee_result.scalars().all()
    
    # Get fee structures
    structure_ids = list(set(f.fee_structure_id for f in fees))
    structures = {}
    if structure_ids:
        struct_result = await session.execute(select(FeeStructure).where(FeeStructure.id.in_(structure_ids)))
        structures = {s.id: s for s in struct_result.scalars().all()}
    
    # Get payments
    fee_ids = [f.id for f in fees]
    payments = []
    if fee_ids:
        payment_result = await session.execute(
            select(FeePayment).where(FeePayment.fee_id.in_(fee_ids))
        )
        payments = payment_result.scalars().all()
    
    # Build response
    fees_list = []
    total_due = 0
    total_paid = 0
    
    for fee in fees:
        structure = structures.get(fee.fee_structure_id)
        fee_payments = [p for p in payments if p.fee_id == fee.id]
        
        fees_list.append({
            "id": fee.id,
            "fee_type": structure.fee_type if structure else "unknown",
            "description": structure.description if structure else None,
            "amount_due": fee.amount_due,
            "amount_paid": fee.amount_paid,
            "balance": fee.amount_due - fee.amount_paid - fee.discount,
            "status": fee.status,
            "due_date": structure.due_date if structure else None,
            "payments": [
                {
                    "receipt_number": p.receipt_number,
                    "amount": p.amount,
                    "payment_date": p.payment_date,
                    "payment_method": p.payment_method
                }
                for p in fee_payments
            ]
        })
        total_due += fee.amount_due
        total_paid += fee.amount_paid
    
    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "summary": {
            "total_due": total_due,
            "total_paid": total_paid,
            "balance": total_due - total_paid,
            "collection_rate": round((total_paid / total_due * 100) if total_due > 0 else 100, 1)
        },
        "fees": fees_list
    }


@router.get("/child/{student_id}/attendance", response_model=dict)
async def get_child_attendance(
    student_id: str,
    days: int = 30,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's attendance history"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Get attendance
    start_date = datetime.utcnow() - timedelta(days=days)
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.created_at >= start_date
        ).order_by(Attendance.attendance_date.desc())
    )
    records = attendance_result.scalars().all()
    
    # Calculate summary
    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    excused = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
    total = len(records)
    
    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "period_days": days,
        "summary": {
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "total_days": total,
            "attendance_rate": round(((present + late) / total * 100) if total > 0 else 0, 1)
        },
        "records": [
            {
                "date": r.attendance_date,
                "status": r.status,
                "remarks": r.remarks,
                "recorded_at": r.created_at.isoformat()
            }
            for r in records
        ]
    }


@router.get("/announcements", response_model=List[dict])
async def get_announcements_for_parent(
    limit: int = 20,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get announcements relevant to parents"""
    school_id = current_user.school_id
    
    result = await session.execute(
        select(Announcement).where(
            Announcement.school_id == school_id,
            Announcement.is_published == True,
            Announcement.audience.in_(["all", "parents"])
        ).order_by(Announcement.publish_date.desc()).limit(limit)
    )
    announcements = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "announcement_type": a.announcement_type,
            "publish_date": a.publish_date if a.publish_date else None
        }
        for a in announcements
    ]
