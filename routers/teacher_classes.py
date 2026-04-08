"""Teacher Classes router for Teacher Portal"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from models.user import User, UserRole
from models.staff import TeacherAssignment, Staff
from models.classroom import Class, Subject, ClassSubject
from models.student import Student
from models.grade import Grade, AssessmentType
from database import get_session
from auth import require_roles

router = APIRouter(prefix="/teacher/classes", tags=["Teacher Portal - Classes"])


@router.get("", response_model=dict)
async def get_my_classes(
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all classes assigned to the teacher for current term.
    GES Aligned: Via TeacherAssignment model (defines class-subject-term assignments).
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    teacher_id = current_user.staff_id
    if not teacher_id:
        raise HTTPException(status_code=400, detail="No teacher context")
    
    try:
        # Get teacher assignments (links to classes)
        result = await session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.staff_id == teacher_id
            ).distinct()
        )
        assignments = result.scalars().all()
        
        classes_data = []
        for assignment in assignments:
            # Get class info
            class_result = await session.execute(
                select(Class).where(Class.id == assignment.class_id)
            )
            class_obj = class_result.scalar_one_or_none()
            
            # Get subject info
            subject_result = await session.execute(
                select(Subject).where(Subject.id == assignment.subject_id)
            )
            subject_obj = subject_result.scalar_one_or_none()
            
            if class_obj and subject_obj:
                classes_data.append({
                    "assignment_id": assignment.id,
                    "class_id": class_obj.id,
                    "class_name": class_obj.name,
                    "class_level": class_obj.level,
                    "subject_id": subject_obj.id,
                    "subject_name": subject_obj.name,
                    "is_class_teacher": assignment.is_class_teacher
                })
        
        return {
            "items": classes_data,
            "total": len(classes_data)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching classes: {str(e)}")


@router.get("/{class_id}/roster", response_model=dict)
async def get_class_roster(
    class_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get student roster for a class with recent grades.
    GES Aligned: Shows all students in class with latest assessment scores.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify teacher teaches this class
        result = await session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.staff_id == teacher_id,
                TeacherAssignment.class_id == class_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="You don't teach this class")
        
        # Get all students in class
        result = await session.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.class_id == class_id
            ).order_by(Student.last_name, Student.first_name)
        )
        students = result.scalars().all()
        
        roster = []
        for student in students:
            # Get latest grade for this student
            grade_result = await session.execute(
                select(Grade).where(
                    Grade.school_id == school_id,
                    Grade.student_id == student.id,
                    Grade.class_id == class_id
                ).order_by(Grade.created_at.desc())
            )
            latest_grade = grade_result.scalars().first()
            
            roster.append({
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}",
                "admission_number": student.student_id,
                "latest_grade": latest_grade.score if latest_grade else None,
                "latest_assessment": latest_grade.assessment_type if latest_grade else None
            })
        
        return {
            "class_id": class_id,
            "items": roster,
            "total": len(roster)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching roster: {str(e)}")


@router.get("/{class_id}/performance", response_model=dict)
async def get_class_performance(
    class_id: str,
    subject_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get class-level performance metrics and analytics.
    GES Aligned: Shows performance against GES grading scale.
    
    Returns:
    - Average score
    - Highest/lowest scores
    - Pass percentage (GES: >= 50)
    - Excellent percentage (GES: >= 80)
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify teacher teaches this class
        result = await session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.staff_id == teacher_id,
                TeacherAssignment.class_id == class_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="You don't teach this class")
        
        # Get all grades for this class
        query = select(Grade).where(
            Grade.school_id == school_id,
            Grade.class_id == class_id
        )
        
        if subject_id:
            query = query.where(Grade.subject_id == subject_id)
        
        result = await session.execute(query)
        grades = result.scalars().all()
        
        if not grades:
            return {
                "class_id": class_id,
                "subject_id": subject_id,
                "average_score": 0.0,
                "highest_score": 0.0,
                "lowest_score": 0.0,
                "total_grades": 0,
                "pass_percentage": 0.0,
                "excellent_percentage": 0.0
            }
        
        scores = [g.score for g in grades if g.score is not None]
        
        if not scores:
            return {
                "class_id": class_id,
                "subject_id": subject_id,
                "average_score": 0.0,
                "highest_score": 0.0,
                "lowest_score": 0.0,
                "total_grades": len(grades),
                "pass_percentage": 0.0,
                "excellent_percentage": 0.0
            }
        
        # Calculate metrics (GES aligned)
        average_score = sum(scores) / len(scores)
        highest_score = max(scores)
        lowest_score = min(scores)
        
        # GES thresholds
        pass_count = sum(1 for s in scores if s >= 50)  # GES: >= 50 is pass
        excellent_count = sum(1 for s in scores if s >= 80)  # GES: >= 80 is excellent
        
        pass_percentage = (pass_count / len(scores)) * 100 if scores else 0
        excellent_percentage = (excellent_count / len(scores)) * 100 if scores else 0
        
        return {
            "class_id": class_id,
            "subject_id": subject_id,
            "average_score": round(average_score, 2),
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "total_grades": len(grades),
            "pass_percentage": round(pass_percentage, 2),
            "excellent_percentage": round(excellent_percentage, 2),
            "ges_pass_threshold": 50,
            "ges_excellent_threshold": 80
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching performance: {str(e)}")


@router.get("/{class_id}/students-count", response_model=dict)
async def get_class_students_count(
    class_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get count of students in a class.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify teacher teaches this class
        result = await session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.staff_id == teacher_id,
                TeacherAssignment.class_id == class_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="You don't teach this class")
        
        # Count active students
        result = await session.execute(
            select(func.count(Student.id)).where(
                Student.school_id == school_id,
                Student.class_id == class_id
            )
        )
        total_students = result.scalar() or 0
        
        return {
            "class_id": class_id,
            "total_students": total_students
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error counting students: {str(e)}")
