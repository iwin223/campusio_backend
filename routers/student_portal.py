"""Student Portal Router - API endpoints for students to view their own information"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
from models.user import User, UserRole
from models.student import Student
from models.grade import Grade
from models.fee import Fee, FeePayment, FeeStructure, PaymentStatus
from models.attendance import Attendance, AttendanceStatus
from models.classroom import Class, Subject
from models.timetable import Timetable, Period, DayOfWeek
from models.communication import Announcement
from models.staff import Staff
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/student-portal", tags=["Student Portal"])


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


async def get_student_record(user: User, session: AsyncSession) -> Student:
    """Get student record linked to user"""
    result = await session.execute(
        select(Student).where(Student.user_id == user.id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")
    return student


@router.get("/profile", response_model=dict)
async def get_my_profile(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's own profile"""
    student = await get_student_record(current_user, session)
    
    # Get class info
    class_name = None
    class_level = None
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        if cls:
            class_name = cls.name
            class_level = cls.level
    
    return {
        "id": student.id,
        "student_id": student.student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "full_name": f"{student.first_name} {student.last_name}",
        "date_of_birth": student.date_of_birth if student.date_of_birth else None,
        "gender": student.gender,
        "class_id": student.class_id,
        "class_name": class_name,
        "class_level": class_level,
        "admission_date": student.admission_date if student.admission_date else None,
        "status": student.status,
        "email": current_user.email
    }


@router.get("/dashboard", response_model=dict)
async def get_student_dashboard(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student dashboard overview"""
    student = await get_student_record(current_user, session)
    
    # Get class info
    class_name = None
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        class_name = cls.name if cls else None
    
    # Get attendance stats (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.student_id == student.id,
            Attendance.created_at >= thirty_days_ago
        )
    )
    attendance_records = attendance_result.scalars().all()
    
    present_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.PRESENT)
    total_days = len(attendance_records)
    attendance_rate = round((present_count / total_days * 100) if total_days > 0 else 0, 1)
    
    # Get grades stats
    grades_result = await session.execute(
        select(Grade).where(Grade.student_id == student.id)
    )
    grades = grades_result.scalars().all()
    
    total_score = sum(g.score for g in grades)
    total_max = sum(g.max_score for g in grades)
    overall_avg = round((total_score / total_max * 100) if total_max > 0 else 0, 1)
    overall_grade = get_letter_grade(overall_avg)
    
    # Get fee balance
    fee_result = await session.execute(
        select(Fee).where(Fee.student_id == student.id)
    )
    fees = fee_result.scalars().all()
    total_due = sum(f.amount_due for f in fees)
    total_paid = sum(f.amount_paid for f in fees)
    fee_balance = total_due - total_paid
    
    # Get upcoming classes (today's timetable)
    today = datetime.utcnow().strftime('%A').lower()
    timetable_result = await session.execute(
        select(Timetable).where(
            Timetable.class_id == student.class_id,
            Timetable.day_of_week == today
        )
    )
    today_classes = timetable_result.scalars().all()
    
    # Get recent announcements
    announcement_result = await session.execute(
        select(Announcement).where(
            Announcement.school_id == student.school_id,
            Announcement.is_published == True,
            Announcement.audience.in_(["all", "students"])
        ).order_by(Announcement.publish_date.desc()).limit(3)
    )
    recent_announcements = announcement_result.scalars().all()
    
    return {
        "student": {
            "id": student.id,
            "name": f"{student.first_name} {student.last_name}",
            "student_id": student.student_id,
            "class_name": class_name
        },
        "attendance": {
            "rate": attendance_rate,
            "present": present_count,
            "total_days": total_days
        },
        "academics": {
            "overall_average": overall_avg,
            "overall_grade": overall_grade["grade"],
            "grade_description": overall_grade["description"],
            "subjects_count": len(set(g.subject_id for g in grades)),
            "assessments_count": len(grades)
        },
        "fees": {
            "balance": fee_balance,
            "status": "paid" if fee_balance <= 0 else "outstanding"
        },
        "today_classes": len(today_classes),
        "recent_announcements": [
            {
                "id": a.id,
                "title": a.title,
                "type": a.announcement_type,
                "date": a.publish_date if a.publish_date else None
            }
            for a in recent_announcements
        ]
    }


@router.get("/grades", response_model=dict)
async def get_my_grades(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's own grades"""
    student = await get_student_record(current_user, session)
    
    # Get all grades
    grades_result = await session.execute(
        select(Grade).where(Grade.student_id == student.id)
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
        subject_code = subject.code if subject else "???"
        
        if subject_name not in grades_by_subject:
            grades_by_subject[subject_name] = {
                "subject_id": grade.subject_id,
                "subject_name": subject_name,
                "subject_code": subject_code,
                "assessments": [],
                "total_score": 0,
                "total_max": 0
            }
        
        percentage = round(grade.score / grade.max_score * 100, 1)
        letter = get_letter_grade(percentage)
        
        grades_by_subject[subject_name]["assessments"].append({
            "type": grade.assessment_type,
            "score": grade.score,
            "max_score": grade.max_score,
            "percentage": percentage,
            "grade": letter["grade"],
            "description": letter["description"],
            "date": grade.created_at.isoformat()
        })
        grades_by_subject[subject_name]["total_score"] += grade.score
        grades_by_subject[subject_name]["total_max"] += grade.max_score
    
    # Calculate averages and build subjects list
    subjects_list = []
    for name, data in grades_by_subject.items():
        avg = round((data["total_score"] / data["total_max"] * 100) if data["total_max"] > 0 else 0, 1)
        letter = get_letter_grade(avg)
        subjects_list.append({
            "subject_name": name,
            "subject_code": data["subject_code"],
            "assessments_count": len(data["assessments"]),
            "average_percentage": avg,
            "average_grade": letter["grade"],
            "average_description": letter["description"],
            "assessments": sorted(data["assessments"], key=lambda x: x["date"], reverse=True)
        })
    
    # Sort by subject name
    subjects_list.sort(key=lambda x: x["subject_name"])
    
    # Calculate overall average
    total_score = sum(g.score for g in grades)
    total_max = sum(g.max_score for g in grades)
    overall_avg = round((total_score / total_max * 100) if total_max > 0 else 0, 1)
    overall_grade = get_letter_grade(overall_avg)
    
    return {
        "overall": {
            "average": overall_avg,
            "grade": overall_grade["grade"],
            "description": overall_grade["description"],
            "total_assessments": len(grades),
            "total_subjects": len(subjects_list)
        },
        "subjects": subjects_list
    }


@router.get("/attendance", response_model=dict)
async def get_my_attendance(
    days: int = 30,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's own attendance history"""
    student = await get_student_record(current_user, session)
    
    # Get attendance records
    start_date = datetime.utcnow() - timedelta(days=days)
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.student_id == student.id,
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
    
    # Group by month
    monthly_stats = {}
    for record in records:
        month_key = record.attendance_date[:7] if record.attendance_date else "unknown"
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {"present": 0, "absent": 0, "late": 0, "total": 0}
        monthly_stats[month_key]["total"] += 1
        if record.status == AttendanceStatus.PRESENT:
            monthly_stats[month_key]["present"] += 1
        elif record.status == AttendanceStatus.ABSENT:
            monthly_stats[month_key]["absent"] += 1
        elif record.status == AttendanceStatus.LATE:
            monthly_stats[month_key]["late"] += 1
    
    return {
        "period_days": days,
        "summary": {
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "total_days": total,
            "attendance_rate": round(((present + late) / total * 100) if total > 0 else 0, 1)
        },
        "monthly": monthly_stats,
        "records": [
            {
                "date": r.attendance_date,
                "status": r.status,
                "remarks": r.remarks
            }
            for r in records
        ]
    }


@router.get("/timetable", response_model=dict)
async def get_my_timetable(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's class timetable"""
    student = await get_student_record(current_user, session)
    
    if not student.class_id:
        return {"message": "No class assigned", "schedule": {}, "periods": []}
    
    # Get class info
    class_result = await session.execute(select(Class).where(Class.id == student.class_id))
    classroom = class_result.scalar_one_or_none()
    
    # Get periods
    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == student.school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}
    
    # Get timetable entries
    timetable_result = await session.execute(
        select(Timetable).where(Timetable.class_id == student.class_id)
    )
    entries = timetable_result.scalars().all()
    
    # Get subjects and teachers
    subject_ids = list(set(e.subject_id for e in entries))
    teacher_ids = list(set(e.teacher_id for e in entries))
    
    subjects = {}
    if subject_ids:
        subj_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subj_result.scalars().all()}
    
    teachers = {}
    if teacher_ids:
        teacher_result = await session.execute(select(Staff).where(Staff.id.in_(teacher_ids)))
        teachers = {t.id: t for t in teacher_result.scalars().all()}
    
    # Build schedule
    schedule = {day.value: [] for day in DayOfWeek}
    
    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        teacher = teachers.get(entry.teacher_id)
        
        schedule[entry.day_of_week.value].append({
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_name": subject.name if subject else "Unknown",
            "subject_code": subject.code if subject else "???",
            "teacher_name": f"{teacher.first_name} {teacher.last_name}" if teacher else "TBA",
            "room": entry.room
        })
    
    # Sort each day's entries by period number
    for day in schedule:
        schedule[day].sort(key=lambda x: x["period_number"])
    
    return {
        "class_name": classroom.name if classroom else "Unknown",
        "class_level": classroom.level if classroom else None,
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "period_number": p.period_number,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "period_type": p.period_type
            }
            for p in sorted(periods.values(), key=lambda x: x.period_number)
        ],
        "schedule": schedule
    }


@router.get("/fees", response_model=dict)
async def get_my_fees(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's fee details"""
    student = await get_student_record(current_user, session)
    
    # Get fees
    fee_result = await session.execute(
        select(Fee).where(Fee.student_id == student.id)
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
            "payments_count": len(fee_payments)
        })
        total_due += fee.amount_due
        total_paid += fee.amount_paid
    
    return {
        "summary": {
            "total_due": total_due,
            "total_paid": total_paid,
            "balance": total_due - total_paid,
            "status": "paid" if total_due - total_paid <= 0 else "outstanding"
        },
        "fees": fees_list
    }


@router.get("/announcements", response_model=List[dict])
async def get_student_announcements(
    limit: int = 20,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get announcements for students"""
    student = await get_student_record(current_user, session)
    
    result = await session.execute(
        select(Announcement).where(
            Announcement.school_id == student.school_id,
            Announcement.is_published == True,
            Announcement.audience.in_(["all", "students"])
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
