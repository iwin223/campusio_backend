"""Parent Portal Router - API endpoints for parents to view their children's information"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
from models.user import User, UserRole
from models.student import StudentParent, Student, Parent
from models.grade import Grade
from models.fee import Fee, FeePayment, FeeStructure, PaymentStatus
from models.attendance import Attendance, AttendanceStatus
from models.classroom import Class, Subject
from models.communication import Announcement
from models.assignment import Assignment, Submission, SubmissionStatus, AssignmentStatus
from models.staff import Staff
from models.hostel import StudentHostel, HostelFee, Room, Hostel
from models.transport import StudentTransport, TransportFee, Route
from database import get_session
from auth import get_current_user, require_roles
from services.assignment_performance import AssignmentPerformanceService

router = APIRouter(prefix="/parent", tags=["Parent Portal"])


async def get_parent_children_ids(current_user: User, session: AsyncSession) -> List[str]:
    """Helper function to get student IDs for a parent's children"""
    # 1. Get the Parent record linked to this User
    parent_result = await session.execute(
        select(Parent).where(Parent.user_id == current_user.id)
    )
    parent = parent_result.scalar_one_or_none()
    
    if not parent:
        return []
    
    # 2. Get student-parent relationships using the Parent's ID
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get overview of a child's information, optionally filtered by term"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Get class info
    class_name = None
    if student.class_id:
        class_result = await session.execute(select(Class).where(Class.id == student.class_id))
        cls = class_result.scalar_one_or_none()
        class_name = cls.name if cls else None
    
    # Get recent attendance (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    attendance_query = select(Attendance).where(
        Attendance.student_id == student_id,
        Attendance.created_at >= thirty_days_ago
    )
    
    # Filter by term if provided
    if term_id:
        attendance_query = attendance_query.where(Attendance.academic_term_id == term_id)
    
    attendance_result = await session.execute(attendance_query)
    attendance_records = attendance_result.scalars().all()
    
    present_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.LATE)
    total_days = len(attendance_records)
    attendance_rate = round((present_count / total_days * 100) if total_days > 0 else 0, 1)
    
    # Get fee balance
    fee_query = select(Fee).where(Fee.student_id == student_id)
    
    # Filter fees by term if provided
    if term_id:
        fee_query = fee_query.where(Fee.academic_term_id == term_id)
    
    fee_result = await session.execute(fee_query)
    fees = fee_result.scalars().all()
    total_due = sum(f.amount_due for f in fees)
    total_paid = sum(f.amount_paid for f in fees)
    fee_balance = total_due - total_paid
    
    # Get recent grades count
    grades_query = select(Grade).where(Grade.student_id == student_id)
    
    # Filter grades by term if provided
    if term_id:
        grades_query = grades_query.where(Grade.academic_term_id == term_id)
    
    grades_result = await session.execute(grades_query)
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's grades, optionally filtered by academic term"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Build query for grades
    query = select(Grade).where(Grade.student_id == student_id)
    
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
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's fee details, optionally filtered by academic term"""
    import sys
    print("=" * 80, file=sys.stderr)
    print(f"FEES ENDPOINT CALLED - student_id={student_id}, term_id={term_id}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    
    student = await verify_child_access(student_id, current_user, session)
    print(f"STUDENT FOUND: {student.first_name} {student.last_name}, class_id={student.class_id}", file=sys.stderr)
    
    # First, try to get fees directly assigned to the student
    query = select(Fee).where(Fee.student_id == student_id)
    
    # Filter by term if provided
    if term_id:
        query = query.where(Fee.academic_term_id == term_id)
    
    fee_result = await session.execute(query)
    fees = fee_result.scalars().all()
    print(f"DIRECT FEES: {len(fees)} found", file=sys.stderr)
    
    # If no direct fees found, try to get fees by class (fees are usually assigned at class level)
    if not fees and student.class_id:
        print(f"NO DIRECT FEES. Looking up class_id={student.class_id}", file=sys.stderr)
        
        # Get the student's class to get its name/level
        class_result = await session.execute(
            select(Class).where(Class.id == student.class_id)
        )
        student_class = class_result.scalar_one_or_none()
        print(f"CLASS LOOKUP: {student_class.name if student_class else 'CLASS NOT FOUND'}", file=sys.stderr)
        
        if student_class:
            # Query FeeStructure by class_level (the ClassLevel enum like "jhs_1", not display name)
            # FeeStructure.class_level stores the enum value, not the display name
            class_level_value = student_class.level.value if hasattr(student_class.level, 'value') else str(student_class.level)
            struct_query = select(FeeStructure).where(
                FeeStructure.class_level == class_level_value,
                FeeStructure.school_id == student.school_id
            )
            
            # Filter by term if provided
            if term_id:
                struct_query = struct_query.where(FeeStructure.academic_term_id == term_id)
                print(f"QUERY: class_level='{class_level_value}', school_id='{student.school_id}', term_id='{term_id}'", file=sys.stderr)
            else:
                print(f"QUERY: class_level='{class_level_value}', school_id='{student.school_id}', no term filter", file=sys.stderr)
            
            struct_result = await session.execute(struct_query)
            fee_structures = struct_result.scalars().all()
            print(f"FEESTRUCTURES WITH TERM: {len(fee_structures)} found", file=sys.stderr)
            
            # Debug: Check what FeeStructures actually exist in DB
            all_structures_query = select(FeeStructure).where(FeeStructure.school_id == student.school_id)
            all_structures_result = await session.execute(all_structures_query)
            all_structures = all_structures_result.scalars().all()
            print(f"DEBUG: Total FeeStructures in school: {len(all_structures)}", file=sys.stderr)
            for fs in all_structures[:5]:  # Show first 5
                print(f"  - class_level='{fs.class_level}', fee_type={fs.fee_type}, amount={fs.amount}", file=sys.stderr)
            
            # If no fees found for that term, try without term filter (they may apply across terms)
            if not fee_structures and term_id:
                print(f"NO TERM FEES. Trying without term filter...", file=sys.stderr)
                struct_query = select(FeeStructure).where(
                    FeeStructure.class_level == class_level_value,
                    FeeStructure.school_id == student.school_id
                )
                struct_result = await session.execute(struct_query)
                fee_structures = struct_result.scalars().all()
                print(f"FEESTRUCTURES WITHOUT TERM: {len(fee_structures)} found", file=sys.stderr)
            
            # Convert fee structures to fee records for the student
            # Create actual Fee records in the database (idempotent - won't duplicate)
            fees = []
            for structure in fee_structures:
                # Check if Fee already exists for this student + structure + term
                existing_fee_result = await session.execute(
                    select(Fee).where(
                        Fee.student_id == student_id,
                        Fee.fee_structure_id == structure.id,
                        Fee.academic_term_id == structure.academic_term_id,
                        Fee.school_id == student.school_id
                    )
                )
                existing_fee = existing_fee_result.scalar_one_or_none()
                
                if existing_fee:
                    # Use existing Fee record
                    fees.append(existing_fee)
                    print(f"FEE EXISTS: {structure.fee_type} - GHS {structure.amount} for term {structure.academic_term_id}", file=sys.stderr)
                else:
                    # Create new Fee record
                    new_fee = Fee(
                        student_id=student_id,
                        fee_structure_id=structure.id,
                        amount_due=structure.amount,
                        amount_paid=0,
                        discount=0,
                        status=PaymentStatus.PENDING,
                        academic_term_id=structure.academic_term_id,
                        school_id=student.school_id
                    )
                    session.add(new_fee)
                    fees.append(new_fee)
                    print(f"FEE CREATED IN DB: {structure.fee_type} - GHS {structure.amount}", file=sys.stderr)
            
            # Flush and commit to ensure fees are persisted to database
            await session.flush()
            await session.commit()
    
    print(f"TOTAL FEES READY: {len(fees)} fees", file=sys.stderr)
    
    # Get fee structures
    structure_ids = list(set(f.fee_structure_id for f in fees))
    structures = {}
    if structure_ids:
        struct_result = await session.execute(select(FeeStructure).where(FeeStructure.id.in_(structure_ids)))
        structures = {s.id: s for s in struct_result.scalars().all()}
    
    # Get payments for all fees
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
    total_discount = 0
    
    for fee in fees:
        structure = structures.get(fee.fee_structure_id)
        fee_payments = [p for p in payments if p.fee_id == fee.id]
        
        # Calculate actual amount paid from payments
        actual_paid = sum(p.amount for p in fee_payments) if fee_payments else fee.amount_paid
        balance = fee.amount_due - actual_paid - fee.discount
        
        # Generate fee name from fee_type (e.g., "tuition" -> "Tuition Fee")
        fee_type_name = structure.fee_type.value.replace('_', ' ').title() if structure else "Fee"
        
        fees_list.append({
            "id": fee.id,
            "fee_name": f"{fee_type_name} Fee",
            "fee_type": structure.fee_type if structure else "tuition",
            "description": structure.description if structure else None,
            "amount_due": fee.amount_due,
            "amount_paid": actual_paid,
            "balance": max(0, balance),
            "discount": fee.discount,
            "status": "paid" if balance <= 0 else "outstanding",
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
        total_paid += actual_paid
        total_discount += fee.discount
    
    print(f"RESPONSE: {len(fees_list)} fees. Total due: GHS {total_due}, Total paid: GHS {total_paid}, Total discount: GHS {total_discount}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    
    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "summary": {
            "total_due": total_due,
            "total_paid": total_paid,
            "total_discount": total_discount,
            "balance": max(0, total_due - total_paid - total_discount),
            "collection_rate": round((total_paid / total_due * 100) if total_due > 0 else 100, 1)
        },
        "fees": fees_list
    }


@router.get("/child/{student_id}/attendance", response_model=dict)
async def get_child_attendance(
    student_id: str,
    days: int = 30,
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's attendance history, optionally filtered by academic term"""
    student = await verify_child_access(student_id, current_user, session)
    
    # Build query for attendance
    query = select(Attendance).where(
        Attendance.student_id == student_id,
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


# ============================================================================
# ASSIGNMENTS ENDPOINTS
# ============================================================================

@router.get("/child/{student_id}/assignments", response_model=dict)
async def get_child_assignments(
    student_id: str,
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get all assignments for a parent's child, optionally filtered by academic term"""
    # Verify parent has access to this student
    student = await verify_child_access(student_id, current_user, session)
    
    if not student.class_id:
        return {"assignments": [], "message": "Child has no class assigned"}
    
    # Build query for assignments
    query = select(Assignment).where(
        Assignment.school_id == current_user.school_id,
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
        
        submission = submissions.get(assignment.id)
        
        # Determine submission status
        submission_status = "pending"
        if submission:
            if submission.submission_date:
                submission_status = "submitted"
                if submission.status == SubmissionStatus.GRADED:
                    submission_status = "graded"
            if assignment.due_date and datetime.utcnow() > assignment.due_date and not submission.submission_date:
                submission_status = "overdue"
        elif assignment.due_date and datetime.utcnow() > assignment.due_date:
            submission_status = "overdue"
        
        assignment_list.append({
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "subject_name": subject_info[assignment.subject_id],
            "teacher_name": teacher_info[assignment.teacher_id],
            "assignment_type": assignment.assignment_type,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "created_at": assignment.created_date.isoformat() if assignment.created_date else None,
            "submission_status": submission_status,
            "submitted_at": submission.submission_date.isoformat() if submission and submission.submission_date else None,
            "graded": submission.status == SubmissionStatus.GRADED if submission else False,
            "score": submission.score if submission else None,
            "max_score": submission.max_score if submission else assignment.points_possible,
            "percentage": ((submission.score / assignment.points_possible) * 100) if submission and submission.score else None,
            "feedback": submission.feedback if submission else None
        })
    
    return {
        "assignments": assignment_list,
        "message": f"Found {len(assignment_list)} assignments for {student.first_name}"
    }


@router.get("/child/{student_id}/assignment-metrics", response_model=dict)
async def get_assignment_performance_metrics(
    student_id: str,
    term_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get comprehensive assignment performance metrics for a child.
    
    Returns 5 metrics:
    1. Assignment Performance Index (API) - overall performance percentage
    2. Subject-wise Performance - breakdown by subject with trends
    3. Completion & Punctuality - submission rate and timeliness
    4. Assessment Type Breakdown - performance by assignment type
    5. Progress Trend - performance trajectory through the term
    
    Args:
        student_id: Child's student ID
        term_id: Optional academic term ID. If not provided, uses current term
    """
    # Verify parent has access to this student
    student = await verify_child_access(student_id, current_user, session)
    
    # Get current term if not specified
    if not term_id:
        from models.school import AcademicTerm
        from sqlalchemy import desc
        
        term_result = await session.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.school_id == current_user.school_id,
                AcademicTerm.is_current == True
            )
            .order_by(desc(AcademicTerm.start_date))
            .limit(1)
        )
        current_term = term_result.scalar_one_or_none()
        
        if not current_term:
            return {
                "error": "No active academic term found"
            }
        
        term_id = current_term.id
    
    # Use service to calculate metrics
    service = AssignmentPerformanceService(session)
    metrics = await service.get_all_metrics(
        student_id=student_id,
        academic_term_id=term_id,
        current_user=current_user,
        session=session
    )
    
    return metrics


# ============================================================================
# OPTIONAL MODULES - ENROLLMENT STATUS ENDPOINTS
# ============================================================================

@router.get("/child/{child_id}/enrollment-status", response_model=dict)
async def get_child_enrollment_status(
    child_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Check which optional modules child is enrolled in"""
    # Verify parent-child relationship
    student = await verify_child_access(child_id, current_user, session)
    
    # Check hostel enrollment
    hostel_result = await session.execute(
        select(StudentHostel).where(
            StudentHostel.student_id == child_id,
            StudentHostel.school_id == student.school_id,
            StudentHostel.status == "active"
        )
    )
    has_hostel = hostel_result.scalar_one_or_none() is not None
    
    # Check transport enrollment
    transport_result = await session.execute(
        select(StudentTransport).where(
            StudentTransport.student_id == child_id,
            StudentTransport.school_id == student.school_id,
            StudentTransport.is_active == True
        )
    )
    has_transport = transport_result.scalar_one_or_none() is not None
    
    return {
        "student_id": child_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "has_hostel": has_hostel,
        "has_transport": has_transport,
        "enabled_modules": {
            "hostel": has_hostel,
            "transport": has_transport,
            "fees": True,
            "grades": True,
            "attendance": True,
            "assignments": True
        }
    }


@router.get("/child/{child_id}/hostel/status", response_model=dict)
async def get_child_hostel_status(
    child_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's hostel info if enrolled"""
    # Verify parent-child relationship
    student = await verify_child_access(child_id, current_user, session)
    
    hostel_result = await session.execute(
        select(StudentHostel).where(
            StudentHostel.student_id == child_id,
            StudentHostel.school_id == student.school_id,
            StudentHostel.status == "active"
        )
    )
    hostel = hostel_result.scalar_one_or_none()
    
    if not hostel:
        raise HTTPException(status_code=404, detail="Child is not enrolled in hostel")
    
    # Get room details to get the actual room number
    room_result = await session.execute(
        select(Room).where(Room.id == hostel.room_id)
    )
    room = room_result.scalar_one_or_none()
    room_number = room.room_number if room else hostel.room_id
    
    # Get hostel details to get the hostel name
    hostel_detail_result = await session.execute(
        select(Hostel).where(Hostel.id == hostel.hostel_id)
    )
    hostel_detail = hostel_detail_result.scalar_one_or_none()
    hostel_name = hostel_detail.hostel_name if hostel_detail else hostel.hostel_id
    
    # Get recent fees for this hostel
    fees_result = await session.execute(
        select(HostelFee).where(
            HostelFee.student_id == child_id,
            HostelFee.school_id == student.school_id
        ).order_by(HostelFee.created_at.desc()).limit(10)
    )
    fees = fees_result.scalars().all()
    
    return {
        "student_id": child_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "enrolled": True,
        "hostel_name": hostel_name,
        "assigned_date": hostel.check_in_date,
        "room_number": room_number,
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


@router.get("/child/{child_id}/transport/status", response_model=dict)
async def get_child_transport_status(
    child_id: str,
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Get child's transport info if enrolled"""
    # Verify parent-child relationship
    student = await verify_child_access(child_id, current_user, session)
    
    transport_result = await session.execute(
        select(StudentTransport).where(
            StudentTransport.student_id == child_id,
            StudentTransport.school_id == student.school_id,
            StudentTransport.is_active == True
        )
    )
    transport = transport_result.scalar_one_or_none()
    
    if not transport:
        raise HTTPException(status_code=404, detail="Child is not enrolled in transport")
    
    # Get route details
    route_result = await session.execute(
        select(Route).where(Route.id == transport.route_id)
    )
    route = route_result.scalar_one_or_none()
    
    # Get fees for this route
    fees_result = await session.execute(
        select(TransportFee).where(
            TransportFee.student_id == child_id,
            TransportFee.school_id == student.school_id
        ).order_by(TransportFee.created_at.desc()).limit(10)
    )
    fees = fees_result.scalars().all()
    
    return {
        "student_id": child_id,
        "student_name": f"{student.first_name} {student.last_name}",
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
