"""
Seed script: Kwame Nkrumah Memorial School (KNMS)

Creates realistic test data for ONE school including:
  - 1 school record
  - 1 school admin account
  - 8 teaching staff + 1 HR + 1 security officer + 1 driver
  - 11 classes (KG1 through JHS 3)
  - 8 subjects per class
  - TeacherAssignment records
  - 30 students across classes
  - OTPSettings for all users

Usage:
    python seed_test_school.py

Environment:
    DATABASE_URL  (default: postgresql+asyncpg://campusio:campusio123@localhost:5432/campusio_db)
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow imports from the backend package
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Import all models so SQLModel metadata is fully populated
import models  # noqa: F401 — side-effect: registers all table metadata

from models.user import User, UserRole
from models.school import School, SchoolType
from models.staff import Staff, StaffType, StaffStatus, TeacherAssignment
from models.student import Student, Gender, StudentStatus
from models.classroom import Class as Classroom, ClassLevel, Subject, SubjectCategory, ClassSubject
from models.otp import OTPSettings
from models.school import AcademicTerm, TermType
from models.transport import Vehicle, VehicleType, VehicleStatus, Route, RouteStatus, DriverStaff
from models.security import StudentSecurityProfile

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://campusio:campusio123@localhost:5432/campusio_db",
)

# Normalise URL scheme
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionFactory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helper: delete all rows in reverse dependency order
# ---------------------------------------------------------------------------
# All known tables in reverse dependency order (leaf tables first, root tables last).
# Using TRUNCATE ... CASCADE is simpler but requires superuser on some setups,
# so we DELETE in explicit order instead.
TABLES_DELETE_ORDER = [
    # ----- Leaf / most-dependent tables -----
    "subledger_matches",
    "subledger_adjustments",
    "subledger_details",
    "subledger_reconciliations",
    "bank_reconciliation_adjustments",
    "bank_reconciliation_matches",
    "bank_reconciliations",
    "bank_statements",
    "hierarchy_rollups",
    "hierarchy_consolidations",
    "hierarchy_relationships",
    "hierarchy_nodes",
    "account_hierarchies",
    "gl_audit_logs",
    "journal_line_items",
    "journal_entries",
    "fiscal_periods",
    "deduction_rules",
    "payment_verifications",
    "online_transactions",
    "withdrawals",
    "subscription_invoices",
    "platform_subscriptions",
    "billing_configurations",
    "discount_rules",
    "payment_reminders",
    "late_fee_charges",
    "ticket_notifications",
    "ticket_attachments",
    "ticket_comments",
    "tickets",
    "sms_notifications",
    "email_notifications",
    "messages",
    "announcements",
    "student_progress_notes",
    "submissions",
    "assignment_questions",
    "assignments",
    "learning_materials",
    "teacher_resources",
    "report_cards",
    "report_templates",
    "grade_scales",
    "grades",
    "payroll_adjustments",
    "payroll_line_items",
    "payroll_runs",
    "payroll_contracts",
    "staff_attendance",
    "attendance",
    "periods",
    "timetables",
    "hostel_complaints",
    "hostel_visitors",
    "hostel_maintenance",
    "hostel_fees",
    "hostel_fee_structures",
    "hostel_attendance",
    "room_allocations",
    "student_hostels",
    "rooms",
    "hostels",
    "transport_attendance",
    "transport_fees",
    "student_transport",
    "vehicle_maintenance",
    "driver_staff",
    "routes",
    "vehicles",
    "fee_payments",
    "fees",
    "fee_structures",
    "security_scan_logs",
    "arrival_events",
    "parent_notes",
    "live_bus_locations",
    "collector_live_locations",
    "collector_tracking_sessions",
    "daily_qr_tokens",
    "student_security_profiles",
    "teacher_assignments",
    "class_subjects",
    "student_parents",
    "otps",
    "otp_settings",
    "otp_admin_settings",
    "students",
    "parents",
    "staff",
    "classes",
    "subjects",
    "payroll_contracts",  # listed again in case FK ordering differs
    "gl_accounts",
    "expenses",
    "academic_terms",
    "users",
    "schools",
]


async def clear_all_data(session: AsyncSession) -> None:
    print("\n[1/4] Clearing existing data from all tables (reverse dependency order)...")
    seen: set[str] = set()
    for table in TABLES_DELETE_ORDER:
        if table in seen:
            continue
        seen.add(table)
        try:
            result = await session.execute(text(f"DELETE FROM {table}"))
            print(f"      Deleted {result.rowcount:>5} rows from {table}")
        except Exception as exc:
            # Table may not exist yet — skip silently
            print(f"      Skipped {table}: {type(exc).__name__}")
            await session.rollback()
    await session.commit()
    print("      Done.\n")


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

SCHOOL_ID = new_id()
ACADEMIC_TERM_ID = new_id()

# 11 classes
CLASS_DEFS = [
    ("KG 1",      ClassLevel.KG1,       "A", "R01"),
    ("KG 2",      ClassLevel.KG2,       "A", "R02"),
    ("Primary 1", ClassLevel.PRIMARY_1, "A", "R03"),
    ("Primary 2", ClassLevel.PRIMARY_2, "A", "R04"),
    ("Primary 3", ClassLevel.PRIMARY_3, "A", "R05"),
    ("Primary 4", ClassLevel.PRIMARY_4, "A", "R06"),
    ("Primary 5", ClassLevel.PRIMARY_5, "A", "R07"),
    ("Primary 6", ClassLevel.PRIMARY_6, "A", "R08"),
    ("JHS 1",     ClassLevel.JHS_1,     "A", "R09"),
    ("JHS 2",     ClassLevel.JHS_2,     "A", "R10"),
    ("JHS 3",     ClassLevel.JHS_3,     "A", "R11"),
]

# 8 subjects with codes
SUBJECT_DEFS = [
    ("English Language",          "ENG",  SubjectCategory.CORE,     "Reading, writing and oral communication"),
    ("Mathematics",               "MATH", SubjectCategory.CORE,     "Number, algebra, geometry and statistics"),
    ("Science",                   "SCI",  SubjectCategory.CORE,     "Basic integrated science concepts"),
    ("Social Studies",            "SOC",  SubjectCategory.CORE,     "History, geography and civic education"),
    ("ICT",                       "ICT",  SubjectCategory.ELECTIVE, "Computer literacy and digital skills"),
    ("Ghanaian Language",         "GHL",  SubjectCategory.CORE,     "Twi, Ga, Ewe or other Ghanaian language"),
    ("Creative Arts",             "CRA",  SubjectCategory.CORE,     "Visual arts, music and drama"),
    ("Religious & Moral Education","RME", SubjectCategory.CORE,     "Values, ethics and religious studies"),
]

# 8 teaching staff
TEACHER_DATA = [
    # (first, last, gender, dob, phone, qualification, position)
    ("Kwame",    "Asante",     "male",   "1985-03-12", "+233 24 100 1001", "B.Ed. English",         "English Teacher"),
    ("Abena",    "Boateng",    "female", "1990-07-25", "+233 24 100 1002", "B.Ed. Mathematics",     "Mathematics Teacher"),
    ("Kofi",     "Mensah",     "male",   "1988-11-04", "+233 24 100 1003", "B.Sc. Integrated Sci.", "Science Teacher"),
    ("Akosua",   "Acheampong", "female", "1992-01-18", "+233 24 100 1004", "B.A. Social Studies",   "Social Studies Teacher"),
    ("Fiifi",    "Annan",      "male",   "1987-06-30", "+233 24 100 1005", "B.Sc. Computer Sci.",   "ICT Teacher"),
    ("Adwoa",    "Owusu",      "female", "1993-09-14", "+233 24 100 1006", "Dip. Ed. Ghanaian Lang","Ghanaian Language Teacher"),
    ("Nana",     "Amponsah",   "male",   "1986-04-22", "+233 24 100 1007", "B.A. Creative Arts",    "Creative Arts Teacher"),
    ("Efua",     "Darko",      "female", "1991-12-05", "+233 24 100 1008", "B.Ed. RME",             "RME Teacher"),
]

# Non-teaching staff: HR, Security Officer
NON_TEACHING_STAFF_DATA = [
    # (first, last, gender, dob, phone, qualification, position, staff_type)
    ("Ama",      "Frimpong",   "female", "1984-08-17", "+233 24 200 2001", "HND HR Management",   "HR Officer",        StaffType.NON_TEACHING),
    ("Kweku",    "Tetteh",     "male",   "1979-02-28", "+233 24 200 2002", "WASSCE",               "Security Officer",  StaffType.NON_TEACHING),
]

# Driver
DRIVER_DATA = ("Yaw", "Asamoah", "male", "1982-05-10", "+233 24 300 3001", "WASSCE + Driving Lic.", "School Driver")

# 30 students (first, last, gender, dob, class_index 0-10)
STUDENT_DATA = [
    # KG1 (index 0)
    ("Kojo",      "Mensah",      Gender.MALE,   "2020-04-05", 0),
    ("Abena",     "Asante",      Gender.FEMALE, "2020-07-11", 0),
    ("Kwabena",   "Owusu",       Gender.MALE,   "2020-01-29", 0),
    # KG2 (index 1)
    ("Akua",      "Boateng",     Gender.FEMALE, "2019-09-14", 1),
    ("Kofi",      "Acheampong",  Gender.MALE,   "2019-03-22", 1),
    # Primary 1 (index 2)
    ("Adwoa",     "Annan",       Gender.FEMALE, "2018-06-01", 2),
    ("Fiifi",     "Amponsah",    Gender.MALE,   "2018-11-17", 2),
    ("Efua",      "Darko",       Gender.FEMALE, "2018-02-08", 2),
    # Primary 2 (index 3)
    ("Nana",      "Frimpong",    Gender.MALE,   "2017-08-30", 3),
    ("Ama",       "Tetteh",      Gender.FEMALE, "2017-12-12", 3),
    # Primary 3 (index 4)
    ("Yaw",       "Appiah",      Gender.MALE,   "2016-05-19", 4),
    ("Akosua",    "Mensah",      Gender.FEMALE, "2016-10-03", 4),
    ("Kwame",     "Ofori",       Gender.MALE,   "2016-03-27", 4),
    # Primary 4 (index 5)
    ("Abena",     "Quaye",       Gender.FEMALE, "2015-07-08", 5),
    ("Kweku",     "Asare",       Gender.MALE,   "2015-01-14", 5),
    # Primary 5 (index 6)
    ("Araba",     "Yankey",      Gender.FEMALE, "2014-09-25", 6),
    ("Kwasi",     "Donkor",      Gender.MALE,   "2014-04-16", 6),
    ("Esi",       "Acquah",      Gender.FEMALE, "2014-11-02", 6),
    # Primary 6 (index 7)
    ("Nii",       "Laryea",      Gender.MALE,   "2013-06-20", 7),
    ("Akweley",   "Teye",        Gender.FEMALE, "2013-02-05", 7),
    # JHS 1 (index 8)
    ("Kwabena",   "Owusu-Agyei", Gender.MALE,   "2012-08-14", 8),
    ("Maame",     "Sarpong",     Gender.FEMALE, "2012-04-28", 8),
    ("Kofi",      "Wiredu",      Gender.MALE,   "2012-12-09", 8),
    ("Adwoa",     "Bonsu",       Gender.FEMALE, "2012-07-31", 8),
    # JHS 2 (index 9)
    ("Kweku",     "Baafi",       Gender.MALE,   "2011-03-17", 9),
    ("Afia",      "Agyemang",    Gender.FEMALE, "2011-09-22", 9),
    ("Yaw",       "Boadi",       Gender.MALE,   "2011-01-06", 9),
    # JHS 3 (index 10)
    ("Abena",     "Asiedu",      Gender.FEMALE, "2010-05-13", 10),
    ("Kwame",     "Twum",        Gender.MALE,   "2010-11-28", 10),
    ("Akosua",    "Peprah",      Gender.FEMALE, "2010-08-02", 10),
]


# ---------------------------------------------------------------------------
# Main seeding function
# ---------------------------------------------------------------------------

async def seed() -> None:
    print("=" * 65)
    print("  SEED SCRIPT: Kwame Nkrumah Memorial School (KNMS)")
    print("  Database:", DATABASE_URL.split("@")[-1])  # hide credentials
    print("=" * 65)

    async with AsyncSessionFactory() as session:

        # ------------------------------------------------------------------
        # Step 1: Clear all tables
        # ------------------------------------------------------------------
        await clear_all_data(session)

        # ------------------------------------------------------------------
        # Step 2: Create school
        # ------------------------------------------------------------------
        print("[2/4] Creating school, admin, academic term...")

        school = School(
            id=SCHOOL_ID,
            name="Kwame Nkrumah Memorial School",
            code="KNMS",
            school_type=SchoolType.COMBINED,
            address="14 Nkrumah Avenue, Kumasi",
            city="Kumasi",
            region="Ashanti",
            phone="+233 32 200 0001",
            email="info@knms.edu.gh",
            motto="Knowledge, Discipline, Excellence",
            is_active=True,
        )
        session.add(school)
        await session.flush()

        # Academic term (2025/2026 – Term 1, current)
        term = AcademicTerm(
            id=ACADEMIC_TERM_ID,
            school_id=SCHOOL_ID,
            academic_year="2025/2026",
            term=TermType.FIRST,
            start_date="2025-09-08",
            end_date="2025-12-19",
            is_current=True,
        )
        session.add(term)
        await session.flush()

        # ------------------------------------------------------------------
        # Step 3: School admin user
        # ------------------------------------------------------------------
        admin_password = "Admin@123"
        admin_user = User(
            id=new_id(),
            email="admin@knms.edu.gh",
            password_hash=get_password_hash(admin_password),
            plain_text_password=admin_password,
            first_name="Adjoa",
            last_name="Nkrumah",
            phone="+233 24 900 0001",
            role=UserRole.SCHOOL_ADMIN,
            school_id=SCHOOL_ID,
            must_change_password=False,
        )
        session.add(admin_user)
        await session.flush()

        # OTP settings for admin — mandatory OTP (school_admin is in MANDATORY_OTP_ROLES)
        session.add(OTPSettings(
            user_id=admin_user.id,
            is_enabled=True,
            is_mandatory=True,
            method="sms",
        ))

        await session.flush()
        print(f"      School admin: {admin_user.email}  /  {admin_password}")

        # ------------------------------------------------------------------
        # Step 4: Classes
        # ------------------------------------------------------------------
        print("[3/4] Creating classes, subjects, staff, students...")

        class_ids: list[str] = []
        for (name, level, section, room) in CLASS_DEFS:
            cls = Classroom(
                id=new_id(),
                school_id=SCHOOL_ID,
                name=name,
                level=level,
                section=section,
                capacity=40,
                room_number=room,
                academic_term_id=ACADEMIC_TERM_ID,
                is_active=True,
            )
            session.add(cls)
            class_ids.append(cls.id)

        await session.flush()

        # ------------------------------------------------------------------
        # Step 5: Subjects
        # ------------------------------------------------------------------
        subject_ids: list[str] = []
        for (name, code, category, description) in SUBJECT_DEFS:
            subj = Subject(
                id=new_id(),
                school_id=SCHOOL_ID,
                name=name,
                code=code,
                category=category,
                description=description,
                credit_hours=1,
                is_active=True,
            )
            session.add(subj)
            subject_ids.append(subj.id)

        await session.flush()

        # ------------------------------------------------------------------
        # Step 6: ClassSubject mappings (every class gets all 8 subjects)
        # ------------------------------------------------------------------
        for class_id in class_ids:
            for subject_id in subject_ids:
                session.add(ClassSubject(
                    id=new_id(),
                    school_id=SCHOOL_ID,
                    class_id=class_id,
                    subject_id=subject_id,
                    academic_term_id=ACADEMIC_TERM_ID,
                ))

        await session.flush()

        # ------------------------------------------------------------------
        # Step 7: Teaching staff + portal accounts
        # ------------------------------------------------------------------
        teacher_staff_ids: list[str] = []

        for idx, (first, last, gender, dob, phone, qualification, position) in enumerate(TEACHER_DATA):
            # Portal account
            email = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}@knms001.school.edu.gh"
            plain_pw = f"Teacher@{idx + 1}001"

            user = User(
                id=new_id(),
                email=email,
                password_hash=get_password_hash(plain_pw),
                plain_text_password=plain_pw,
                first_name=first,
                last_name=last,
                phone=phone,
                role=UserRole.TEACHER,
                school_id=SCHOOL_ID,
                must_change_password=True,
            )
            session.add(user)
            await session.flush()

            session.add(OTPSettings(
                user_id=user.id,
                is_enabled=False,
                is_mandatory=False,
                method="sms",
            ))

            staff_record_id = new_id()
            staff = Staff(
                id=staff_record_id,
                school_id=SCHOOL_ID,
                staff_id=f"KNMS-TCH-{idx + 1:03d}",
                first_name=first,
                last_name=last,
                email=email,
                phone=phone,
                date_of_birth=dob,
                gender=gender,
                staff_type=StaffType.TEACHING,
                position=position,
                department="Academics",
                qualification=qualification,
                date_joined="2022-09-05",
                address="Kumasi, Ashanti Region",
                status=StaffStatus.ACTIVE,
                user_id=user.id,
            )
            session.add(staff)
            teacher_staff_ids.append(staff_record_id)

        await session.flush()

        # ------------------------------------------------------------------
        # Step 8: Non-teaching staff (HR + Security Officer) + portal accounts
        # ------------------------------------------------------------------
        non_teach_user_roles = [UserRole.HR, UserRole.SECURITY_OFFICER]

        for idx, (first, last, gender, dob, phone, qualification, position, staff_type) in enumerate(NON_TEACHING_STAFF_DATA):
            role = non_teach_user_roles[idx]
            email = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}@knms001.school.edu.gh"
            plain_pw = f"Staff@{idx + 1}001"

            user = User(
                id=new_id(),
                email=email,
                password_hash=get_password_hash(plain_pw),
                plain_text_password=plain_pw,
                first_name=first,
                last_name=last,
                phone=phone,
                role=role,
                school_id=SCHOOL_ID,
                must_change_password=True,
            )
            session.add(user)
            await session.flush()

            # HR is in MANDATORY_OTP_ROLES; security officer is not
            is_mandatory_otp = role == UserRole.HR
            session.add(OTPSettings(
                user_id=user.id,
                is_enabled=is_mandatory_otp,
                is_mandatory=is_mandatory_otp,
                method="sms",
            ))

            staff = Staff(
                id=new_id(),
                school_id=SCHOOL_ID,
                staff_id=f"KNMS-NTC-{idx + 1:03d}",
                first_name=first,
                last_name=last,
                email=email,
                phone=phone,
                date_of_birth=dob,
                gender=gender,
                staff_type=staff_type,
                position=position,
                department="Administration" if role == UserRole.HR else "Security",
                qualification=qualification,
                date_joined="2022-09-05",
                address="Kumasi, Ashanti Region",
                status=StaffStatus.ACTIVE,
                user_id=user.id,
            )
            session.add(staff)

        await session.flush()

        # ------------------------------------------------------------------
        # Step 9: Driver + portal account
        # ------------------------------------------------------------------
        (d_first, d_last, d_gender, d_dob, d_phone, d_qual, d_pos) = DRIVER_DATA
        driver_email = f"{d_first.lower()}.{d_last.lower()}@knms001.school.edu.gh"
        driver_pw = "Driver@001"

        driver_user = User(
            id=new_id(),
            email=driver_email,
            password_hash=get_password_hash(driver_pw),
            plain_text_password=driver_pw,
            first_name=d_first,
            last_name=d_last,
            phone=d_phone,
            role=UserRole.DRIVER,
            school_id=SCHOOL_ID,
            must_change_password=True,
        )
        session.add(driver_user)
        await session.flush()

        session.add(OTPSettings(
            user_id=driver_user.id,
            is_enabled=False,
            is_mandatory=False,
            method="sms",
        ))

        driver_staff_record = Staff(
            id=new_id(),
            school_id=SCHOOL_ID,
            staff_id="KNMS-DRV-001",
            first_name=d_first,
            last_name=d_last,
            email=driver_email,
            phone=d_phone,
            date_of_birth=d_dob,
            gender=d_gender,
            staff_type=StaffType.NON_TEACHING,
            position=d_pos,
            department="Transport",
            qualification=d_qual,
            date_joined="2022-09-05",
            address="Kumasi, Ashanti Region",
            status=StaffStatus.ACTIVE,
            user_id=driver_user.id,
        )
        session.add(driver_staff_record)

        await session.flush()

        # ------------------------------------------------------------------
        # Step 9b: Vehicle + DriverStaff + Route (school bus transport)
        # ------------------------------------------------------------------
        driver_staff_assignment = DriverStaff(
            id=new_id(),
            school_id=SCHOOL_ID,
            staff_id=driver_staff_record.id,
            license_number="DL-KNMS-2024-001",
            license_expiry="2027-05-10",
            role="driver",
            is_active=True,
            is_verified=True,
        )
        session.add(driver_staff_assignment)
        await session.flush()

        school_bus = Vehicle(
            id=new_id(),
            school_id=SCHOOL_ID,
            registration_number="GR-4521-22",
            vehicle_type=VehicleType.BUS,
            make="Toyota",
            model="Coaster",
            year=2019,
            seating_capacity=30,
            driver_id=driver_staff_assignment.id,
            status=VehicleStatus.ACTIVE,
        )
        session.add(school_bus)
        await session.flush()

        school_route = Route(
            id=new_id(),
            school_id=SCHOOL_ID,
            route_name="Kumasi Central Route",
            start_point="Kumasi Central Market",
            end_point="Kwame Nkrumah Memorial School",
            route_code="KNMS-RT-01",
            distance_km=8.5,
            estimated_duration_minutes=25,
            vehicle_id=school_bus.id,
            pickup_time="06:30",
            dropoff_time="15:30",
            pickup_days=json.dumps(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]),
            fee_amount=150.0,
            status=RouteStatus.ACTIVE,
        )
        session.add(school_route)
        await session.flush()

        # ------------------------------------------------------------------
        # Step 10: TeacherAssignments
        # Each teacher (8 total, indexed 0-7) maps to a subject (0-7 correspondingly).
        # Each teacher is also assigned 2-3 class levels.
        # Teacher 0 → English  (classes: KG1, KG2, P1)
        # Teacher 1 → Math     (classes: P2, P3, P4)
        # Teacher 2 → Science  (classes: P5, P6, JHS1)
        # Teacher 3 → Social   (classes: JHS2, JHS3, KG1)
        # Teacher 4 → ICT      (classes: P1, P4, JHS1)
        # Teacher 5 → Ghanaian (classes: KG2, P2, JHS2)
        # Teacher 6 → CreArts  (classes: P3, P5, JHS3)
        # Teacher 7 → RME      (classes: P6, JHS1, JHS2)
        # ------------------------------------------------------------------
        TEACHER_ASSIGNMENT_MAP = [
            # (teacher_staff_idx, subject_idx, [class_indices], is_class_teacher_for_first)
            (0, 0, [0, 1, 2],  True),   # English → KG1, KG2, P1
            (1, 1, [3, 4, 5],  True),   # Math    → P2, P3, P4
            (2, 2, [6, 7, 8],  True),   # Science → P5, P6, JHS1
            (3, 3, [9, 10, 0], True),   # Social  → JHS2, JHS3, KG1
            (4, 4, [2, 5, 8],  False),  # ICT     → P1, P4, JHS1
            (5, 5, [1, 3, 9],  False),  # Ghanaian→ KG2, P2, JHS2
            (6, 6, [4, 6, 10], True),   # CreArts → P3, P5, JHS3
            (7, 7, [7, 8, 9],  False),  # RME     → P6, JHS1, JHS2
        ]

        for (t_idx, s_idx, c_indices, is_ct) in TEACHER_ASSIGNMENT_MAP:
            staff_id = teacher_staff_ids[t_idx]
            subject_id = subject_ids[s_idx]
            for i, c_idx in enumerate(c_indices):
                session.add(TeacherAssignment(
                    id=new_id(),
                    school_id=SCHOOL_ID,
                    staff_id=staff_id,
                    class_id=class_ids[c_idx],
                    subject_id=subject_id,
                    academic_term_id=ACADEMIC_TERM_ID,
                    is_class_teacher=(is_ct and i == 0),  # only class teacher for first class
                ))

        await session.flush()

        # ------------------------------------------------------------------
        # Step 11: Students + portal accounts
        # ------------------------------------------------------------------
        student_count = 0
        student_ids: list[str] = []
        for idx, (first, last, gender, dob, class_idx) in enumerate(STUDENT_DATA):
            student_id_code = f"KNMS{2025}{idx + 1:03d}"
            email = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}.{student_id_code.lower()}@knms001.school.edu.gh"
            plain_pw = f"Student@{idx + 1:03d}"

            stu_user = User(
                id=new_id(),
                email=email,
                password_hash=get_password_hash(plain_pw),
                plain_text_password=plain_pw,
                first_name=first,
                last_name=last,
                role=UserRole.STUDENT,
                school_id=SCHOOL_ID,
                must_change_password=True,
            )
            session.add(stu_user)
            await session.flush()

            session.add(OTPSettings(
                user_id=stu_user.id,
                is_enabled=False,
                is_mandatory=False,
                method="sms",
            ))

            student_obj = Student(
                id=new_id(),
                school_id=SCHOOL_ID,
                student_id=student_id_code,
                first_name=first,
                last_name=last,
                date_of_birth=dob,
                gender=gender,
                class_id=class_ids[class_idx],
                admission_date="2025-09-08",
                nationality="Ghanaian",
                status=StudentStatus.ACTIVE,
                user_id=stu_user.id,
            )
            session.add(student_obj)
            student_ids.append(student_obj.id)

            student_count += 1

        await session.flush()

        # ------------------------------------------------------------------
        # Step 11b: Security profiles — every 3rd student rides the school
        # bus (transport pickup), the rest are collected by a parent.
        # ------------------------------------------------------------------
        transport_count = 0
        for idx, student_id in enumerate(student_ids):
            on_transport = idx % 3 == 0
            session.add(StudentSecurityProfile(
                id=new_id(),
                student_id=student_id,
                school_id=SCHOOL_ID,
                pickup_method="transport" if on_transport else "parent",
                transport_route_id=school_route.id if on_transport else None,
            ))
            if on_transport:
                transport_count += 1

        await session.flush()
        await session.commit()

        # ------------------------------------------------------------------
        # Step 12: Print summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 65)
        print("  SEED COMPLETE — Summary")
        print("=" * 65)
        print(f"  School        : Kwame Nkrumah Memorial School")
        print(f"  Code          : KNMS")
        print(f"  Short code    : knms001")
        print(f"  Academic Year : 2025/2026, Term 1")
        print()
        print(f"  Classes       : {len(CLASS_DEFS)} (KG1 → JHS 3)")
        print(f"  Subjects      : {len(SUBJECT_DEFS)} per class")
        print(f"  Class-Subject : {len(CLASS_DEFS) * len(SUBJECT_DEFS)} mappings")
        print()
        print(f"  Teaching staff: {len(TEACHER_DATA)}")
        print(f"  Non-teaching  : {len(NON_TEACHING_STAFF_DATA)} (HR + Security Officer)")
        print(f"  Driver        : 1")
        print(f"  Teacher assgn : {sum(len(c) for (_, _, c, _) in TEACHER_ASSIGNMENT_MAP)} assignments")
        print()
        print(f"  Students      : {student_count}")
        print(f"  Transport     : 1 route (Kumasi Central) — {transport_count} students on school bus")
        print(f"  Parent pickup : {student_count - transport_count} students")
        print()
        print("  ---- Login Credentials ----")
        print()
        print("  SCHOOL ADMIN")
        print(f"    Email   : {admin_user.email}")
        print(f"    Password: {admin_password}")
        print(f"    OTP     : ENABLED (mandatory, via SMS)")
        print()
        print("  TEACHERS  (must_change_password=True)")
        for idx, (first, last, _, _, _, _, _) in enumerate(TEACHER_DATA):
            email_t = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}@knms001.school.edu.gh"
            pw_t = f"Teacher@{idx + 1}001"
            print(f"    {email_t:<52}  pw: {pw_t}")
        print()
        print("  NON-TEACHING STAFF  (must_change_password=True)")
        for idx, (first, last, _, _, _, _, _, _) in enumerate(NON_TEACHING_STAFF_DATA):
            email_nt = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}@knms001.school.edu.gh"
            pw_nt = f"Staff@{idx + 1}001"
            print(f"    {email_nt:<52}  pw: {pw_nt}")
        print()
        print("  DRIVER  (must_change_password=True)")
        print(f"    {driver_email:<52}  pw: {driver_pw}")
        print()
        print("  STUDENTS  (must_change_password=True)")
        for idx, (first, last, _, _, class_idx) in enumerate(STUDENT_DATA):
            student_id_code = f"KNMS{2025}{idx + 1:03d}"
            email_s = f"{first.lower()}.{last.lower().replace('-', '').replace(' ', '')}.{student_id_code.lower()}@knms001.school.edu.gh"
            pw_s = f"Student@{idx + 1:03d}"
            cls_name = CLASS_DEFS[class_idx][0]
            print(f"    [{cls_name:<9}]  {email_s:<62}  pw: {pw_s}")
        print()
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(seed())
