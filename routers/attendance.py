"""Attendance router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from models.attendance import Attendance, AttendanceCreate, AttendanceStatus, AttendanceBulkCreate
from models.student import Student
from models.classroom import Class
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("", response_model=dict)
async def record_attendance(
    attendance_data: AttendanceCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Record attendance for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    existing = await session.execute(
        select(Attendance).where(
            Attendance.school_id == school_id,
            Attendance.student_id == attendance_data.student_id,
            Attendance.attendance_date == attendance_data.attendance_date
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Attendance already recorded for this date")
    
    attendance = Attendance(
        school_id=school_id,
        recorded_by=current_user.id,
        **attendance_data.model_dump()
    )
    session.add(attendance)
    await session.commit()
    await session.refresh(attendance)
    
    return {
        "id": attendance.id,
        "student_id": attendance.student_id,
        "date": attendance.attendance_date,
        "status": attendance.status,
        "message": "Attendance recorded"
    }


@router.post("/bulk", response_model=dict)
async def record_bulk_attendance(
    bulk_data: AttendanceBulkCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Record attendance for multiple students"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    recorded = 0
    skipped = 0
    
    for record in bulk_data.records:
        existing = await session.execute(
            select(Attendance).where(
                Attendance.school_id == school_id,
                Attendance.student_id == record.get("student_id"),
                Attendance.attendance_date == bulk_data.attendance_date
            )
        )
        
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        
        attendance = Attendance(
            school_id=school_id,
            class_id=bulk_data.class_id,
            student_id=record.get("student_id"),
            attendance_date=bulk_data.attendance_date,
            status=record.get("status", AttendanceStatus.PRESENT),
            remarks=record.get("remarks"),
            recorded_by=current_user.id
        )
        session.add(attendance)
        recorded += 1
    
    await session.commit()
    
    return {
        "message": f"Attendance recorded for {recorded} students",
        "recorded": recorded,
        "skipped": skipped
    }


@router.get("/class/{class_id}", response_model=dict)
async def get_class_attendance(
    class_id: str,
    attendance_date: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get attendance for a class on a specific date"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    students_result = await session.execute(
        select(Student).where(Student.class_id == class_id).order_by(Student.first_name)
    )
    students = students_result.scalars().all()
    
    attendance_result = await session.execute(
        select(Attendance).where(
            Attendance.class_id == class_id,
            Attendance.attendance_date == attendance_date
        )
    )
    attendance_records = {a.student_id: a for a in attendance_result.scalars().all()}
    
    records = []
    present = 0
    absent = 0
    late = 0
    excused = 0
    
    for student in students:
        att = attendance_records.get(student.id)
        status = att.status if att else None
        
        if status == AttendanceStatus.PRESENT:
            present += 1
        elif status == AttendanceStatus.ABSENT:
            absent += 1
        elif status == AttendanceStatus.LATE:
            late += 1
        elif status == AttendanceStatus.EXCUSED:
            excused += 1
        
        records.append({
            "student_id": student.id,
            "student_name": f"{student.first_name} {student.last_name}",
            "photo_url": student.photo_url,
            "status": status,
            "remarks": att.remarks if att else None,
            "recorded": att is not None
        })
    
    return {
        "class_id": class_id,
        "class_name": cls.name,
        "date": attendance_date,
        "total_students": len(students),
        "summary": {
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "not_recorded": len(students) - (present + absent + late + excused)
        },
        "records": records
    }


@router.get("/student/{student_id}", response_model=dict)
async def get_student_attendance(
    student_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get attendance history for a student"""
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = select(Attendance).where(Attendance.student_id == student_id)
    
    if start_date:
        query = query.where(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.where(Attendance.attendance_date <= end_date)
    
    query = query.order_by(Attendance.attendance_date.desc())
    
    result = await session.execute(query)
    records = result.scalars().all()
    
    total = len(records)
    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
    
    return {
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "summary": {
            "total_days": total,
            "present": present,
            "absent": absent,
            "late": late_count,
            "excused": excused_count,
            "attendance_percentage": round((present + late_count) / total * 100, 1) if total > 0 else 0
        },
        "records": [
            {
                "id": r.id,
                "date": r.attendance_date,
                "status": r.status,
                "remarks": r.remarks
            }
            for r in records
        ]
    }


@router.put("/{attendance_id}", response_model=dict)
async def update_attendance(
    attendance_id: str,
    status: AttendanceStatus,
    remarks: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Update an attendance record"""
    result = await session.execute(select(Attendance).where(Attendance.id == attendance_id))
    attendance = result.scalar_one_or_none()
    
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    if current_user.role not in [UserRole.SUPER_ADMIN] and current_user.school_id != attendance.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    attendance.status = status
    attendance.remarks = remarks
    attendance.updated_at = datetime.utcnow()
    session.add(attendance)
    await session.commit()
    
    return {"message": "Attendance updated"}
