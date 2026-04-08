#!/usr/bin/env python3
"""
Quick script to directly seed allocations and dependent data
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date
from sqlmodel import select
from database import init_db, async_session
from models.student import Student
from models.hostel import (
    Hostel, Room, StudentHostel, StudentHostelStatus, HostelFee, HostelAttendance, 
    HostelComplaint, HostelVisitor, HostelFeeType, CheckInStatus
)
from models.user import User
from models.school import School

async def seed_allocations_and_more():
    """Directly create allocations and dependent data"""
    print("\n" + "="*60)
    print("HOSTEL ALLOCATIONS - DIRECT SEED")
    print("="*60)
    
    await init_db()
    
    async with async_session() as session:
        # Get school
        school_result = await session.execute(
            select(School).limit(1)
        )
        school = school_result.scalar_one_or_none()
        
        if not school:
            print("❌ No school found")
            return
        
        print(f"\n✓ Using school: {school.name}")
        
        # Get hostels
        hostels_result = await session.execute(
            select(Hostel).where(Hostel.school_id == school.id)
        )
        hostels = hostels_result.scalars().all()
        
        if not hostels:
            print("❌ No hostels found. Run seed_hostel_data.py first")
            return
        
        print(f"✓ Found {len(hostels)} hostels")
        
        # Get rooms
        rooms_result = await session.execute(
            select(Room).where(Room.school_id == school.id)
        )
        rooms = rooms_result.scalars().all()
        
        if not rooms:
            print("❌ No rooms found")
            return
        
        print(f"✓ Found {len(rooms)} rooms")
        
        # Get students
        students_result = await session.execute(
            select(Student).where(Student.school_id == school.id).limit(20)
        )
        students = list(students_result.scalars().all())
        
        # If not enough students, create some
        if len(students) < 10:
            print(f"\n✓ Found {len(students)} students, creating {10 - len(students)} more for testing")
            from models.student import Gender, StudentStatus
            
            for i in range(len(students) + 1, 11):
                student = Student(
                    school_id=school.id,
                    student_id=f"STU-ALLOC-{i:04d}",
                    first_name=f"Allocation Test",
                    last_name=f"Student {i}",
                    gender=Gender.MALE if i % 2 == 0 else Gender.FEMALE,
                    date_of_birth="2008-01-15",
                    admission_date="2024-09-01",
                    status=StudentStatus.ACTIVE,
                )
                session.add(student)
                students.append(student)
            
            await session.flush()
            print(f"✓ Created {10 - len(students) + (10 if len(students) < 10 else 0)} additional students")
        
        if not students:
            print("❌ No students found or could not create students")
            return
        
        print(f"✓ Total students for allocation: {len(students)}")
        
        # Check if allocations already exist
        alloc_result = await session.execute(
            select(StudentHostel).where(StudentHostel.school_id == school.id).limit(1)
        )
        if alloc_result.scalar_one_or_none():
            print("Allocations already exist. Skipping...")
            return
        
        # Create allocations
        print("\n=== CREATING ALLOCATIONS ===")
        created_allocations = []
        check_in_date = datetime(2026, 4, 1).strftime("%Y-%m-%d")
        
        for i, student in enumerate(students):
            hostel = hostels[i % len(hostels)]
            rooms_in_hostel = [r for r in rooms if r.hostel_id == hostel.id]
            if not rooms_in_hostel:
                continue
            
            room = rooms_in_hostel[i % len(rooms_in_hostel)]
            
            allocation = StudentHostel(
                school_id=school.id,
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
        print(f"✓ Created {len(created_allocations)} allocations")
        
        # Create fees
        print("\n=== CREATING HOSTEL FEES ===")
        due_date = datetime(2026, 5, 1).strftime("%Y-%m-%d")
        created_fees = []
        
        for allocation in created_allocations:
            fee = HostelFee(
                school_id=school.id,
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
        
        # Create attendance
        print("\n=== CREATING ATTENDANCE ===")
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        created_attendance = []
        
        for allocation in created_allocations:
            attendance = HostelAttendance(
                school_id=school.id,
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
        
        # Create complaints
        print("\n=== CREATING COMPLAINTS ===")
        created_complaints = []
        
        if len(created_allocations) >= 3:
            complaints_data = [
                {
                    "complaint_type": "Noise",
                    "title": "Noise from adjacent room",
                    "description": "Students making excessive noise at night",
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
                allocation = created_allocations[complaint_data["allocation_index"]]
                complaint = HostelComplaint(
                    school_id=school.id,
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
            print(f"✓ Created {len(created_complaints)} complaints")
        
        # Create visitors
        print("\n=== CREATING VISITORS ===")
        created_visitors = []
        
        if len(created_allocations) >= 2:
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
                allocation = created_allocations[visitor["allocation_index"]]
                record = HostelVisitor(
                    school_id=school.id,
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
            print(f"✓ Created {len(created_visitors)} visitor logs")
        
        # Commit all changes
        await session.commit()
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"✓ Allocations: {len(created_allocations)}")
        print(f"✓ Fees: {len(created_fees)}")
        print(f"✓ Attendance: {len(created_attendance)}")
        print(f"✓ Complaints: {len(created_complaints)}")
        print(f"✓ Visitors: {len(created_visitors)}")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(seed_allocations_and_more())
