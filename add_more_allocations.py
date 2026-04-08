#!/usr/bin/env python3
"""Add more allocations to enable complaints and visitors testing"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from sqlmodel import select
from database import init_db, async_session
from models.student import Student, Gender, StudentStatus
from models.school import School
from models.hostel import (
    Hostel, Room, StudentHostel, StudentHostelStatus, 
    HostelComplaint, HostelVisitor
)

async def add_more_allocations():
    """Add more allocations and create complaints/visitors"""
    print("\n" + "="*60)
    print("ADD MORE HOSTEL ALLOCATIONS")
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
        
        # Get existing allocations count
        alloc_count = await session.execute(
            select(StudentHostel).where(StudentHostel.school_id == school.id)
        )
        existing = len(alloc_count.scalars().all())
        
        print(f"\n✓ School: {school.name}")
        print(f"✓ Existing allocations: {existing}")
        
        if existing >= 3:
            print("✓ Already have 3+ allocations. Skipping creation...")
        else:
            # Get hostels and rooms
            hostels_result = await session.execute(
                select(Hostel).where(Hostel.school_id == school.id)
            )
            hostels = list(hostels_result.scalars().all())
            
            rooms_result = await session.execute(
                select(Room).where(Room.school_id == school.id)
            )
            rooms = list(rooms_result.scalars().all())
            
            if not hostels or not rooms:
                print("❌ No hostels or rooms found")
                return
            
            # Create 2 more students
            print("\n=== CREATING STUDENTS ===")
            new_students = []
            
            for i in range(1, 3):
                student = Student(
                    school_id=school.id,
                    student_id=f"STU-COMP-{i:04d}",
                    first_name=f"Complaint Test",
                    last_name=f"Student {i}",
                    gender=Gender.MALE if i % 2 == 0 else Gender.FEMALE,
                    date_of_birth="2008-01-15",
                    admission_date="2024-09-01",
                    status=StudentStatus.ACTIVE,
                )
                session.add(student)
                new_students.append(student)
            
            await session.flush()
            print(f"✓ Created {len(new_students)} student records")
            
            # Create allocations
            print("\n=== CREATING ALLOCATIONS ===")
            check_in_date = datetime(2026, 4, 1).strftime("%Y-%m-%d")
            new_allocations = []
            
            for i, student in enumerate(new_students):
                hostel = hostels[i % len(hostels)]
                rooms_in_hostel = [r for r in rooms if r.hostel_id == hostel.id]
                if not rooms_in_hostel:
                    continue
                
                room = rooms_in_hostel[(i + 2) % len(rooms_in_hostel)]
                
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
                new_allocations.append(allocation)
            
            await session.flush()
            print(f"✓ Created {len(new_allocations)} allocations")
            
            # Now get all allocations
            all_alloc_result = await session.execute(
                select(StudentHostel).where(StudentHostel.school_id == school.id)
            )
            all_allocations = list(all_alloc_result.scalars().all())
            
            # Create complaints
            print("\n=== CREATING COMPLAINTS ===")
            today = datetime.utcnow().strftime("%Y-%m-%d")
            created_complaints = []
            
            if len(all_allocations) >= 3:
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
                    allocation = all_allocations[complaint_data["allocation_index"]]
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
            
            if len(all_allocations) >= 2:
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
                    allocation = all_allocations[visitor["allocation_index"]]
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
        print("✅ Allocations, complaints, and visitors updated!")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(add_more_allocations())
