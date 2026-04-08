"""Seed initial teacher data for School ERP System

This script creates:
1. Teacher user accounts
2. Staff records (teacher type)
3. Subjects (core and elective)
4. Teacher assignments (teachers to classes and subjects per term)
5. Class teacher assignments
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_session, init_db
from models.user import User, UserRole
from models.school import School, AcademicTerm, TermType
from models.staff import Staff, StaffStatus, StaffType, TeacherAssignment
from models.classroom import Class as Classroom, Subject, SubjectCategory
from auth import get_password_hash


# Default subjects for Ghana schools
DEFAULT_SUBJECTS = [
    # Core Subjects
    {"name": "English Language", "code": "ENG101", "category": SubjectCategory.CORE, "credit_hours": 4},
    {"name": "Mathematics", "code": "MAT101", "category": SubjectCategory.CORE, "credit_hours": 4},
    {"name": "Integrated Science", "code": "SCI101", "category": SubjectCategory.CORE, "credit_hours": 3},
    {"name": "Social Studies", "code": "SOC101", "category": SubjectCategory.CORE, "credit_hours": 3},
    
    # Core JHS Subjects (additional for secondary)
    {"name": "English (Literature)", "code": "ENG201", "category": SubjectCategory.CORE, "credit_hours": 3},
    {"name": "Chemistry", "code": "CHM101", "category": SubjectCategory.CORE, "credit_hours": 3},
    {"name": "Physics", "code": "PHY101", "category": SubjectCategory.CORE, "credit_hours": 3},
    {"name": "Biology", "code": "BIO101", "category": SubjectCategory.CORE, "credit_hours": 3},
    {"name": "History", "code": "HIS101", "category": SubjectCategory.CORE, "credit_hours": 2},
    {"name": "Geography", "code": "GEO101", "category": SubjectCategory.CORE, "credit_hours": 2},
    
    # Elective Subjects
    {"name": "French Language", "code": "FRE101", "category": SubjectCategory.ELECTIVE, "credit_hours": 3},
    {"name": "Computer Science", "code": "COM101", "category": SubjectCategory.ELECTIVE, "credit_hours": 3},
    {"name": "Physical Education", "code": "PHE101", "category": SubjectCategory.ELECTIVE, "credit_hours": 2},
    {"name": "Visual Arts", "code": "ART101", "category": SubjectCategory.ELECTIVE, "credit_hours": 2},
    {"name": "Music", "code": "MUS101", "category": SubjectCategory.ELECTIVE, "credit_hours": 2},
    {"name": "Business Studies", "code": "BUS101", "category": SubjectCategory.ELECTIVE, "credit_hours": 2},
]

# Sample teacher data
SAMPLE_TEACHERS = [
    {
        "first_name": "Kwame",
        "last_name": "Asante",
        "email": "kwame.asante@school.edu.gh",
        "phone": "+233 20 222 2222",
        "position": "Senior Teacher - Mathematics",
        "department": "Academic",
        "qualification": "B.Sc. Mathematics Education (Legon)",
        "subjects": ["Mathematics"],
        "classes": [],  # Class teacher for P1A
        "is_class_teacher": True,
    },
    {
        "first_name": "Ama",
        "last_name": "Osei",
        "email": "ama.osei@school.edu.gh",
        "phone": "+233 20 333 3333",
        "position": "Teacher - English Language",
        "department": "Academic",
        "qualification": "B.A. English Studies (UCC)",
        "subjects": ["English Language", "English (Literature)"],
        "classes": [],
    },
    {
        "first_name": "Kofi",
        "last_name": "Mensah",
        "email": "kofi.mensah@school.edu.gh",
        "phone": "+233 20 444 4444",
        "position": "Teacher - Integrated Science",
        "department": "Academic",
        "qualification": "B.Sc. Science Education (Kumasi)",
        "subjects": ["Integrated Science", "Chemistry", "Physics"],
        "classes": [],
        "is_class_teacher": True,
    },
    {
        "first_name": "Abena",
        "last_name": "Boateng",
        "email": "abena.boateng@school.edu.gh",
        "phone": "+233 20 555 5555",
        "position": "Teacher - Social Studies",
        "department": "Academic",
        "qualification": "B.A. History & Geography (Cape Coast)",
        "subjects": ["Social Studies", "History", "Geography"],
        "classes": [],
    },
    {
        "first_name": "David",
        "last_name": "Nyarko",
        "email": "david.nyarko@school.edu.gh",
        "phone": "+233 20 666 6666",
        "position": "ICT Specialist - Computer Science",
        "department": "Academic",
        "qualification": "B.Sc. Computer Science (KNUST)",
        "subjects": ["Computer Science"],
        "classes": [],
    },
    {
        "first_name": "Ekua",
        "last_name": "Gyimah",
        "email": "ekua.gyimah@school.edu.gh",
        "phone": "+233 20 777 7777",
        "position": "Physical Education Coordinator",
        "department": "Academic",
        "qualification": "Diploma in Physical Education (UCEW)",
        "subjects": ["Physical Education"],
        "classes": [],
        "is_class_teacher": True,
    },
    {
        "first_name": "Samuel",
        "last_name": "Okonkwo",
        "email": "samuel.okonkwo@school.edu.gh",
        "phone": "+233 20 888 8888",
        "position": "Teacher - French Language",
        "department": "Academic",
        "qualification": "B.A. French Studies (Accra)",
        "subjects": ["French Language"],
        "classes": [],
    },
    {
        "first_name": "Grace",
        "last_name": "Owusu",
        "email": "grace.owusu@school.edu.gh",
        "phone": "+233 20 999 9999",
        "position": "Teacher - Arts & Crafts",
        "department": "Academic",
        "qualification": "Diploma in Visual Arts (National)",
        "subjects": ["Visual Arts", "Music"],
        "classes": [],
    },
]


async def create_subjects(session, school_id):
    """Create subjects for the school"""
    print("\n=== CREATING SUBJECTS ===")
    
    # Check if subjects already exist
    result = await session.execute(
        select(Subject).where(Subject.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Subjects already exist. Skipping...")
        # Still fetch them for mapping
        result = await session.execute(
            select(Subject).where(Subject.school_id == school_id)
        )
        subjects = result.scalars().all()
        return {s.name: s for s in subjects}
    
    subjects_map = {}
    for subject_data in DEFAULT_SUBJECTS:
        subject = Subject(
            school_id=school_id,
            **subject_data
        )
        session.add(subject)
        subjects_map[subject_data["name"]] = subject
    
    await session.flush()
    print(f"✓ Created {len(subjects_map)} subjects")
    
    return subjects_map


async def create_teacher_users(session, school_id):
    """Create teacher user accounts"""
    print("\n=== CREATING TEACHER USER ACCOUNTS ===")
    
    teachers_created = []
    for teacher_data in SAMPLE_TEACHERS:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == teacher_data["email"])
        )
        if result.scalar_one_or_none():
            print(f"  ⊘ User {teacher_data['email']} already exists, skipping...")
            continue
        
        # Create user
        user = User(
            email=teacher_data["email"],
            password_hash=get_password_hash("teacher123"),  # Default password
            first_name=teacher_data["first_name"],
            last_name=teacher_data["last_name"],
            phone=teacher_data["phone"],
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True
        )
        session.add(user)
        await session.flush()
        
        teachers_created.append({
            "user": user,
            "teacher_data": teacher_data
        })
        print(f"  ✓ Created user: {teacher_data['first_name']} {teacher_data['last_name']}")
    
    return teachers_created


async def create_staff_records(session, school_id, teachers_created):
    """Create Staff records for teachers"""
    print("\n=== CREATING STAFF RECORDS ===")
    
    staff_records = []
    staff_counter = 1000  # Start staff IDs from 1000
    
    for teacher_info in teachers_created:
        user = teacher_info["user"]
        teacher_data = teacher_info["teacher_data"]
        
        # Check if staff record already exists
        result = await session.execute(
            select(Staff).where(Staff.user_id == user.id)
        )
        if result.scalar_one_or_none():
            print(f"  ⊘ Staff record for {user.email} already exists, skipping...")
            continue
        
        # Create staff record with generated staff_id
        staff_id = f"STF{staff_counter}"
        staff_counter += 1
        
        staff = Staff(
            school_id=school_id,
            staff_id=staff_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone,
            date_of_birth="1990-01-01",  # Placeholder
            gender="Other",  # Placeholder
            position=teacher_data["position"],
            department=teacher_data["department"],
            qualification=teacher_data["qualification"],
            staff_type=StaffType.TEACHING,
            status=StaffStatus.ACTIVE,
            user_id=user.id,
            date_joined="2024-01-01",  # Placeholder
        )
        session.add(staff)
        await session.flush()
        
        staff_records.append({
            "staff": staff,
            "user": user,
            "teacher_data": teacher_data
        })
        print(f"  ✓ Created staff record: {staff.first_name} {staff.last_name}")
    
    return staff_records


async def create_teacher_assignments(session, school_id, staff_records, subjects_map):
    """Create teacher assignments to classes and subjects"""
    print("\n=== CREATING TEACHER ASSIGNMENTS ===")
    
    # Get all classes for the school
    class_result = await session.execute(
        select(Classroom).where(Classroom.school_id == school_id)
    )
    classes = class_result.scalars().all()
    
    if not classes:
        print("⚠ No classes found. Please seed classes first.")
        return
    
    # Get or create current academic term
    term_result = await session.execute(
        select(AcademicTerm).where(
            (AcademicTerm.school_id == school_id) &
            (AcademicTerm.is_current == True)
        )
    )
    current_term = term_result.scalar()
    
    if not current_term:
        print("⚠ No current academic term found. Creating one...")
        current_term = AcademicTerm(
            school_id=school_id,
            academic_year="2025/2026",
            term=TermType.SECOND,
            start_date="2026-03-01",
            end_date="2026-06-30",
            is_current=True
        )
        session.add(current_term)
        await session.flush()
    
    assignments_created = 0
    
    for staff_idx, staff_info in enumerate(staff_records):
        staff = staff_info["staff"]
        teacher_data = staff_info["teacher_data"]
        
        # Get subjects for this teacher
        teacher_subjects = [subjects_map.get(s) for s in teacher_data["subjects"]]
        teacher_subjects = [s for s in teacher_subjects if s is not None]
        
        if not teacher_subjects:
            print(f"  ⚠ No subjects found for {staff.first_name}. Skipping assignments...")
            continue
        
        # Assign to classes
        for idx, class_obj in enumerate(classes):
            # Skip some teachers from some classes to vary assignments
            if idx % 2 != 0 and staff_idx % 3 != 0:
                continue
            
            for subject in teacher_subjects:
                # Check if assignment already exists
                assign_result = await session.execute(
                    select(TeacherAssignment).where(
                        (TeacherAssignment.school_id == school_id) &
                        (TeacherAssignment.staff_id == staff.id) &
                        (TeacherAssignment.class_id == class_obj.id) &
                        (TeacherAssignment.subject_id == subject.id) &
                        (TeacherAssignment.academic_term_id == current_term.id)
                    )
                )
                if assign_result.scalar_one_or_none():
                    continue  # Already exists
                
                # Create assignment
                is_class_teacher = (
                    teacher_data.get("is_class_teacher", False) and 
                    idx == 0 and 
                    subject.name == teacher_data["subjects"][0]
                )
                
                assignment = TeacherAssignment(
                    school_id=school_id,
                    staff_id=staff.id,
                    class_id=class_obj.id,
                    subject_id=subject.id,
                    academic_term_id=current_term.id,
                    is_class_teacher=is_class_teacher,
                    assigned_date=datetime.utcnow()
                )
                session.add(assignment)
                assignments_created += 1
    
    await session.flush()
    print(f"✓ Created {assignments_created} teacher assignments")


async def seed_teacher_data():
    """Main seed function"""
    print("=" * 60)
    print("SEEDING TEACHER DATA")
    print("=" * 60)
    
    # Initialize database
    await init_db()
    
    async with async_session() as session:
        # Get admin user first
        admin_result = await session.execute(
            select(User).where(User.email == "admin@school.edu.gh")
        )
        admin_user = admin_result.scalar_one_or_none()
        
        if not admin_user:
            print("\n❌ Admin user not found.")
            print("Please run seed_data.py first to create initial users and school.")
            return
        
        # Get school from admin
        school_result = await session.execute(
            select(School).where(School.id == admin_user.school_id)
        )
        school = school_result.scalar_one_or_none()
        
        if not school:
            print("❌ No school found for admin user.")
            return
        
        print(f"\n📚 Using school: {school.name} (ID: {school.id})")
        print(f"✓ Admin user: {admin_user.email}")
        
        # Create subjects
        subjects_map = await create_subjects(session, school.id)
        
        # Create teacher users
        teachers_created = await create_teacher_users(session, school.id)
        
        if not teachers_created:
            print("⚠ No new teachers to create. Exiting...")
            return
        
        # Create staff records
        staff_records = await create_staff_records(session, school.id, teachers_created)
        
        # Create teacher assignments
        await create_teacher_assignments(session, school.id, staff_records, subjects_map)
        
        # Commit all changes
        await session.commit()
        
        print("\n" + "=" * 60)
        print("✅ TEACHER DATA SEEDING COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
        # Print summary
        print("\n=== SUMMARY ===")
        print(f"✓ {len(staff_records)} teacher accounts created")
        print(f"✓ {len(subjects_map)} subjects available")
        print(f"✓ Multiple teacher-to-class assignments created")
        
        print("\n=== TEACHER LOGIN CREDENTIALS ===")
        for teacher_info in teachers_created:
            teacher_data = teacher_info["teacher_data"]
            print(f"\nTeacher: {teacher_data['first_name']} {teacher_data['last_name']}")
            print(f"  Email: {teacher_data['email']}")
            print(f"  Password: teacher123")
            print(f"  Position: {teacher_data['position']}")
            print(f"  Subjects: {', '.join(teacher_data['subjects'])}")
            if teacher_data.get("is_class_teacher"):
                print(f"  Role: Class Teacher + Subject Teacher")
        
        print("\n✓ All teachers can now log in to the Teacher Portal at /teacher-portal")


if __name__ == "__main__":
    asyncio.run(seed_teacher_data())
