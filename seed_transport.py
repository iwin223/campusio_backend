"""Seed transport data for School ERP System"""
import asyncio
import sys
from pathlib import Path
from datetime import date, datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_engine, async_session, init_db
from models.user import User, UserRole
from models.school import School
from models.student import Student
from models.transport import (
    Vehicle, VehicleCreate, Route, RouteCreate, StudentTransport, StudentTransportCreate,
    TransportFee, TransportFeeCreate, DriverStaff, DriverStaffCreate
)
from models.staff import Staff, StaffStatus, StaffType


async def seed_transport_data():
    """Seed transport-specific data"""
    async with async_session() as session:
        # Get the first school
        result = await session.execute(select(School).limit(1))
        school = result.scalar_one_or_none()
        
        if not school:
            print("No school found. Please run main seed_data.py first.")
            return
        
        # Get the first student for enrollment
        result = await session.execute(select(Student).where(Student.school_id == school.id).limit(1))
        student = result.scalar_one_or_none()
        
        if not student:
            print("No student found. Please run main seed_data.py first.")
            return
        
        print(f"Seeding transport data for school: {school.name}")
        
        # Create driver and conductor staff (non-teaching staff)
        driver_staff = Staff(
            school_id=school.id,
            staff_id="DRV001",
            first_name="Yaw",
            last_name="Boateng",
            email="driver1@school.edu.gh",
            phone="+233 20 666 6666",
            date_of_birth="1985-03-15",
            gender="male",
            staff_type=StaffType.NON_TEACHING,
            position="Transport Driver",
            date_joined="2023-06-01",
            status=StaffStatus.ACTIVE
        )
        session.add(driver_staff)
        
        conductor_staff = Staff(
            school_id=school.id,
            staff_id="CON001",
            first_name="Ade",
            last_name="Osei",
            email="conductor1@school.edu.gh",
            phone="+233 20 777 7777",
            date_of_birth="1990-08-22",
            gender="male",
            staff_type=StaffType.NON_TEACHING,
            position="Transport Conductor",
            date_joined="2023-06-15",
            status=StaffStatus.ACTIVE
        )
        session.add(conductor_staff)
        
        await session.flush()
        
        # Create vehicles
        vehicle1 = Vehicle(
            school_id=school.id,
            registration_number="GR-123-20",
            vehicle_type="bus",
            make="Hyundai",
            model="H350",
            year=2022,
            color="Yellow",
            seating_capacity=45,
            current_occupancy=0,
            driver_id=driver_staff.id,
            conductor_id=conductor_staff.id,
            insurance_expiry="2025-12-31",
            roadworthiness_expiry="2025-06-30",
            status="active",
            notes="Main school transport bus"
        )
        session.add(vehicle1)
        
        vehicle2 = Vehicle(
            school_id=school.id,
            registration_number="GR-124-20",
            vehicle_type="minibus",
            make="Toyota",
            model="Hiace",
            year=2021,
            color="White",
            seating_capacity=25,
            current_occupancy=0,
            driver_id=None,
            conductor_id=None,
            insurance_expiry="2025-12-31",
            roadworthiness_expiry="2025-06-30",
            status="active",
            notes="Secondary route transport"
        )
        session.add(vehicle2)
        
        await session.flush()
        
        # Create transport routes
        route1 = Route(
            school_id=school.id,
            route_name="Downtown Route",
            route_code="RT001",
            start_point="Labadi Beach",
            end_point="School Gate",
            distance_km=15.5,
            estimated_duration_minutes=45,
            vehicle_id=vehicle1.id,
            pickup_time="07:00",
            dropoff_time="08:30",
            pickup_days='["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]',
            intermediate_stops='["Osu Junction", "Cantonments Market", "Airport Roundabout"]',
            student_count=0,
            fee_amount=50.0,
            status="active"
        )
        session.add(route1)
        
        route2 = Route(
            school_id=school.id,
            route_name="East Legon Route",
            route_code="RT002",
            start_point="East Legon",
            end_point="School Gate",
            distance_km=12.0,
            estimated_duration_minutes=35,
            vehicle_id=vehicle2.id,
            pickup_time="07:15",
            dropoff_time="08:45",
            pickup_days='["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]',
            intermediate_stops='["Tetteh Quarshie Interchange", "Achimota School"]',
            student_count=0,
            fee_amount=45.0,
            status="active"
        )
        session.add(route2)
        
        await session.flush()
        
        # Create driver staff records
        driver_record = DriverStaff(
            school_id=school.id,
            staff_id=driver_staff.id,
            license_number="DL-2023-001",
            license_expiry="2026-12-31",
            role="driver",
            insurance_provider="National Insurance",
            insurance_expiry="2025-12-31",
            is_verified=True
        )
        session.add(driver_record)
        
        conductor_record = DriverStaff(
            school_id=school.id,
            staff_id=conductor_staff.id,
            license_number="CD-2023-001",
            license_expiry="2026-12-31",
            role="conductor",
            insurance_provider="National Insurance",
            insurance_expiry="2025-12-31",
            is_verified=True
        )
        session.add(conductor_record)
        
        await session.flush()
        
        # Create student transport enrollment
        student_transport = StudentTransport(
            school_id=school.id,
            student_id=student.id,
            route_id=route1.id,
            pickup_point="Labadi Beach (Main Stop)",
            dropoff_point="School Gate",
            emergency_contact="Ama Mensah",
            emergency_contact_phone="+233 20 555 5555",
            is_active=True,
            enrollment_date="2024-01-08"
        )
        session.add(student_transport)
        
        # Update route student count
        route1.student_count = 1
        vehicle1.current_occupancy += 1
        
        await session.flush()
        
        # Create transport fee
        transport_fee = TransportFee(
            school_id=school.id,
            student_id=student.id,
            route_id=route1.id,
            academic_term_id=None,
            fee_type="monthly",
            amount_due=50.0,
            amount_paid=0.0,
            discount=0.0,
            payment_date=None,
            payment_method=None,
            receipt_number=None,
            is_paid=False,
            due_date="2024-02-08",
            notes="January transport fee"
        )
        session.add(transport_fee)
        
        await session.commit()
        
        print("\n✓ Transport data seeded successfully!")
        print("\n=== Transport Summary ===")
        print("✓ 2 Staff created (Driver + Conductor)")
        print("✓ 2 Vehicles created (Bus + Minibus)")
        print("✓ 2 Transport Routes created")
        print("✓ 1 Student enrolled in transport")
        print("✓ 1 Transport fee record created")
        print("✓ Driver and Conductor records with licenses")


if __name__ == "__main__":
    asyncio.run(seed_transport_data())
