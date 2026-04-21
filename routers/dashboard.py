"""Dashboard router - Analytics and Overview"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case
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
        # 🚀 OPTIMIZATION: Combined single query instead of multiple count queries
        super_admin_stats = await session.execute(
            select(
                func.count(func.distinct(School.id)).label("total_schools"),
                func.count(func.distinct(Student.id)).label("total_students"),
                func.count(func.distinct(Staff.id)).label("total_staff")
            )
            .select_from(School)
            .outerjoin(Student, Student.school_id == School.id)
            .outerjoin(Staff, Staff.school_id == School.id)
            .where(
                (Student.status == StudentStatus.ACTIVE) | (Student.id == None),
                (Staff.status == StaffStatus.ACTIVE) | (Staff.id == None)
            )
        )
        row = super_admin_stats.first()
        
        return {
            "role": "super_admin",
            "stats": {
                "total_schools": row.total_schools or 0,
                "total_students": row.total_students or 0,
                "total_staff": row.total_staff or 0
            }
        }
    
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # 🚀 OPTIMIZATION: Combined statistics query - avoid multiple database round trips
    today = date.today().isoformat()
    
    stats_result = await session.execute(
        select(
            func.count(func.distinct(Student.id)).label("total_students"),
            func.count(func.distinct(Staff.id)).label("total_staff"),
            func.count(func.distinct(
                case(
                    (Staff.staff_type == StaffType.TEACHING, Staff.id),
                    else_=None
                )
            )).label("total_teachers"),
            func.count(func.distinct(Class.id)).label("total_classes"),
            func.count(func.distinct(
                case(
                    (Attendance.status == AttendanceStatus.PRESENT, Attendance.id),
                    else_=None
                )
            )).label("present_count"),
            func.count(func.distinct(
                case(
                    (Attendance.status == AttendanceStatus.ABSENT, Attendance.id),
                    else_=None
                )
            )).label("absent_count"),
            func.sum(Fee.amount_due).label("total_fees"),
            func.sum(Fee.amount_paid).label("total_fees_collected")
        )
        .select_from(Student)
        .outerjoin(Staff, and_(Staff.school_id == school_id, Staff.status == StaffStatus.ACTIVE))
        .outerjoin(Class, and_(Class.school_id == school_id, Class.is_active == True))
        .outerjoin(Attendance, and_(
            Attendance.school_id == school_id,
            Attendance.attendance_date == today
        ))
        .outerjoin(Fee, Fee.school_id == school_id)
        .where(
            Student.school_id == school_id,
            Student.status == StudentStatus.ACTIVE
        )
    )
    
    row = stats_result.first()
    
    total_fees = row.total_fees or 0
    collected = row.total_fees_collected or 0
    outstanding = total_fees - collected
    present = row.present_count or 0
    absent = row.absent_count or 0
    
    return {
        "role": current_user.role,
        "stats": {
            "total_students": row.total_students or 0,
            "total_staff": row.total_staff or 0,
            "total_teachers": row.total_teachers or 0,
            "total_classes": row.total_classes or 0,
            "attendance_today": {
                "present": present,
                "absent": absent,
                "attendance_rate": round(present / (present + absent) * 100, 1) if (present + absent) > 0 else 0
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
