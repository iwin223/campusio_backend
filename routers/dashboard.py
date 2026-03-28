"""Dashboard router - Analytics and Overview"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, date, timedelta
from models.student import Student, StudentStatus
from models.staff import Staff, StaffType, StaffStatus
from models.classroom import Class
from models.attendance import Attendance, AttendanceStatus
from models.fee import Fee, PaymentStatus
from models.school import School, AcademicTerm
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview", response_model=dict)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get dashboard overview statistics"""
    school_id = current_user.school_id
    
    if current_user.role == UserRole.SUPER_ADMIN:
        schools_result = await session.execute(select(func.count(School.id)))
        total_schools = schools_result.scalar()
        
        students_result = await session.execute(
            select(func.count(Student.id)).where(Student.status == StudentStatus.ACTIVE)
        )
        total_students = students_result.scalar()
        
        staff_result = await session.execute(
            select(func.count(Staff.id)).where(Staff.status == StaffStatus.ACTIVE)
        )
        total_staff = staff_result.scalar()
        
        return {
            "role": "super_admin",
            "stats": {
                "total_schools": total_schools,
                "total_students": total_students,
                "total_staff": total_staff
            }
        }
    
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    students_result = await session.execute(
        select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.status == StudentStatus.ACTIVE
        )
    )
    total_students = students_result.scalar()
    
    staff_result = await session.execute(
        select(func.count(Staff.id)).where(
            Staff.school_id == school_id,
            Staff.status == StaffStatus.ACTIVE
        )
    )
    total_staff = staff_result.scalar()
    
    teachers_result = await session.execute(
        select(func.count(Staff.id)).where(
            Staff.school_id == school_id,
            Staff.staff_type == StaffType.TEACHING,
            Staff.status == StaffStatus.ACTIVE
        )
    )
    total_teachers = teachers_result.scalar()
    
    classes_result = await session.execute(
        select(func.count(Class.id)).where(
            Class.school_id == school_id,
            Class.is_active == True
        )
    )
    total_classes = classes_result.scalar()
    
    today = date.today().isoformat()
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.school_id == school_id,
            Attendance.attendance_date == today
        )
    )
    today_attendance = attendance_result.scalars().all()
    
    present_count = sum(1 for a in today_attendance if a.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for a in today_attendance if a.status == AttendanceStatus.ABSENT)
    
    fees_result = await session.execute(
        select(Fee).where(Fee.school_id == school_id)
    )
    fees = fees_result.scalars().all()
    
    total_fees = sum(f.amount_due for f in fees)
    collected = sum(f.amount_paid for f in fees)
    outstanding = total_fees - collected
    
    return {
        "role": current_user.role,
        "stats": {
            "total_students": total_students,
            "total_staff": total_staff,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "attendance_today": {
                "present": present_count,
                "absent": absent_count,
                "attendance_rate": round(present_count / (present_count + absent_count) * 100, 1) if (present_count + absent_count) > 0 else 0
            },
            "fees": {
                "total": total_fees,
                "collected": collected,
                "outstanding": outstanding,
                "collection_rate": round(collected / total_fees * 100, 1) if total_fees > 0 else 0
            }
        }
    }


@router.get("/class-summary", response_model=list[dict])
async def get_class_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get summary for all classes"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    classes_result = await session.execute(
        select(Class).where(
            Class.school_id == school_id,
            Class.is_active == True
        ).order_by(Class.level, Class.name)
    )
    classes = classes_result.scalars().all()
    
    summaries = []
    for cls in classes:
        student_count_result = await session.execute(
            select(func.count(Student.id)).where(
                Student.class_id == cls.id,
                Student.status == StudentStatus.ACTIVE
            )
        )
        student_count = student_count_result.scalar()
        
        today = date.today().isoformat()
        attendance_result = await session.execute(
            select(Attendance).where(
                Attendance.class_id == cls.id,
                Attendance.attendance_date == today
            )
        )
        attendance = attendance_result.scalars().all()
        present = sum(1 for a in attendance if a.status == AttendanceStatus.PRESENT)
        
        summaries.append({
            "id": cls.id,
            "name": cls.name,
            "level": cls.level,
            "capacity": cls.capacity,
            "student_count": student_count,
            "attendance_today": present,
            "attendance_rate": round(present / student_count * 100, 1) if student_count > 0 else 0
        })
    
    return summaries


@router.get("/gender-distribution", response_model=dict)
async def get_gender_distribution(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get student gender distribution"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    from models.student import Gender
    
    male_result = await session.execute(
        select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.gender == Gender.MALE,
            Student.status == StudentStatus.ACTIVE
        )
    )
    male_count = male_result.scalar()
    
    female_result = await session.execute(
        select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.gender == Gender.FEMALE,
            Student.status == StudentStatus.ACTIVE
        )
    )
    female_count = female_result.scalar()
    
    total = male_count + female_count
    
    return {
        "male": male_count,
        "female": female_count,
        "total": total,
        "male_percentage": round(male_count / total * 100, 1) if total > 0 else 0,
        "female_percentage": round(female_count / total * 100, 1) if total > 0 else 0
    }
