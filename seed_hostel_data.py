"""Comprehensive seed data for Hostel Module
This script initializes:
1. Hostels (dormitory units with facilities)
2. Rooms (individual accommodations within hostels)
3. Student Allocations (room assignments)
4. Hostel Fees (monthly/semester charges)
5. Attendance Records (check-in/check-out tracking)
6. Maintenance Records (facility repairs)
7. Complaints (student issues)
8. Visitor Logs (guest tracking)
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_session, init_db
from models.user import User, UserRole
from models.school import School
from models.student import Student, Gender, StudentStatus
from models.hostel import (
    Hostel, HostelStatus,
    Room, RoomType, RoomStatus,
    StudentHostel, StudentHostelStatus,
    HostelAttendance, CheckInStatus,
    HostelFee, HostelFeeType,
    HostelMaintenance,
    HostelComplaint,
    HostelVisitor
)

# Default Hostel Configurations
DEFAULT_HOSTELS = [
    {
        "hostel_name": "Boys Hostel A",
        "hostel_code": "BH-A",
        "hostel_type": "boys",
        "capacity": 100,
        "warden_name": "Mr. John Agyeman",
        "warden_phone": "+233501234567",
        "location": "North Campus",
        "has_wifi": True,
        "has_laundry": True,
        "has_kitchen": False,
        "has_common_room": True,
        "has_security": True,
    },
    {
        "hostel_name": "Girls Hostel A",
        "hostel_code": "GH-A",
        "hostel_type": "girls",
        "capacity": 80,
        "warden_name": "Ms. Abena Owusu",
        "warden_phone": "+233502345678",
        "location": "South Campus",
        "has_wifi": True,
        "has_laundry": True,
        "has_kitchen": True,
        "has_common_room": True,
        "has_security": True,
    },
    {
        "hostel_name": "Mixed Hostel B",
        "hostel_code": "MH-B",
        "hostel_type": "mixed",
        "capacity": 120,
        "warden_name": "Mr. Samuel Boateng",
        "warden_phone": "+233503456789",
        "location": "East Campus",
        "has_wifi": True,
        "has_laundry": True,
        "has_kitchen": True,
        "has_common_room": True,
        "has_security": True,
    },
]

# Room Templates for Different Hostel Types
ROOM_TEMPLATES = {
    "double": {"capacity": 2, "room_type": RoomType.DOUBLE},
    "triple": {"capacity": 3, "room_type": RoomType.TRIPLE},
    "single": {"capacity": 1, "room_type": RoomType.SINGLE},
}


async def seed_hostels(session, school_id):
    """Seed Hostel definitions for a school"""
    print("\n=== SEEDING HOSTELS ===")
    
    # Check if hostels already exist
    result = await session.execute(
        select(Hostel).where(Hostel.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Hostels already exist. Skipping...")
        return []
    
    created_hostels = []
    for hostel_data in DEFAULT_HOSTELS:
        hostel = Hostel(
            school_id=school_id,
            status=HostelStatus.ACTIVE,
            **hostel_data
        )
        session.add(hostel)
        created_hostels.append(hostel)
    
    await session.flush()
    print(f"✓ Created {len(created_hostels)} hostels")
    return created_hostels


async def seed_rooms(session, school_id, hostels):
    """Seed Rooms within hostels"""
    print("\n=== SEEDING ROOMS ===")
    
    # Check if rooms already exist
    result = await session.execute(
        select(Room).where(Room.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Rooms already exist. Skipping...")
        return []
    
    created_rooms = []
    room_id = 1
    
    for hostel in hostels:
        # Create mix of room types
        room_configs = [
            ("double", 5),   # 5 double rooms
            ("triple", 5),   # 5 triple rooms
            ("single", 2),   # 2 single rooms
        ]
        
        for room_type_name, count in room_configs:
            config = ROOM_TEMPLATES[room_type_name]
            
            for i in range(count):
                floor = (i // 5) + 1
                room = Room(
                    school_id=school_id,
                    hostel_id=hostel.id,
                    room_number=f"{chr(65 + (i % 5))}{floor:02d}",
                    room_type=config["room_type"],
                    capacity=config["capacity"],
                    floor=floor,
                    has_bathroom=True,
                    has_ac=i % 3 == 0,
                    has_heater=True,
                    has_desk=True,
                    has_bed=True,
                    status=RoomStatus.VACANT,
                )
                session.add(room)
                created_rooms.append(room)
                room_id += 1
    
    await session.flush()
    print(f"✓ Created {len(created_rooms)} rooms across all hostels")
    return created_rooms


async def seed_students(session, school_id, count=20):
    """Get or seed Student records for hostel allocation testing"""
    print("\n=== GETTING STUDENTS ===")
    
    # Fetch existing students (created by seed_data.py or other seeds)
    result = await session.execute(
        select(Student).where(Student.school_id == school_id).limit(count)
    )
    existing_students = result.scalars().all()
    
    if existing_students:
        print(f"✓ Found {len(existing_students)} existing students for allocation")
        return existing_students
    
    # If no students exist, create seed students
    created_students = []
    
    for i in range(1, count + 1):
        student = Student(
            school_id=school_id,
            student_id=f"STU{i:04d}",
            first_name=f"Student",
            last_name=f"Test{i}",
            gender=Gender.MALE if i % 2 == 0 else Gender.FEMALE,
            date_of_birth=date(2008, 1, 15),
            admission_date=date(2024, 9, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(student)
        created_students.append(student)
    
    await session.flush()
    print(f"✓ Created {len(created_students)} student records")
    return created_students


async def seed_allocations(session, school_id, students, hostels, rooms):
    """Seed Student Hostel Allocations"""
    print("\n=== SEEDING ALLOCATIONS ===")
    
    # Check if allocations already exist
    result = await session.execute(
        select(StudentHostel).where(StudentHostel.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Allocations already exist. Skipping...")
        return []
    
    created_allocations = []
    check_in_date = datetime(2026, 4, 1).strftime("%Y-%m-%d")
    
    for i, student in enumerate(students):
        # Distribute students across hostels
        hostel = hostels[i % len(hostels)]
        
        # Get available rooms in this hostel
        rooms_in_hostel = [r for r in rooms if r.hostel_id == hostel.id]
        if not rooms_in_hostel:
            continue
        
        room = rooms_in_hostel[i % len(rooms_in_hostel)]
        
        allocation = StudentHostel(
            school_id=school_id,
            student_id=student.id,
            hostel_id=hostel.id,
            room_id=room.id,
            check_in_date=check_in_date,
            academic_year="2025/2026",
            parent_contact=f"+233{50 + i % 2}{i:08d}",
            emergency_contact=f"Parent {i}",
            emergency_contact_phone=f"+233{50 + i % 2}{i:08d}",
            status=StudentHostelStatus.ACTIVE,
        )
        session.add(allocation)
        created_allocations.append(allocation)
    
    await session.flush()
    print(f"✓ Created {len(created_allocations)} student allocations")
    return created_allocations


async def seed_fees(session, school_id, allocations, admin_user):
    """Seed Hostel Fees for students"""
    print("\n=== SEEDING FEES ===")
    
    # Check if fees already exist
    result = await session.execute(
        select(HostelFee).where(HostelFee.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Hostel fees already exist. Skipping...")
        return []
    
    created_fees = []
    due_date = datetime(2026, 5, 1).strftime("%Y-%m-%d")
    
    for allocation in allocations:
        # Create monthly fee
        fee = HostelFee(
            school_id=school_id,
            student_id=allocation.student_id,
            hostel_id=allocation.hostel_id,
            academic_term_id=None,
            fee_type=HostelFeeType.MONTHLY,
            amount_due=500.0,
            amount_paid=0.0,
            discount=0.0,
            is_paid=False,
            due_date=due_date,
        )
        session.add(fee)
        created_fees.append(fee)
    
    await session.flush()
    print(f"✓ Created {len(created_fees)} hostel fees")
    return created_fees


async def seed_attendance(session, school_id, allocations, admin_user):
    """Seed Hostel Attendance Records"""
    print("\n=== SEEDING ATTENDANCE ===")
    
    # Check if attendance records already exist
    result = await session.execute(
        select(HostelAttendance).where(HostelAttendance.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Attendance records already exist. Skipping...")
        return []
    
    created_attendance = []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    for allocation in allocations:
        # Create attendance record for today
        attendance = HostelAttendance(
            school_id=school_id,
            student_id=allocation.student_id,
            hostel_id=allocation.hostel_id,
            attendance_date=today,
            check_in_time=today_time,
            check_out_time=None,
            status=CheckInStatus.CHECKED_IN,
            notes="Regular check-in",
        )
        session.add(attendance)
        created_attendance.append(attendance)
    
    await session.flush()
    print(f"✓ Created {len(created_attendance)} attendance records")
    return created_attendance


async def seed_maintenance(session, school_id, hostels, admin_user):
    """Seed Maintenance Records"""
    print("\n=== SEEDING MAINTENANCE ===")
    
    # Check if maintenance records already exist
    result = await session.execute(
        select(HostelMaintenance).where(HostelMaintenance.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Maintenance records already exist. Skipping...")
        return []
    
    created_maintenance = []
    
    maintenance_issues = [
        {
            "title": "Broken window in block A",
            "description": "Window in room A01 needs replacement",
            "maintenance_type": "Repair",
            "priority": "high",
            "hostel_index": 0,
        },
        {
            "title": "Air conditioning not working",
            "description": "AC unit in common room needs service",
            "maintenance_type": "Service",
            "priority": "medium",
            "hostel_index": 1,
        },
        {
            "title": "Damaged door hinge",
            "description": "Door hinge in room B02 needs repair",
            "maintenance_type": "Repair",
            "priority": "low",
            "hostel_index": 2,
        },
    ]
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    for issue in maintenance_issues:
        hostel_index = min(issue["hostel_index"], len(hostels) - 1)
        maintenance = HostelMaintenance(
            school_id=school_id,
            hostel_id=hostels[hostel_index].id,
            room_id=None,
            maintenance_date=today,
            maintenance_type=issue["maintenance_type"],
            description=issue["description"],
            cost=0.0,
            status="pending",
            notes=f"Priority: {issue['priority']}",
        )
        session.add(maintenance)
        created_maintenance.append(maintenance)
    
    await session.flush()
    print(f"✓ Created {len(created_maintenance)} maintenance records")
    return created_maintenance


async def seed_complaints(session, school_id, allocations, admin_user):
    """Seed Hostel Complaints"""
    print("\n=== SEEDING COMPLAINTS ===")
    
    # Check if complaints already exist
    result = await session.execute(
        select(HostelComplaint).where(HostelComplaint.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Complaints already exist. Skipping...")
        return []
    
    created_complaints = []
    
    if len(allocations) < 3:
        print("Not enough allocations for sample complaints. Skipping...")
        return []
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    complaints_data = [
        {
            "complaint_type": "Noise",
            "title": "Noise from adjacent room",
            "description": "Students in room B03 making excessive noise at night",
            "priority": "high",
            "allocation_index": 0,
        },
        {
            "complaint_type": "Maintenance",
            "title": "Hot water not available",
            "description": "Hot water supply in bathroom is not working",
            "priority": "medium",
            "allocation_index": 1,
        },
        {
            "complaint_type": "Cleanliness",
            "title": "Missing bedsheets",
            "description": "Bedsheets were not provided upon check-in",
            "priority": "normal",
            "allocation_index": 2,
        },
    ]
    
    for complaint_data in complaints_data:
        allocation = allocations[complaint_data["allocation_index"]]
        complaint = HostelComplaint(
            school_id=school_id,
            student_id=allocation.student_id,
            hostel_id=allocation.hostel_id,
            room_id=allocation.room_id,
            complaint_type=complaint_data["complaint_type"],
            title=complaint_data["title"],
            description=complaint_data["description"],
            status="open",
            priority=complaint_data["priority"],
            reported_date=today,
            resolution_notes=None,
        )
        session.add(complaint)
        created_complaints.append(complaint)
    
    await session.flush()
    print(f"✓ Created {len(created_complaints)} complaint records")
    return created_complaints


async def seed_visitors(session, school_id, allocations, admin_user):
    """Seed Visitor Logs"""
    print("\n=== SEEDING VISITORS ===")
    
    # Check if visitor records already exist
    result = await session.execute(
        select(HostelVisitor).where(HostelVisitor.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Visitor records already exist. Skipping...")
        return []
    
    created_visitors = []
    
    if len(allocations) < 2:
        print("Not enough allocations for sample visitors. Skipping...")
        return []
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    visitor_data = [
        {
            "visitor_name": "Parent A",
            "relationship": "Parent",
            "visitor_phone": "+233501111111",
            "visit_date": today,
            "allocation_index": 0,
        },
        {
            "visitor_name": "Sibling B",
            "relationship": "Sister",
            "visitor_phone": "+233502222222",
            "visit_date": today,
            "allocation_index": 1,
        },
    ]
    
    for visitor in visitor_data:
        allocation = allocations[visitor["allocation_index"]]
        record = HostelVisitor(
            school_id=school_id,
            student_id=allocation.student_id,
            hostel_id=allocation.hostel_id,
            visitor_name=visitor["visitor_name"],
            relationship=visitor["relationship"],
            visitor_phone=visitor["visitor_phone"],
            visit_date=visitor["visit_date"],
            check_in_time=None,
            check_out_time=None,
            notes="Visitor logged",
        )
        session.add(record)
        created_visitors.append(record)
    
    await session.flush()
    print(f"✓ Created {len(created_visitors)} visitor records")
    return created_visitors


async def seed_hostel_data():
    """Main function to seed all hostel data"""
    print("\n" + "="*60)
    print("HOSTEL MODULE SEED DATA")
    print("="*60)
    
    await init_db()
    
    async with async_session() as session:
        # Get admin user
        admin_result = await session.execute(
            select(User).where(User.email == "admin@school.edu.gh")
        )
        admin_user = admin_result.scalar_one_or_none()
        
        if not admin_user:
            print("\n❌ Admin user not found.")
            print("Please run seed_data.py first to create initial users and school.")
            return
        
        # Get school
        school_result = await session.execute(
            select(School).where(School.id == admin_user.school_id)
        )
        school = school_result.scalar_one_or_none()
        
        if not school:
            print("\n❌ School not found.")
            return
        
        print(f"\n✓ Using school: {school.name} (ID: {school.id})")
        print(f"✓ Admin user: {admin_user.email}")
        
        # Initialize variables for summary
        hostels = []
        rooms = []
        students = []
        allocations = []
        fees = []
        attendance = []
        maintenance = []
        complaints = []
        visitors = []
        
        # Seed data in order
        hostels = await seed_hostels(session, school.id)
        
        if hostels:
            rooms = await seed_rooms(session, school.id, hostels)
            students = await seed_students(session, school.id, count=20)
            allocations = await seed_allocations(session, school.id, students, hostels, rooms)
            fees = await seed_fees(session, school.id, allocations, admin_user)
            attendance = await seed_attendance(session, school.id, allocations, admin_user)
            maintenance = await seed_maintenance(session, school.id, hostels, admin_user)
            complaints = await seed_complaints(session, school.id, allocations, admin_user)
            visitors = await seed_visitors(session, school.id, allocations, admin_user)
        
        await session.commit()
        
        print("\n" + "="*60)
        print("SEED DATA CREATION COMPLETE")
        print("="*60)
        print("\n📊 HOSTEL MODULE DATA SUMMARY")
        print(f"  • Hostels: {len(hostels)} created")
        print(f"  • Rooms: {len(rooms)} rooms created")
        print(f"  • Students: {len(students)} student records")
        print(f"  • Allocations: {len(allocations)} room assignments")
        print(f"  • Fees: {len(fees)} hostel fees")
        print(f"  • Attendance: {len(attendance)} attendance records")
        print(f"  • Maintenance: {len(maintenance)} maintenance issues")
        print(f"  • Complaints: {len(complaints)} complaint records")
        print(f"  • Visitors: {len(visitors)} visitor logs")
        
        print(f"\n💾 Total Items Created:")
        total_items = (
            len(hostels) + 
            len(rooms) + 
            len(students) + 
            len(allocations) + 
            len(fees) + 
            len(attendance) + 
            len(maintenance) + 
            len(complaints) + 
            len(visitors)
        )
        print(f"  • Total database records: {total_items}")
        
        print(f"\n✅ All hostel module seed data created successfully!")
        print(f"\n📝 Ready for testing and API validation!")


if __name__ == "__main__":
    asyncio.run(seed_hostel_data())
