"""Student Portal Router - API endpoints for students to view their own information"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
import json
import uuid
from models.user import User, UserRole
from models.student import Student
from models.grade import Grade
from models.fee import Fee, FeePayment, FeeStructure, PaymentStatus
from models.attendance import Attendance, AttendanceStatus
from models.classroom import Class, Subject
from models.timetable import Timetable, Period, DayOfWeek
from models.communication import Announcement
from models.staff import Staff
from models.assignment import Assignment, Submission, SubmissionStatus, AssignmentStatus, AssignmentQuestion
from models.hostel import StudentHostel, HostelFee
from models.transport import StudentTransport, TransportFee, Route
from database import get_session
from auth import get_current_user, require_roles
from services.auto_grader import AutoGrader

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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student dashboard overview, optionally filtered by academic term"""
    student = await get_student_record(current_user, session)
    
    # Get class info
    class_name = None
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        class_name = cls.name if cls else None
    
    # Get attendance stats (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    attendance_query = select(Attendance).where(
        Attendance.student_id == student.id,
        Attendance.created_at >= thirty_days_ago
    )
    
    # Filter by term if provided
    if term_id:
        attendance_query = attendance_query.where(Attendance.academic_term_id == term_id)
    
    attendance_result = await session.execute(attendance_query)
    attendance_records = attendance_result.scalars().all()
    
    present_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.PRESENT)
    total_days = len(attendance_records)
    attendance_rate = round((present_count / total_days * 100) if total_days > 0 else 0, 1)
    
    # Get grades stats
    grades_query = select(Grade).where(Grade.student_id == student.id)
    
    # Filter by term if provided
    if term_id:
        grades_query = grades_query.where(Grade.academic_term_id == term_id)
    
    grades_result = await session.execute(grades_query)
    grades = grades_result.scalars().all()
    
    total_score = sum(g.score for g in grades)
    total_max = sum(g.max_score for g in grades)
    overall_avg = round((total_score / total_max * 100) if total_max > 0 else 0, 1)
    overall_grade = get_letter_grade(overall_avg)
    
    # Get fee balance
    fee_query = select(Fee).where(Fee.student_id == student.id)
    
    # Filter by term if provided
    if term_id:
        fee_query = fee_query.where(Fee.academic_term_id == term_id)
    
    fee_result = await session.execute(fee_query)
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's own grades, optionally filtered by academic term"""
    student = await get_student_record(current_user, session)
    
    # Build query to get grades
    query = select(Grade).where(Grade.student_id == student.id)
    
    # Filter by term if provided
    if term_id:
        query = query.where(Grade.academic_term_id == term_id)
    
    grades_result = await session.execute(query)
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's own attendance history, optionally filtered by academic term"""
    student = await get_student_record(current_user, session)
    
    # Build query for attendance
    query = select(Attendance).where(
        Attendance.student_id == student.id,
        Attendance.created_at >= datetime.utcnow() - timedelta(days=days)
    )
    
    # Filter by term if provided
    if term_id:
        query = query.where(Attendance.academic_term_id == term_id)
    
    query = query.order_by(Attendance.attendance_date.desc())
    
    attendance_result = await session.execute(query)
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's fee details, optionally filtered by academic term"""
    student = await get_student_record(current_user, session)
    
    # Build query for fees
    query = select(Fee).where(Fee.student_id == student.id)
    
    # Filter by term if provided
    if term_id:
        query = query.where(Fee.academic_term_id == term_id)
    
    fee_result = await session.execute(query)
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


# ============================================================================
# ASSIGNMENTS ENDPOINTS
# ============================================================================

@router.get("/assignments/my-assignments", response_model=dict)
async def get_my_assignments(
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get all assignments for the current student, optionally filtered by academic term"""
    student = await get_student_record(current_user, session)
    
    if not student.class_id:
        return {"assignments": [], "message": "No class assigned"}
    
    # Build query for assignments
    query = select(Assignment).where(
        Assignment.school_id == student.school_id,
        Assignment.class_id == student.class_id,
        Assignment.status == AssignmentStatus.PUBLISHED
    )
    
    # Filter by term if provided
    if term_id:
        query = query.where(Assignment.academic_term_id == term_id)
    
    query = query.order_by(Assignment.due_date)
    
    assignments_result = await session.execute(query)
    assignments = assignments_result.scalars().all()
    
    # Get student's submissions for these assignments
    submissions = {}
    if assignments:
        assignment_ids = [a.id for a in assignments]
        submissions_result = await session.execute(
            select(Submission).where(
                Submission.student_id == student.id,
                Submission.assignment_id.in_(assignment_ids)
            )
        )
        for sub in submissions_result.scalars().all():
            submissions[sub.assignment_id] = sub
    
    # Get teacher and subject info
    teacher_info = {}
    subject_info = {}
    
    assignment_list = []
    for assignment in assignments:
        # Get teacher name
        if assignment.teacher_id not in teacher_info:
            teacher_result = await session.execute(
                select(Staff).where(Staff.id == assignment.teacher_id)
            )
            staff = teacher_result.scalar_one_or_none()
            teacher_info[assignment.teacher_id] = f"{staff.first_name} {staff.last_name}" if staff else "Unknown"
        
        # Get subject name
        if assignment.subject_id not in subject_info:
            subject_result = await session.execute(
                select(Subject).where(Subject.id == assignment.subject_id)
            )
            subject = subject_result.scalar_one_or_none()
            subject_info[assignment.subject_id] = subject.name if subject else "Unknown"
        
        # Get questions for this assignment
        questions_result = await session.execute(
            select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id)
        )
        questions = questions_result.scalars().all()
        
# Format questions for response
        formatted_questions = []
        for q in questions:
            question_data = {
                "id": q.id,
                "question": q.question_text,
                "type": q.question_type,
                "answer": q.correct_answer,
                "points": q.points,
            }
            
            # Parse options if they exist
            if q.options:
                try:
                    if isinstance(q.options, str):
                        parsed = json.loads(q.options)
                    else:
                        parsed = q.options
                    
                    # For matching questions, split key=value pairs into options and items
                    if q.question_type == "matching":
                        options = []
                        items = []
                        for pair in parsed:
                            if "=" in str(pair):
                                key, value = str(pair).split("=", 1)
                                options.append(key)
                                items.append(value)
                            else:
                                options.append(pair)
                        question_data["options"] = options
                        question_data["items"] = items
                    else:
                        question_data["options"] = parsed
                        question_data["items"] = []  # Non-matching questions don't have items
                except:
                    question_data["options"] = []
                    question_data["items"] = []
            else:
                question_data["options"] = []
                question_data["items"] = []
            
            formatted_questions.append(question_data)
        
        submission = submissions.get(assignment.id)
        
        assignment_list.append({
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "subject_name": subject_info[assignment.subject_id],
            "teacher_name": teacher_info[assignment.teacher_id],
            "assignment_type": assignment.assignment_type,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "created_at": assignment.created_date.isoformat() if assignment.created_date else None,
            "submitted_at": submission.submission_date.isoformat() if submission and submission.submission_date else None,
            "graded": submission.status == SubmissionStatus.GRADED if submission else False,
            "score": submission.score if submission else None,
            "max_score": submission.max_score if submission else assignment.points_possible,
            "percentage": round((submission.score / (submission.max_score or assignment.points_possible)) * 100, 1) if submission and submission.score else None,
            "feedback": submission.feedback if submission else None,
            "graded_at": submission.graded_date.isoformat() if submission and submission.graded_date else None,
            "points_possible": assignment.points_possible,
            "questions": formatted_questions
        })
    
    return {
        "assignments": assignment_list,
        "message": f"Found {len(assignment_list)} assignments"
    }


@router.get("/assignments/{assignment_id}", response_model=dict)
async def get_assignment_detail(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get full assignment details with questions for a student"""
    student = await get_student_record(current_user, session)
    
    # Get assignment
    assignment_result = await session.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.school_id == student.school_id,
            Assignment.class_id == student.class_id,
            Assignment.status == AssignmentStatus.PUBLISHED
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or not accessible")
    
    # Get questions
    questions_result = await session.execute(
        select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment_id)
    )
    questions = questions_result.scalars().all()
    
    # Format questions for response
    formatted_questions = []
    for q in questions:
        question_data = {
            "id": q.id,
            "question": q.question_text,
            "type": q.question_type,
            "answer": q.correct_answer,
            "points": q.points,
        }
        
        # Parse options if they exist
        if q.options:
            try:
                if isinstance(q.options, str):
                    parsed = json.loads(q.options)
                else:
                    parsed = q.options
                
                # For matching questions, split key=value pairs into options and items
                if q.question_type == "matching":
                    options = []
                    items = []
                    for pair in parsed:
                        if "=" in str(pair):
                            key, value = str(pair).split("=", 1)
                            options.append(key)
                            items.append(value)
                        else:
                            options.append(pair)
                    question_data["options"] = options
                    question_data["items"] = items
                else:
                    question_data["options"] = parsed
                    question_data["items"] = []  # Non-matching questions don't have items
            except:
                question_data["options"] = []
                question_data["items"] = []
        else:
            question_data["options"] = []
            question_data["items"] = []
        
        formatted_questions.append(question_data)
    
    # Get teacher name
    teacher_result = await session.execute(
        select(Staff).where(Staff.id == assignment.teacher_id)
    )
    staff = teacher_result.scalar_one_or_none()
    teacher_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown"
    
    # Get subject name
    subject_result = await session.execute(
        select(Subject).where(Subject.id == assignment.subject_id)
    )
    subject = subject_result.scalar_one_or_none()
    subject_name = subject.name if subject else "Unknown"
    
    # Get student's submission if exists
    submission_result = await session.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student.id
        )
    )
    submission = submission_result.scalar_one_or_none()
    
    return {
        "assignment": {
            "id": assignment.id,
            "class_id": assignment.class_id,
            "subject_id": assignment.subject_id,
            "teacher_id": assignment.teacher_id,
            "title": assignment.title,
            "description": assignment.description,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "points_possible": assignment.points_possible,
            "total_points": assignment.points_possible,
            "instructions": assignment.instructions,
            "assignment_type": assignment.assignment_type,
            "status": assignment.status,
            "created_at": assignment.created_date.isoformat() if assignment.created_date else None,
            "teacher_name": teacher_name,
            "subject_name": subject_name,
            "questions": formatted_questions,
        },
        "submission": {
            "submitted_at": submission.submission_date.isoformat() if submission and submission.submission_date else None,
            "status": submission.status if submission else None,
            "score": submission.score if submission else None,
        } if submission else None,
        "message": "Assignment details retrieved successfully"
    }


@router.post("/assignments/{assignment_id}/submit", response_model=dict)
async def submit_assignment(
    assignment_id: str,
    submission_text: Optional[str] = None,
    answers: Optional[dict] = None,
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """
    Submit an assignment with either text/file or quiz answers.
    
    Args:
        submission_text: Text submission or answers JSON string
        answers: Dict of {question_id: answer} for quiz submissions
    """
    student = await get_student_record(current_user, session)
    
    # Get assignment
    assignment_result = await session.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = assignment_result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Verify student has access to this assignment
    if assignment.class_id != student.class_id or assignment.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this assignment")
    
    # Check if assignment is already graded - prevent resubmission
    existing_submission_result = await session.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student.id
        )
    )
    existing_submission = existing_submission_result.scalar_one_or_none()
    
    if existing_submission and existing_submission.status == SubmissionStatus.GRADED:
        raise HTTPException(
            status_code=400, 
            detail="This assignment has already been graded and cannot be submitted again"
        )
    
    # Prepare submission data
    answers_json = None
    auto_grade_data = None
    
    # If answers provided, store as JSON and attempt auto-grading
    if answers:
        answers_json = json.dumps(answers)
        
        # Get assignment questions for grading
        questions_result = await session.execute(
            select(AssignmentQuestion).where(
                AssignmentQuestion.assignment_id == assignment_id
            )
        )
        questions = questions_result.scalars().all()
        
        # Auto-grade if configured
        if assignment.rubric:
            try:
                rubric_settings = json.loads(assignment.rubric)
                if rubric_settings.get("allow_auto_grade", False):
                    auto_grader = AutoGrader()
                    auto_grade_data = await auto_grader.auto_grade_submission(
                        answers_json,
                        questions,
                        float(assignment.points_possible or 100)
                    )
            except:
                pass  # Continue without auto-grading if it fails
    
    # Get or create submission
    submission_result = await session.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student.id
        )
    )
    submission = submission_result.scalar_one_or_none()
    
    if not submission:
        # Create new submission
        submission = Submission(
            id=str(uuid.uuid4()),
            school_id=student.school_id,
            assignment_id=assignment_id,
            student_id=student.id,
            class_id=student.class_id,
            subject_id=assignment.subject_id,
            status=SubmissionStatus.SUBMITTED,
            submission_text=answers_json or submission_text,
            submission_date=datetime.utcnow(),
            max_score=assignment.points_possible
        )
        session.add(submission)
    else:
        # Update existing submission
        submission.submission_text = answers_json or submission_text
        submission.status = SubmissionStatus.SUBMITTED
        submission.submission_date = datetime.utcnow()
    
    # If auto-graded, set the score
    if auto_grade_data and auto_grade_data.get("can_full_auto_grade"):
        submission.score = auto_grade_data["total_score"]
        submission.status = SubmissionStatus.GRADED
        submission.graded_date = datetime.utcnow()
        # Store grading details in rubric_scores for reference
        submission.rubric_scores = json.dumps({
            "auto_graded": True,
            "question_scores": auto_grade_data["question_scores"],
            "feedback": auto_grade_data["feedback"]
        })
    
    await session.commit()
    await session.refresh(submission)
    
    response = {
        "message": "Assignment submitted successfully",
        "submission_id": submission.id,
        "status": submission.status,
        "submitted_at": submission.submission_date.isoformat() if submission.submission_date else None
    }
    
    # Include auto-grading results if available
    if auto_grade_data:
        response["auto_graded"] = True
        response["grading"] = {
            "score": auto_grade_data["total_score"],
            "max_score": auto_grade_data["max_score"],
            "percentage": auto_grade_data["percentage"],
            "feedback": auto_grade_data["feedback"],
            "can_full_auto_grade": auto_grade_data["can_full_auto_grade"]
        }
    
    return response

# ============================================================================
# OPTIONAL MODULES - ENROLLMENT STATUS ENDPOINTS
# ============================================================================

@router.get("/enrollment-status", response_model=dict)
async def get_enrollment_status(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Check which optional modules student is enrolled in"""
    student = await get_student_record(current_user, session)
    
    # Check hostel enrollment
    hostel_result = await session.execute(
        select(StudentHostel).where(
            StudentHostel.student_id == student.id,
            StudentHostel.school_id == student.school_id,
            StudentHostel.status == "active"
        )
    )
    has_hostel = hostel_result.scalar_one_or_none() is not None
    
    # Check transport enrollment
    transport_result = await session.execute(
        select(StudentTransport).where(
            StudentTransport.student_id == student.id,
            StudentTransport.school_id == student.school_id,
            StudentTransport.is_active == True
        )
    )
    has_transport = transport_result.scalar_one_or_none() is not None
    
    return {
        "has_hostel": has_hostel,
        "has_transport": has_transport,
        "enabled_modules": {
            "hostel": has_hostel,
            "transport": has_transport,
            "fees": True,
            "grades": True,
            "attendance": True,
            "assignments": True,
            "timetable": True
        }
    }


@router.get("/hostel/status", response_model=dict)
async def get_hostel_status(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's hostel info if enrolled"""
    student = await get_student_record(current_user, session)
    
    hostel_result = await session.execute(
        select(StudentHostel).where(
            StudentHostel.student_id == student.id,
            StudentHostel.school_id == student.school_id,
            StudentHostel.status == "active"
        )
    )
    hostel = hostel_result.scalar_one_or_none()
    
    if not hostel:
        raise HTTPException(status_code=404, detail="Not enrolled in hostel")
    
    # Get recent fees for this hostel
    fees_result = await session.execute(
        select(HostelFee).where(
            HostelFee.student_id == student.id,
            HostelFee.school_id == student.school_id
        ).order_by(HostelFee.created_at.desc()).limit(10)
    )
    fees = fees_result.scalars().all()
    
    return {
        "enrolled": True,
        "hostel_id": hostel.hostel_id,
        "assigned_date": hostel.check_in_date,
        "room_number": hostel.room_id or "TBA",
        "academic_year": hostel.academic_year,
        "parent_contact": hostel.parent_contact,
        "emergency_contact": hostel.emergency_contact,
        "emergency_contact_phone": hostel.emergency_contact_phone,
        "recent_fees": [
            {
                "id": f.id,
                "fee_type": f.fee_type,
                "amount_due": f.amount_due,
                "amount_paid": f.amount_paid,
                "balance": f.amount_due - f.amount_paid - f.discount,
                "is_paid": f.is_paid,
                "due_date": f.due_date,
                "payment_date": f.payment_date,
                "payment_method": f.payment_method
            }
            for f in fees
        ]
    }


@router.get("/transport/status", response_model=dict)
async def get_transport_status(
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get student's transport info if enrolled"""
    student = await get_student_record(current_user, session)
    
    transport_result = await session.execute(
        select(StudentTransport).where(
            StudentTransport.student_id == student.id,
            StudentTransport.school_id == student.school_id,
            StudentTransport.is_active == True
        )
    )
    transport = transport_result.scalar_one_or_none()
    
    if not transport:
        raise HTTPException(status_code=404, detail="Not enrolled in transport")
    
    # Get route details
    route_result = await session.execute(
        select(Route).where(Route.id == transport.route_id)
    )
    route = route_result.scalar_one_or_none()
    
    # Get fees for this route
    fees_result = await session.execute(
        select(TransportFee).where(
            TransportFee.student_id == student.id,
            TransportFee.school_id == student.school_id
        ).order_by(TransportFee.created_at.desc()).limit(10)
    )
    fees = fees_result.scalars().all()
    
    return {
        "enrolled": True,
        "route_id": transport.route_id,
        "route_name": route.route_name if route else "Unknown",
        "pickup_point": transport.pickup_point or "N/A",
        "dropoff_point": transport.dropoff_point or "N/A",
        "enrollment_date": transport.enrollment_date,
        "emergency_contact": transport.emergency_contact,
        "emergency_contact_phone": transport.emergency_contact_phone,
        "recent_fees": [
            {
                "id": f.id,
                "fee_type": f.fee_type,
                "amount_due": f.amount_due,
                "amount_paid": f.amount_paid,
                "balance": f.amount_due - f.amount_paid - f.discount,
                "is_paid": f.is_paid,
                "due_date": f.due_date,
                "payment_date": f.payment_date,
                "payment_method": f.payment_method
            }
            for f in fees
        ]
    }