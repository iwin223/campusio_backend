"""Submissions router for Teacher Portal"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import uuid

from models.user import User, UserRole
from models.assignment import (
    Assignment, Submission, SubmissionCreate, SubmissionGrade,
    SubmissionStatus, AssignmentStatus
)
from models.student import Student
from models.grade import Grade, GradeCreate, AssessmentType
from database import get_session
from auth import require_roles

router = APIRouter(prefix="/teacher/assignments", tags=["Teacher Portal - Submissions"])


@router.get("/{assignment_id}/submissions", response_model=dict)
async def list_submissions(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all submissions for an assignment with pagination & filters.
    GES Aligned: Track submission status for attendance to standards.
    
    Query params:
    - status: Filter by status (not_submitted, submitted, graded, late, excused)
    - skip: Pagination offset
    - limit: Page size
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify assignment belongs to teacher
        result = await session.execute(
            select(Assignment).where(
                Assignment.id == assignment_id,
                Assignment.school_id == school_id,
                Assignment.teacher_id == teacher_id
            )
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Build query for submissions
        query = select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.school_id == school_id
        )
        
        if status_filter:
            query = query.where(Submission.status == status_filter)
        
        # Get total count
        count_query = select(func.count(Submission.id)).where(
            Submission.assignment_id == assignment_id,
            Submission.school_id == school_id
        )
        if status_filter:
            count_query = count_query.where(Submission.status == status_filter)
        
        result = await session.execute(count_query)
        total = result.scalar() or 0
        
        # Get paginated submissions
        result = await session.execute(
            query.order_by(Submission.submission_date.desc())
            .offset(skip)
            .limit(limit)
        )
        submissions = result.scalars().all()
        
        # Get student names
        submission_data = []
        for submission in submissions:
            student_result = await session.execute(
                select(Student).where(Student.id == submission.student_id)
            )
            student = student_result.scalar_one_or_none()
            
            submission_data.append({
                "id": submission.id,
                "student_id": submission.student_id,
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "status": submission.status,
                "submission_date": submission.submission_date,
                "score": submission.score,
                "feedback": submission.feedback,
                "graded_date": submission.graded_date
            })
        
        return {
            "items": submission_data,
            "total": total,
            "page": skip // limit + 1,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing submissions: {str(e)}")


@router.get("/{assignment_id}/submissions/stats", response_model=dict)
async def get_submission_stats(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get submission statistics for an assignment.
    GES Aligned: Quick overview of submission status.
    
    Returns:
    - submitted: Count of submitted (on-time)
    - not_submitted: Count of missing
    - graded: Count of graded
    - late: Count of late submissions
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify assignment belongs to teacher
        result = await session.execute(
            select(Assignment).where(
                Assignment.id == assignment_id,
                Assignment.school_id == school_id,
                Assignment.teacher_id == teacher_id
            )
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Count by status
        statuses = [
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.NOT_SUBMITTED,
            SubmissionStatus.GRADED,
            SubmissionStatus.LATE
        ]
        
        stats = {}
        for status in statuses:
            result = await session.execute(
                select(func.count(Submission.id)).where(
                    Submission.assignment_id == assignment_id,
                    Submission.school_id == school_id,
                    Submission.status == status
                )
            )
            stats[status.value] = result.scalar() or 0
        
        # Get total students in class
        result = await session.execute(
            select(func.count(Student.id)).where(
                Student.school_id == school_id,
                Student.class_id == assignment.class_id
            )
        )
        total_students = result.scalar() or 0
        
        return {
            "assignment_id": assignment_id,
            "total_students": total_students,
            "submitted_count": stats.get("submitted", 0),
            "not_submitted_count": stats.get("not_submitted", 0),
            "graded_count": stats.get("graded", 0),
            "late_count": stats.get("late", 0),
            "submission_percentage": (
                ((stats.get("submitted", 0) + stats.get("graded", 0) + stats.get("late", 0)) 
                 / total_students * 100) if total_students > 0 else 0
            ) if total_students > 0 else 0
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.post("/{assignment_id}/submissions/{submission_id}/grade", response_model=dict)
async def grade_submission(
    assignment_id: str,
    submission_id: str,
    grade_data: SubmissionGrade,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Grade a student submission and record score.
    GES Aligned: Records score with assessment type for GES compliance.
    
    This also creates a Grade record for the student's transcript.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify assignment belongs to teacher
        result = await session.execute(
            select(Assignment).where(
                Assignment.id == assignment_id,
                Assignment.school_id == school_id,
                Assignment.teacher_id == teacher_id
            )
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get submission
        result = await session.execute(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.assignment_id == assignment_id,
                Submission.school_id == school_id
            )
        )
        submission = result.scalar_one_or_none()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Validate score
        if grade_data.score < 0 or grade_data.score > assignment.points_possible:
            raise HTTPException(
                status_code=400,
                detail=f"Score must be between 0 and {assignment.points_possible}"
            )
        
        # Update submission
        submission.score = grade_data.score
        submission.max_score = assignment.points_possible
        submission.feedback = grade_data.feedback
        submission.graded_by = current_user.id
        submission.graded_date = datetime.utcnow()
        submission.status = SubmissionStatus.GRADED
        submission.updated_at = datetime.utcnow()
        
        if grade_data.rubric_scores:
            # Store rubric scores as JSON string
            import json
            submission.rubric_scores = json.dumps(grade_data.rubric_scores)
        
        session.add(submission)
        
        # Create Grade record (for transcript/report card)
        # Convert points to percentage (0-100)
        percentage_score = (grade_data.score / assignment.points_possible) * 100
        
        grade = Grade(
            id=str(uuid.uuid4()),
            school_id=school_id,
            student_id=submission.student_id,
            class_id=assignment.class_id,
            subject_id=assignment.subject_id,
            academic_term_id=assignment.academic_term_id,
            assessment_type=AssessmentType(assignment.assignment_type.value),
            score=percentage_score,
            max_score=100.0,
            weight=1.0,
            remarks=grade_data.feedback,
            recorded_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(grade)
        await session.commit()
        
        return {
            "id": submission.id,
            "status": submission.status,
            "score": submission.score,
            "feedback": submission.feedback,
            "graded_date": submission.graded_date,
            "message": "Submission graded successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error grading submission: {str(e)}")


@router.get("/{assignment_id}/submissions/summary/export", response_model=dict)
async def get_submission_summary(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get summary of all submissions for export (CSV/Excel).
    GES Aligned: Exportable format for record-keeping.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Verify assignment belongs to teacher
        result = await session.execute(
            select(Assignment).where(
                Assignment.id == assignment_id,
                Assignment.school_id == school_id,
                Assignment.teacher_id == teacher_id
            )
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get all submissions
        result = await session.execute(
            select(Submission).where(
                Submission.assignment_id == assignment_id,
                Submission.school_id == school_id
            ).order_by(Submission.student_id)
        )
        submissions = result.scalars().all()
        
        summary = []
        for submission in submissions:
            student_result = await session.execute(
                select(Student).where(Student.id == submission.student_id)
            )
            student = student_result.scalar_one_or_none()
            
            summary.append({
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "student_id": submission.student_id,
                "submission_status": submission.status,
                "submission_date": submission.submission_date.isoformat() if submission.submission_date else None,
                "score": submission.score,
                "max_score": submission.max_score,
                "feedback": submission.feedback,
                "graded_date": submission.graded_date.isoformat() if submission.graded_date else None
            })
        
        return {
            "assignment_id": assignment_id,
            "assignment_title": assignment.title,
            "items": summary,
            "total": len(summary),
            "export_format": "json"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")
