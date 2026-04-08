"""Teacher Portal - Attendance Management Router

Endpoints for teachers to:
- Mark attendance for their classes
- View attendance records
- Generate attendance reports
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Optional, List
from datetime import datetime, date

from models.attendance import Attendance, AttendanceStatus
from models.staff import TeacherAssignment, Staff
from models.student import Student
from models.classroom import Class
from database import get_session
from auth import get_current_user, require_roles
from models.user import User, UserRole


router = APIRouter(prefix="/teacher/attendance", tags=["teacher-attendance"])


@router.post("/mark", response_model=dict)
async def mark_attendance(
    attendance_data: dict,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """
    Mark attendance for a student in a class.
    Teachers can only mark attendance for classes they teach.
    
    Body:
    {
        "student_id": int,
        "class_id": int,
        "attendance_date": "YYYY-MM-DD",
        "status": "PRESENT|ABSENT|LATE|EXCUSED",
        "remarks": str (optional)
    }
    """
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        # Verify teacher is assigned to this class
        assignment_result = await session.execute(
            select(TeacherAssignment).where(
                and_(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher_id,
                    TeacherAssignment.class_id == attendance_data.get("class_id"),
                    TeacherAssignment.is_class_teacher == True,  # Only class teachers can mark attendance
                )
            )
        )
        assignment = assignment_result.scalar()
        
        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You are not a class teacher for this class"
            )
        
        # Verify student is in the class
        student_result = await session.execute(
            select(Student).where(
                and_(
                    Student.id == attendance_data.get("student_id"),
                    Student.class_id == attendance_data.get("class_id"),
                    Student.school_id == school_id,
                )
            )
        )
        student = student_result.scalar()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found in this class")
        
        # Check if attendance already marked for this date
        check_result = await session.execute(
            select(Attendance).where(
                and_(
                    Attendance.student_id == attendance_data.get("student_id"),
                    Attendance.attendance_date == attendance_data.get("attendance_date"),
                    Attendance.school_id == school_id,
                )
            )
        )
        existing = check_result.scalar()
        
        if existing:
            # Update existing
            existing.status = attendance_data.get("status")
            existing.marked_by = teacher_id
            existing.remarks = attendance_data.get("remarks", "")
            existing.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
            return {
                "message": "Attendance updated successfully",
                "attendance_id": existing.id,
            }
        
        # Create new attendance record
        attendance = Attendance(
            school_id=school_id,
            student_id=attendance_data.get("student_id"),
            class_id=attendance_data.get("class_id"),
            attendance_date=attendance_data.get("attendance_date"),
            status=attendance_data.get("status"),
            marked_by=teacher_id,
            remarks=attendance_data.get("remarks", ""),
        )
        
        session.add(attendance)
        await session.commit()
        await session.refresh(attendance)
        
        return {
            "message": "Attendance marked successfully",
            "attendance_id": attendance.id,
            "student_id": attendance.student_id,
            "status": attendance.status,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error marking attendance: {str(e)}")


@router.post("/mark-bulk", response_model=dict)
async def mark_attendance_bulk(
    attendance_list: List[dict],
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """
    Mark attendance for multiple students at once.
    
    Body: [
        {
            "student_id": int,
            "class_id": int,
            "attendance_date": "YYYY-MM-DD",
            "status": "PRESENT|ABSENT|LATE|EXCUSED"
        },
        ...
    ]
    """
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        if not attendance_list:
            raise HTTPException(status_code=400, detail="No attendance records provided")
        
        # Verify teacher is class teacher for the class (all records should be same class)
        class_id = attendance_list[0].get("class_id")
        assignment_result = await session.execute(
            select(TeacherAssignment).where(
                and_(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher_id,
                    TeacherAssignment.class_id == class_id,
                    TeacherAssignment.is_class_teacher == True,
                )
            )
        )
        assignment = assignment_result.scalar()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="Not authorized to mark attendance for this class")
        
        created_count = 0
        updated_count = 0
        
        for record in attendance_list:
            try:
                # Check existing
                check_result = await session.execute(
                    select(Attendance).where(
                        and_(
                            Attendance.student_id == record.get("student_id"),
                            Attendance.attendance_date == record.get("attendance_date"),
                            Attendance.school_id == school_id,
                        )
                    )
                )
                existing = check_result.scalar()
                
                if existing:
                    existing.status = record.get("status")
                    existing.marked_by = teacher_id
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    attendance = Attendance(
                        school_id=school_id,
                        student_id=record.get("student_id"),
                        class_id=class_id,
                        attendance_date=record.get("attendance_date"),
                        status=record.get("status"),
                        marked_by=teacher_id,
                    )
                    session.add(attendance)
                    created_count += 1
                    
            except Exception as e:
                continue
        
        await session.commit()
        
        return {
            "message": f"Bulk attendance marking completed",
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error marking bulk attendance: {str(e)}")


@router.get("/class/{class_id}", response_model=dict)
async def get_class_attendance(
    class_id: int,
    attendance_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """
    Get attendance records for a class on a specific date or date range.
    Only accessible to teacher assigned to the class.
    """
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        # Verify teacher is assigned to this class
        assignment_result = await session.execute(
            select(TeacherAssignment).where(
                and_(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher_id,
                    TeacherAssignment.class_id == class_id,
                )
            )
        )
        assignment = assignment_result.scalar()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="Not authorized to view attendance for this class")
        
        # Build filters
        filters = [
            Attendance.school_id == school_id,
            Attendance.class_id == class_id,
        ]
        
        if attendance_date:
            filters.append(Attendance.attendance_date == attendance_date)
        
        # Count total
        count_result = await session.execute(
            select(func.count(Attendance.id)).where(and_(*filters))
        )
        total = count_result.scalar()
        
        # Get paginated results
        result = await session.execute(
            select(Attendance)
            .where(and_(*filters))
            .order_by(Attendance.attendance_date.desc(), Attendance.student_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        records = result.scalars().all()
        
        attendance_list = []
        for record in records:
            student_result = await session.execute(
                select(Student).where(Student.id == record.student_id)
            )
            student = student_result.scalar()
            
            teacher_result = await session.execute(
                select(Staff).where(Staff.id == record.marked_by)
            )
            teacher = teacher_result.scalar()
            
            attendance_list.append({
                "attendance_id": record.id,
                "student_id": record.student_id,
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "attendance_date": record.attendance_date.isoformat() if record.attendance_date else None,
                "status": record.status,
                "marked_by": teacher.first_name if teacher else "System",
                "remarks": record.remarks or "",
            })
        
        pages = (total + limit - 1) // limit
        return {
            "items": attendance_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
            "message": "Attendance records retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving attendance: {str(e)}")


@router.get("/student/{student_id}/report", response_model=dict)
async def get_student_attendance_report(
    student_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """Get attendance report for a student across all classes or date range."""
    try:
        school_id = current_user.school_id
        
        # Verify student exists
        student_result = await session.execute(
            select(Student).where(
                and_(
                    Student.id == student_id,
                    Student.school_id == school_id,
                )
            )
        )
        student = student_result.scalar()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Build query filters
        filters = [
            Attendance.student_id == student_id,
            Attendance.school_id == school_id,
        ]
        
        if start_date:
            filters.append(Attendance.attendance_date >= start_date)
        if end_date:
            filters.append(Attendance.attendance_date <= end_date)
        
        # Get attendance records
        result = await session.execute(
            select(Attendance)
            .where(and_(*filters))
            .order_by(Attendance.attendance_date.desc())
        )
        records = result.scalars().all()
        
        # Calculate statistics
        total_records = len(records)
        present_count = sum(1 for r in records if r.status == "PRESENT")
        absent_count = sum(1 for r in records if r.status == "ABSENT")
        late_count = sum(1 for r in records if r.status == "LATE")
        excused_count = sum(1 for r in records if r.status == "EXCUSED")
        
        attendance_pct = (present_count / total_records * 100) if total_records > 0 else 0
        
        return {
            "student_id": student_id,
            "student_name": f"{student.first_name} {student.last_name}",
            "attendance_summary": {
                "total_records": total_records,
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "excused": excused_count,
                "attendance_percentage": round(attendance_pct, 2),
            },
            "message": "Attendance report retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating attendance report: {str(e)}")
