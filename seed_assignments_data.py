"""Seed initial assignment and submission data for School ERP System

This script creates:
1. Sample assignments for each teacher's classes/subjects
2. Student submissions (some submitted, some pending, some graded)
3. Grades and feedback on submissions
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import async_session, init_db
from models.user import User, UserRole
from models.school import School, AcademicTerm, TermType
from models.student import Student
from models.staff import Staff, StaffType, TeacherAssignment
from models.classroom import Class as Classroom, Subject
from models.assignment import Assignment, Submission, AssignmentType, AssignmentStatus, SubmissionStatus
from auth import get_password_hash


# Sample assignments per subject
SAMPLE_ASSIGNMENTS = [
    {
        "title": "Chapter 1-2 Exercises",
        "description": "Complete all exercises from chapters 1 and 2",
        "assignment_type": AssignmentType.HOMEWORK,
        "points_possible": 50.0,
        "days_out": 0,
        "days_due": 7,
    },
    {
        "title": "Weekly Quiz",
        "description": "Quiz covering this week's lessons",
        "assignment_type": AssignmentType.QUIZ,
        "points_possible": 30.0,
        "days_out": 1,
        "days_due": 3,
    },
    {
        "title": "Research Project",
        "description": "Research and present on assigned topic",
        "assignment_type": AssignmentType.PROJECT,
        "points_possible": 100.0,
        "days_out": -7,  # Posted a week ago
        "days_due": 14,
    },
    {
        "title": "Worksheet - Calculations",
        "description": "Complete calculation worksheet",
        "assignment_type": AssignmentType.WORKSHEET,
        "points_possible": 25.0,
        "days_out": -2,
        "days_due": 5,
    },
    {
        "title": "Class Activity",
        "description": "In-class activity and exercises",
        "assignment_type": AssignmentType.CLASSWORK,
        "points_possible": 40.0,
        "days_out": -5,
        "days_due": 2,
    },
]


async def seed_assignments_data():
    """Create sample assignments and submissions"""
    
    async with async_session() as session:
        print("\n📚 SEEDING ASSIGNMENT DATA...")
        
        # Get admin user to retrieve school
        admin_result = await session.execute(
            select(User).where(User.email == "admin@school.edu.gh")
        )
        admin_user = admin_result.scalar_one_or_none()
        
        if not admin_user:
            print("❌ Admin user not found. Please run seed_school_data.py first.")
            return
        
        school_id = admin_user.school_id
        
        # Get academic term
        term_result = await session.execute(
            select(AcademicTerm).where(
                AcademicTerm.school_id == school_id,
                AcademicTerm.term == TermType.SECOND
            )
        )
        academic_term = term_result.scalar_one_or_none()
        
        if not academic_term:
            print("❌ Academic term not found.")
            return
        
        # Get all teachers
        teachers_result = await session.execute(
            select(Staff).where(
                Staff.school_id == school_id,
                Staff.staff_type == StaffType.TEACHING
            )
        )
        teachers = teachers_result.scalars().all()
        
        if not teachers:
            print("❌ No teachers found. Please run seed_teacher_data.py first.")
            return
        
        # Get all students
        students_result = await session.execute(
            select(Student).where(Student.school_id == school_id)
        )
        all_students = students_result.scalars().all()
        
        if not all_students:
            print("❌ No students found.")
            return
        
        # Get all classes
        classes_result = await session.execute(
            select(Classroom).where(Classroom.school_id == school_id)
        )
        classes = classes_result.scalars().all()
        
        if not classes:
            print("❌ No classes found.")
            return
        
        # Get all subjects
        subjects_result = await session.execute(
            select(Subject).where(Subject.school_id == school_id)
        )
        subjects_list = subjects_result.scalars().all()
        subjects_by_id = {s.id: s for s in subjects_list}
        
        assignment_count = 0
        submission_count = 0
        graded_count = 0
        
        # Create assignments for each teacher-class-subject combination
        for teacher in teachers:
            # Get teacher's assignments (class-subject combinations)
            teacher_assignments_result = await session.execute(
                select(TeacherAssignment).where(
                    TeacherAssignment.school_id == school_id,
                    TeacherAssignment.staff_id == teacher.id
                )
            )
            teacher_assignments = teacher_assignments_result.scalars().all()
            
            for ta in teacher_assignments:
                # Create 2-3 assignments per teacher-class-subject
                for sample_idx, sample in enumerate(SAMPLE_ASSIGNMENTS[:3]):
                    assignment = Assignment(
                        id=str(uuid.uuid4()),
                        school_id=school_id,
                        teacher_id=teacher.id,
                        class_id=ta.class_id,
                        subject_id=ta.subject_id,
                        academic_term_id=academic_term.id,
                        title=f"{sample['title']} - {ta.subject_id[:3]}",
                        description=sample["description"],
                        assignment_type=sample["assignment_type"],
                        status=AssignmentStatus.PUBLISHED,
                        instructions=f"Complete this {sample['assignment_type']} assignment",
                        points_possible=sample["points_possible"],
                        recorded_by=teacher.id,
                        created_date=datetime.utcnow() + timedelta(days=sample["days_out"]),
                        published_date=datetime.utcnow() + timedelta(days=sample["days_out"]),
                        due_date=datetime.utcnow() + timedelta(days=sample["days_due"]),
                    )
                    session.add(assignment)
                    await session.flush()  # Get the assignment ID
                    assignment_count += 1
                    
                    # Get students in this class
                    class_students = [s for s in all_students if s.class_id == ta.class_id]
                    
                    # Create submissions for students
                    for student_idx, student in enumerate(class_students):
                        # Vary submission status: some submitted, some pending, some graded
                        submission_type = student_idx % 4
                        
                        if submission_type == 0:
                            # Pending (not submitted)
                            submission = Submission(
                                id=str(uuid.uuid4()),
                                school_id=school_id,
                                assignment_id=assignment.id,
                                student_id=student.id,
                                class_id=ta.class_id,
                                subject_id=ta.subject_id,
                                status=SubmissionStatus.NOT_SUBMITTED,
                                submission_text=None,
                                submission_date=None,
                                max_score=sample["points_possible"],
                            )
                        elif submission_type == 1:
                            # Submitted but not graded
                            submission = Submission(
                                id=str(uuid.uuid4()),
                                school_id=school_id,
                                assignment_id=assignment.id,
                                student_id=student.id,
                                class_id=ta.class_id,
                                subject_id=ta.subject_id,
                                status=SubmissionStatus.SUBMITTED,
                                submission_text=f"Submission from {student.first_name} {student.last_name}",
                                submission_date=datetime.utcnow() - timedelta(days=1),
                                max_score=sample["points_possible"],
                            )
                        else:
                            # Graded
                            score = 80 + (student_idx % 20)  # Score between 80-100
                            submission = Submission(
                                id=str(uuid.uuid4()),
                                school_id=school_id,
                                assignment_id=assignment.id,
                                student_id=student.id,
                                class_id=ta.class_id,
                                subject_id=ta.subject_id,
                                status=SubmissionStatus.GRADED,
                                submission_text=f"Submission from {student.first_name} {student.last_name}",
                                submission_date=datetime.utcnow() - timedelta(days=2),
                                score=score,
                                max_score=sample["points_possible"],
                                feedback="Great work! Keep it up.",
                                graded_by=teacher.id,
                                graded_date=datetime.utcnow() - timedelta(days=1),
                            )
                            graded_count += 1
                        
                        session.add(submission)
                        submission_count += 1
        
        # Commit all changes
        await session.commit()
        
        print(f"✅ Created {assignment_count} assignments")
        print(f"✅ Created {submission_count} submissions")
        print(f"✅ Graded {graded_count} submissions")
        print("\n🎉 Assignment data seeded successfully!\n")


async def main():
    """Initialize database and seed assignments"""
    try:
        print("\n" + "="*60)
        print("SCHOOL ERP - ASSIGNMENT DATA SEEDER")
        print("="*60)
        
        await init_db()
        await seed_assignments_data()
        
        print("="*60)
        print("✅ SEEDING COMPLETE")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
