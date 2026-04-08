"""Assignments router for Teacher Portal"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
import uuid
import json

from models.user import User, UserRole
from models.assignment import (
    Assignment, AssignmentCreate, AssignmentUpdate, AssignmentResponse,
    AssignmentStatus, AssignmentType, AssignmentQuestion, Submission, SubmissionStatus
)
from models.classroom import Class, Subject
from models.student import Student
from database import get_session
from auth import require_roles

router = APIRouter(prefix="/teacher/assignments", tags=["Teacher Portal - Assignments"])


@router.post("", response_model=dict)
async def create_assignment(
    assignment_data: AssignmentCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new assignment (starts in DRAFT status).
    GES Aligned: Links to subject and term for proper curriculum tracking.
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    teacher_id = current_user.staff_id
    if not teacher_id:
        raise HTTPException(status_code=400, detail="No teacher context")
    
    try:
        # Verify class exists
        result = await session.execute(
            select(Class).where(
                Class.school_id == school_id,
                Class.id == assignment_data.class_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Class not found")
        
        # Verify subject exists
        result = await session.execute(
            select(Subject).where(
                Subject.school_id == school_id,
                Subject.id == assignment_data.subject_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Create assignment
        attachment_urls = None
        resource_links = None
        
        if assignment_data.attachment_urls:
            attachment_urls = ",".join(assignment_data.attachment_urls)
        if assignment_data.resource_links:
            resource_links = ",".join(assignment_data.resource_links)
        
        # Prepare rubric field (store grading settings as JSON)
        rubric_data = assignment_data.rubric
        if assignment_data.grading_settings:
            rubric_data = json.dumps(assignment_data.grading_settings)
        
        assignment = Assignment(
            id=str(uuid.uuid4()),
            school_id=school_id,
            teacher_id=teacher_id,
            class_id=assignment_data.class_id,
            subject_id=assignment_data.subject_id,
            academic_term_id=assignment_data.academic_term_id,
            title=assignment_data.title,
            description=assignment_data.description,
            assignment_type=assignment_data.assignment_type,
            status=AssignmentStatus.DRAFT,
            instructions=assignment_data.instructions,
            rubric=rubric_data,
            points_possible=assignment_data.points_possible,
            due_date=assignment_data.due_date,
            due_time=assignment_data.due_time,
            attachment_urls=attachment_urls,
            resource_links=resource_links,
            recorded_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_date=datetime.utcnow()
        )
        
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        
        # Save questions if provided
        if assignment_data.questions:
            for q_data in assignment_data.questions:
                question = AssignmentQuestion(
                    id=str(uuid.uuid4()),
                    school_id=school_id,
                    assignment_id=assignment.id,
                    question_text=q_data.get('question'),
                    question_type=q_data.get('type', 'essay'),
                    options=json.dumps(q_data.get('options', [])) if q_data.get('options') else None,
                    correct_answer=q_data.get('answer'),
                    points=1.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(question)
            await session.commit()
        
        return {
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "assignment_type": assignment.assignment_type,
            "status": assignment.status,
            "points_possible": assignment.points_possible,
            "due_date": assignment.due_date,
            "created_at": assignment.created_at,
            "questions_count": len(assignment_data.questions) if assignment_data.questions else 0
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating assignment: {str(e)}")


@router.get("", response_model=dict)
async def list_assignments(
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
    class_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all assignments for the teacher (with pagination & filters).
    GES Aligned: Filter by status (DRAFT, PUBLISHED, CLOSED) for proper workflow.
    
    Query params:
    - class_id: Filter by class
    - status: Filter by status (draft, published, closed, archived)
    - skip: Pagination offset
    - limit: Page size (max 100)
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    teacher_id = current_user.staff_id
    if not teacher_id:
        raise HTTPException(status_code=400, detail="No teacher context")
    
    try:
        # Build query
        query = select(Assignment).where(
            Assignment.school_id == school_id,
            Assignment.teacher_id == teacher_id
        )
        
        if class_id:
            query = query.where(Assignment.class_id == class_id)
        
        if status:
            query = query.where(Assignment.status == status)
        
        # Get total count
        count_query = select(func.count(Assignment.id)).where(
            Assignment.school_id == school_id,
            Assignment.teacher_id == teacher_id
        )
        if class_id:
            count_query = count_query.where(Assignment.class_id == class_id)
        if status:
            count_query = count_query.where(Assignment.status == status)
        
        result = await session.execute(count_query)
        total = result.scalar() or 0
        
        # Get paginated results
        result = await session.execute(
            query.order_by(Assignment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        assignments = result.scalars().all()
        
        return {
            "items": [
                {
                    "id": a.id,
                    "title": a.title,
                    "assignment_type": a.assignment_type,
                    "status": a.status,
                    "points_possible": a.points_possible,
                    "due_date": a.due_date,
                    "created_date": a.created_date
                }
                for a in assignments
            ],
            "total": total,
            "page": skip // limit + 1,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing assignments: {str(e)}")


@router.get("/{assignment_id}", response_model=dict)
async def get_assignment(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get assignment details with questions and grading settings.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
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
        
        # Fetch associated questions
        questions_result = await session.execute(
            select(AssignmentQuestion).where(
                AssignmentQuestion.assignment_id == assignment_id
            )
        )
        questions = questions_result.scalars().all()
        
        # Parse grading settings from rubric JSON
        grading_settings = {}
        if assignment.rubric:
            try:
                grading_settings = json.loads(assignment.rubric)
            except:
                grading_settings = {}
        
        return {
            "id": assignment.id,
            "class_id": assignment.class_id,
            "subject_id": assignment.subject_id,
            "title": assignment.title,
            "description": assignment.description,
            "assignment_type": assignment.assignment_type,
            "status": assignment.status,
            "instructions": assignment.instructions,
            "rubric": assignment.rubric,
            "points_possible": assignment.points_possible,
            "due_date": assignment.due_date,
            "due_time": assignment.due_time,
            "created_date": assignment.created_date,
            "published_date": assignment.published_date,
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
            "grading_settings": grading_settings,
            "questions": [
                {
                    "id": q.id,
                    "question": q.question_text,
                    "type": q.question_type,
                    "options": json.loads(q.options) if q.options else [],
                    "answer": q.correct_answer,
                    "points": q.points
                }
                for q in questions
            ],
            "questions_count": len(questions)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assignment: {str(e)}")


@router.get("/{assignment_id}/statistics", response_model=dict)
async def get_assignment_statistics(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get assignment submission statistics (total, submitted, graded, missing, late, average).
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
        # Fetch the assignment to verify it exists and get class_id
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
        
        # Get total students in the class
        students_result = await session.execute(
            select(func.count(Student.id)).where(
                Student.class_id == assignment.class_id,
                Student.school_id == school_id
            )
        )
        total_students = students_result.scalar() or 0
        
        # Get submission statistics
        submissions_result = await session.execute(
            select(Submission).where(
                Submission.assignment_id == assignment_id,
                Submission.school_id == school_id
            )
        )
        submissions = submissions_result.scalars().all()
        
        submitted_count = len([s for s in submissions if s.status in [SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED, SubmissionStatus.LATE]])
        graded_count = len([s for s in submissions if s.status == SubmissionStatus.GRADED])
        late_count = len([s for s in submissions if s.status == SubmissionStatus.LATE])
        missing_count = total_students - submitted_count
        
        # Calculate average score (only from graded submissions)
        graded_submissions = [s for s in submissions if s.status == SubmissionStatus.GRADED and s.score is not None]
        average_score = 0.0
        if graded_submissions:
            total_score = sum(s.score for s in graded_submissions)
            average_score = total_score / len(graded_submissions)
        
        return {
            "statistics": {
                "total_students": total_students,
                "submitted": submitted_count,
                "graded": graded_count,
                "missing": missing_count,
                "late": late_count,
                "average_score": round(average_score, 2)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assignment statistics: {str(e)}")


@router.put("/{assignment_id}", response_model=dict)
async def update_assignment(
    assignment_id: str,
    update_data: AssignmentUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Update assignment (only allowed in DRAFT status).
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
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
        
        # Only allow updates in DRAFT status
        if assignment.status != AssignmentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Can only edit assignments in DRAFT status. Current status: {assignment.status}"
            )
        
        # Update fields
        if update_data.title is not None:
            assignment.title = update_data.title
        if update_data.description is not None:
            assignment.description = update_data.description
        if update_data.instructions is not None:
            assignment.instructions = update_data.instructions
        if update_data.rubric is not None:
            assignment.rubric = update_data.rubric
        if update_data.points_possible is not None:
            assignment.points_possible = update_data.points_possible
        if update_data.due_date is not None:
            assignment.due_date = update_data.due_date
        if update_data.due_time is not None:
            assignment.due_time = update_data.due_time
        
        if update_data.attachment_urls is not None:
            assignment.attachment_urls = ",".join(update_data.attachment_urls)
        if update_data.resource_links is not None:
            assignment.resource_links = ",".join(update_data.resource_links)
        
        # Handle grading settings update
        if update_data.grading_settings is not None:
            assignment.rubric = json.dumps(update_data.grading_settings)
        
        # Handle questions update
        if update_data.questions is not None:
            # Delete existing questions
            await session.execute(
                select(AssignmentQuestion).where(
                    AssignmentQuestion.assignment_id == assignment_id
                )
            )
            delete_result = await session.execute(
                select(AssignmentQuestion).where(
                    AssignmentQuestion.assignment_id == assignment_id
                )
            )
            for q in delete_result.scalars().all():
                await session.delete(q)
            
            # Add new questions
            for q_data in update_data.questions:
                question = AssignmentQuestion(
                    id=str(uuid.uuid4()),
                    school_id=school_id,
                    assignment_id=assignment.id,
                    question_text=q_data.get('question'),
                    question_type=q_data.get('type', 'essay'),
                    options=json.dumps(q_data.get('options', [])) if q_data.get('options') else None,
                    correct_answer=q_data.get('answer'),
                    points=1.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(question)
        
        assignment.updated_by = current_user.id
        assignment.updated_at = datetime.utcnow()
        
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        
        return {
            "id": assignment.id,
            "title": assignment.title,
            "status": assignment.status,
            "updated_at": assignment.updated_at
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating assignment: {str(e)}")


@router.delete("/{assignment_id}", response_model=dict)
async def delete_assignment(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete assignment (only allowed in DRAFT status).
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
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
        
        # Only allow deletion in DRAFT status
        if assignment.status != AssignmentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Can only delete assignments in DRAFT status. Current status: {assignment.status}"
            )
        
        await session.delete(assignment)
        await session.commit()
        
        return {"message": "Assignment deleted successfully", "id": assignment_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting assignment: {str(e)}")


@router.post("/{assignment_id}/publish", response_model=dict)
async def publish_assignment(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Publish assignment (moves from DRAFT to PUBLISHED).
    GES Aligned: Publishing makes assignment available to students for submission.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
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
        
        if assignment.status != AssignmentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Can only publish DRAFT assignments. Current status: {assignment.status}"
            )
        
        assignment.status = AssignmentStatus.PUBLISHED
        assignment.published_date = datetime.utcnow()
        assignment.updated_at = datetime.utcnow()
        
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        
        return {
            "id": assignment.id,
            "status": assignment.status,
            "published_date": assignment.published_date,
            "message": "Assignment published successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error publishing assignment: {str(e)}")


@router.post("/{assignment_id}/close", response_model=dict)
async def close_assignment(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """
    Close assignment (moves from PUBLISHED to CLOSED).
    GES Aligned: Closing prevents further submissions and marks end of assessment.
    """
    school_id = current_user.school_id
    teacher_id = current_user.staff_id
    
    if not school_id or not teacher_id:
        raise HTTPException(status_code=400, detail="No school/teacher context")
    
    try:
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
        
        if assignment.status != AssignmentStatus.PUBLISHED:
            raise HTTPException(
                status_code=400,
                detail=f"Can only close PUBLISHED assignments. Current status: {assignment.status}"
            )
        
        assignment.status = AssignmentStatus.CLOSED
        assignment.updated_at = datetime.utcnow()
        
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        
        return {
            "id": assignment.id,
            "status": assignment.status,
            "message": "Assignment closed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing assignment: {str(e)}")
