"""Teacher Portal - Grades Management Router

Endpoints for teachers to:
- Record grades for their classes
- View grades they've recorded
- Export grade reports
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime

from models.grade import Grade, ReportCard, AssessmentType
from models.staff import TeacherAssignment
from models.student import Student
from models.classroom import Class, Subject, ClassSubject
from database import get_session
from auth import get_current_user, require_roles
from models.user import User, UserRole


router = APIRouter(prefix="/teacher/grades", tags=["teacher-grades"])


@router.post("", response_model=dict)
async def record_grade(
    grade_data: dict,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """
    Record a grade for a student in a class/subject.
    Teachers can only record grades for classes they teach.
    
    Body:
    {
        "student_id": int,
        "class_id": int,
        "subject_id": int,
        "assessment_type": "CLASS_WORK|HOMEWORK|QUIZ|MID_TERM|END_OF_TERM|PROJECT",
        "score": float,
        "max_score": float,
        "weight": float (optional, 0-1),
        "academic_term_id": int (optional)
    }
    """
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        # Verify teacher teaches this class
        assignment_result = await session.execute(
            select(TeacherAssignment).where(
                and_(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher_id,
                    TeacherAssignment.class_id == grade_data.get("class_id"),
                    TeacherAssignment.subject_id == grade_data.get("subject_id"),
                )
            )
        )
        assignment = assignment_result.scalar()
        
        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to teach this class/subject"
            )
        
        # Verify student exists and is in the class
        student_result = await session.execute(
            select(Student).where(
                and_(
                    Student.id == grade_data.get("student_id"),
                    Student.class_id == grade_data.get("class_id"),
                    Student.school_id == school_id,
                )
            )
        )
        student = student_result.scalar()
        
        if not student:
            raise HTTPException(status_code=404, detail="Student not found in this class")
        
        # Create grade record
        grade = Grade(
            school_id=school_id,
            student_id=grade_data.get("student_id"),
            class_id=grade_data.get("class_id"),
            subject_id=grade_data.get("subject_id"),
            assessment_type=grade_data.get("assessment_type"),
            score=grade_data.get("score"),
            max_score=grade_data.get("max_score", 100),
            weight=grade_data.get("weight", 1.0),
            recorded_by=teacher_id,
            academic_term_id=grade_data.get("academic_term_id"),
        )
        
        session.add(grade)
        await session.commit()
        await session.refresh(grade)
        
        return {
            "message": "Grade recorded successfully",
            "grade_id": grade.id,
            "student_id": grade.student_id,
            "score": grade.score,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error recording grade: {str(e)}")


@router.get("/my-classes", response_model=dict)
async def get_my_taught_classes(
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """Get list of classes the teacher is assigned to teach."""
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        # Get all assignments for this teacher
        result = await session.execute(
            select(TeacherAssignment).where(
                and_(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher_id,
                )
            )
        )
        assignments = result.scalars().all()
        
        classes_data = []
        for assignment in assignments:
            class_result = await session.execute(
                select(Class).where(Class.id == assignment.class_id)
            )
            class_obj = class_result.scalar()
            
            subject_result = await session.execute(
                select(Subject).where(Subject.id == assignment.subject_id)
            )
            subject = subject_result.scalar()
            
            if class_obj and subject:
                classes_data.append({
                    "class_id": class_obj.id,
                    "class_name": class_obj.name,
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "is_class_teacher": assignment.is_class_teacher,
                })
        
        return {
            "items": classes_data,
            "total": len(classes_data),
            "message": "Classes retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving classes: {str(e)}")


@router.get("/class/{class_id}", response_model=dict)
async def get_class_grades(
    class_id: int,
    subject_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all grades for a class (optionally filtered by subject).
    Only accessible to teacher teaching the class.
    """
    try:
        school_id = current_user.school_id
        teacher_id = current_user.id
        
        # Verify teacher teaches this class
        if subject_id:
            assignment_result = await session.execute(
                select(TeacherAssignment).where(
                    and_(
                        TeacherAssignment.school_id == school_id,
                        TeacherAssignment.staff_id == teacher_id,
                        TeacherAssignment.class_id == class_id,
                        TeacherAssignment.subject_id == subject_id,
                    )
                )
            )
        else:
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
            raise HTTPException(status_code=403, detail="Not authorized to view grades for this class")
        
        # Build query
        filters = [
            Grade.school_id == school_id,
            Grade.class_id == class_id,
        ]
        if subject_id:
            filters.append(Grade.subject_id == subject_id)
        
        # Count total
        count_result = await session.execute(
            select(func.count(Grade.id)).where(and_(*filters))
        )
        total = count_result.scalar()
        
        # Get paginated results
        result = await session.execute(
            select(Grade)
            .where(and_(*filters))
            .order_by(Grade.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        grades = result.scalars().all()
        
        grades_list = []
        for grade in grades:
            student_result = await session.execute(
                select(Student).where(Student.id == grade.student_id)
            )
            student = student_result.scalar()
            
            grades_list.append({
                "grade_id": grade.id,
                "student_id": grade.student_id,
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "assessment_type": grade.assessment_type,
                "score": grade.score,
                "max_score": grade.max_score,
                "weight": grade.weight,
                "recorded_at": grade.created_at.isoformat() if grade.created_at else None,
            })
        
        pages = (total + limit - 1) // limit
        return {
            "items": grades_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
            "message": "Grades retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving grades: {str(e)}")


@router.get("/student/{student_id}", response_model=dict)
async def get_student_grades(
    student_id: int,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """Get all grades recorded for a specific student by this teacher."""
    try:
        school_id = current_user.school_id
        
        # Verify student exists in this school
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
        
        # Get grades recorded by this teacher for this student
        result = await session.execute(
            select(Grade).where(
                and_(
                    Grade.student_id == student_id,
                    Grade.recorded_by == current_user.id,
                    Grade.school_id == school_id,
                )
            ).order_by(Grade.created_at.desc())
        )
        grades = result.scalars().all()
        
        grades_list = [
            {
                "grade_id": g.id,
                "subject_id": g.subject_id,
                "assessment_type": g.assessment_type,
                "score": g.score,
                "max_score": g.max_score,
                "weight": g.weight,
                "recorded_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in grades
        ]
        
        return {
            "student_id": student_id,
            "student_name": f"{student.first_name} {student.last_name}",
            "grades": grades_list,
            "message": "Student grades retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving student grades: {str(e)}")


@router.patch("/{grade_id}", response_model=dict)
async def update_grade(
    grade_id: int,
    grade_data: dict,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
):
    """Update a grade record (only by the teacher who recorded it)."""
    try:
        school_id = current_user.school_id
        
        # Get the grade
        result = await session.execute(
            select(Grade).where(
                and_(
                    Grade.id == grade_id,
                    Grade.school_id == school_id,
                    Grade.recorded_by == current_user.id,
                )
            )
        )
        grade = result.scalar()
        
        if not grade:
            raise HTTPException(
                status_code=404,
                detail="Grade not found or you don't have permission to edit it"
            )
        
        # Update fields
        if "score" in grade_data:
            grade.score = grade_data["score"]
        if "max_score" in grade_data:
            grade.max_score = grade_data["max_score"]
        if "weight" in grade_data:
            grade.weight = grade_data["weight"]
        if "assessment_type" in grade_data:
            grade.assessment_type = grade_data["assessment_type"]
        
        grade.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(grade)
        
        return {
            "message": "Grade updated successfully",
            "grade_id": grade.id,
            "score": grade.score,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating grade: {str(e)}")
