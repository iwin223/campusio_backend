"""Hostel Management Service - Business logic for hostel operations"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_, func, col
from datetime import datetime, date
from decimal import Decimal

from models.hostel import (
    Hostel, HostelCreate, HostelUpdate, HostelStatus,
    Room, RoomCreate, RoomUpdate, RoomStatus, RoomType,
    StudentHostel, StudentHostelCreate, StudentHostelUpdate, StudentHostelStatus,
    RoomAllocation, RoomAllocationCreate,
    HostelAttendance, HostelAttendanceCreate, CheckInStatus,
    HostelFee, HostelFeeCreate, HostelFeeUpdate, HostelFeeType,
    HostelMaintenance, HostelMaintenanceCreate,
    HostelVisitor, HostelVisitorCreate,
    HostelComplaint, HostelComplaintCreate, HostelComplaintUpdate
)
from models.student import Student
from models.user import User

logger = logging.getLogger(__name__)


class HostelServiceError(Exception):
    """Base exception for Hostel service errors"""
    pass


class HostelService:
    """Service for managing Hostel operations
    
    Handles:
    - Hostel management (CRUD)
    - Room management
    - Student accommodation
    - Room allocations
    - Hostel attendance tracking
    - Fee management
    - Maintenance tracking
    - Complaint handling
    - Visitor management
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with async database session
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
    
    # ==================== Hostel Operations ====================
    
    async def create_hostel(
        self,
        school_id: str,
        hostel_data: HostelCreate,
        created_by: str
    ) -> Hostel:
        """Create a new hostel facility
        
        Args:
            school_id: School identifier
            hostel_data: Hostel creation data
            created_by: User creating the hostel
            
        Returns:
            Created Hostel instance
            
        Raises:
            HostelServiceError: If hostel code already exists
        """
        # Check unique hostel code within school
        existing = await self._get_hostel_by_code(school_id, hostel_data.hostel_code)
        if existing:
            raise HostelServiceError(
                f"Hostel code '{hostel_data.hostel_code}' already exists for this school"
            )
        
        hostel = Hostel(
            school_id=school_id,
            **hostel_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.session.add(hostel)
        await self.session.commit()
        await self.session.refresh(hostel)
        
        logger.info(f"Hostel created: {hostel.id} for school {school_id}")
        return hostel
    
    async def get_hostel_by_id(self, school_id: str, hostel_id: str) -> Optional[Hostel]:
        """Get hostel by ID with school scoping"""
        result = await self.session.execute(
            select(Hostel).where(
                and_(Hostel.id == hostel_id, Hostel.school_id == school_id)
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_hostel_by_code(self, school_id: str, hostel_code: str) -> Optional[Hostel]:
        """Get hostel by code (internal check)"""
        result = await self.session.execute(
            select(Hostel).where(
                and_(Hostel.school_id == school_id, Hostel.hostel_code == hostel_code)
            )
        )
        return result.scalar_one_or_none()
    
    async def list_hostels(
        self,
        school_id: str,
        status: Optional[HostelStatus] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Hostel]:
        """List all hostels for school with optional filtering"""
        query = select(Hostel).where(Hostel.school_id == school_id)
        
        if status:
            query = query.where(Hostel.status == status)
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_hostel(
        self,
        school_id: str,
        hostel_id: str,
        update_data: HostelUpdate
    ) -> Hostel:
        """Update hostel information"""
        hostel = await self.get_hostel_by_id(school_id, hostel_id)
        if not hostel:
            raise HostelServiceError(f"Hostel {hostel_id} not found")
        
        data_dict = update_data.dict(exclude_unset=True)
        for key, value in data_dict.items():
            setattr(hostel, key, value)
        
        hostel.updated_at = datetime.utcnow()
        self.session.add(hostel)
        await self.session.commit()
        await self.session.refresh(hostel)
        
        logger.info(f"Hostel updated: {hostel_id}")
        return hostel
    
    # ==================== Room Operations ====================
    
    async def create_room(
        self,
        school_id: str,
        room_data: RoomCreate
    ) -> Room:
        """Create a new room in hostel
        
        Args:
            school_id: School identifier
            room_data: Room creation data
            
        Returns:
            Created Room instance
            
        Raises:
            HostelServiceError: If hostel not found or room number duplicate
        """
        # Verify hostel exists
        hostel = await self.get_hostel_by_id(school_id, room_data.hostel_id)
        if not hostel:
            raise HostelServiceError(f"Hostel {room_data.hostel_id} not found")
        
        # Check unique room number per hostel
        existing = await self._get_room_by_number(
            school_id, room_data.hostel_id, room_data.room_number
        )
        if existing:
            raise HostelServiceError(
                f"Room {room_data.room_number} already exists in hostel"
            )
        
        room = Room(
            school_id=school_id,
            **room_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(room)
        
        logger.info(f"Room created: {room.id} in hostel {room_data.hostel_id}")
        return room
    
    async def get_room_by_id(self, school_id: str, room_id: str) -> Optional[Room]:
        """Get room by ID with school scoping"""
        result = await self.session.execute(
            select(Room).where(and_(Room.id == room_id, Room.school_id == school_id))
        )
        return result.scalar_one_or_none()
    
    async def _get_room_by_number(
        self,
        school_id: str,
        hostel_id: str,
        room_number: str
    ) -> Optional[Room]:
        """Get room by number (internal check)"""
        result = await self.session.execute(
            select(Room).where(
                and_(
                    Room.school_id == school_id,
                    Room.hostel_id == hostel_id,
                    Room.room_number == room_number
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_rooms(
        self,
        school_id: str,
        hostel_id: Optional[str] = None,
        status: Optional[RoomStatus] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Room]:
        """List rooms with optional filtering"""
        query = select(Room).where(Room.school_id == school_id)
        
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        if status:
            query = query.where(Room.status == status)
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_room(
        self,
        school_id: str,
        room_id: str,
        update_data: RoomUpdate
    ) -> Room:
        """Update room information"""
        room = await self.get_room_by_id(school_id, room_id)
        if not room:
            raise HostelServiceError(f"Room {room_id} not found")
        
        data_dict = update_data.dict(exclude_unset=True)
        for key, value in data_dict.items():
            setattr(room, key, value)
        
        room.updated_at = datetime.utcnow()
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(room)
        
        logger.info(f"Room updated: {room_id}")
        return room
    
    async def get_room_occupancy(self, school_id: str, room_id: str) -> Dict[str, Any]:
        """Get detailed occupancy info for a room"""
        room = await self.get_room_by_id(school_id, room_id)
        if not room:
            raise HostelServiceError(f"Room {room_id} not found")
        
        occupancy_rate = (room.current_occupancy / room.capacity * 100) if room.capacity > 0 else 0
        
        return {
            "room_id": room.id,
            "room_number": room.room_number,
            "capacity": room.capacity,
            "current_occupancy": room.current_occupancy,
            "available_beds": room.capacity - room.current_occupancy,
            "occupancy_rate": round(occupancy_rate, 2),
            "status": room.status.value
        }
    
    # ==================== Student Accommodation ====================
    
    async def allocate_student(
        self,
        school_id: str,
        accommodation_data: StudentHostelCreate
    ) -> StudentHostel:
        """Allocate student to hostel accommodation
        
        Args:
            school_id: School identifier
            accommodation_data: Accommodation data
            
        Returns:
            Created StudentHostel
            
        Raises:
            HostelServiceError: If student/hostel not found or student already allocated
        """
        # Verify student exists
        result = await self.session.execute(
            select(Student).where(
                and_(
                    Student.school_id == school_id,
                    Student.student_id == accommodation_data.student_id
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise HostelServiceError(f"Student {accommodation_data.student_id} not found")
        
        # Check student not already allocated
        existing = await self._get_student_accommodation(
            school_id, accommodation_data.student_id
        )
        if existing:
            raise HostelServiceError(
                f"Student {accommodation_data.student_id} already has hostel allocation"
            )
        
        # Verify hostel exists
        hostel = await self.get_hostel_by_id(school_id, accommodation_data.hostel_id)
        if not hostel:
            raise HostelServiceError(f"Hostel {accommodation_data.hostel_id} not found")
        
        accommodation = StudentHostel(
            school_id=school_id,
            **accommodation_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.session.add(accommodation)
        await self.session.commit()
        await self.session.refresh(accommodation)
        
        logger.info(f"Student {accommodation_data.student_id} allocated to hostel")
        return accommodation
    
    async def _get_student_accommodation(
        self,
        school_id: str,
        student_id: str
    ) -> Optional[StudentHostel]:
        """Get student's current accommodation (internal check)"""
        result = await self.session.execute(
            select(StudentHostel).where(
                and_(
                    StudentHostel.school_id == school_id,
                    StudentHostel.student_id == student_id,
                    StudentHostel.status == StudentHostelStatus.ACTIVE
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_student_accommodation(
        self,
        school_id: str,
        student_id: str
    ) -> Optional[StudentHostel]:
        """Get student's accommodation details"""
        result = await self.session.execute(
            select(StudentHostel).where(
                and_(
                    StudentHostel.school_id == school_id,
                    StudentHostel.student_id == student_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def release_student(
        self,
        school_id: str,
        accommodation_id: str
    ) -> StudentHostel:
        """Release student from hostel accommodation"""
        result = await self.session.execute(
            select(StudentHostel).where(
                and_(
                    StudentHostel.id == accommodation_id,
                    StudentHostel.school_id == school_id
                )
            )
        )
        accommodation = result.scalar_one_or_none()
        if not accommodation:
            raise HostelServiceError(f"Accommodation {accommodation_id} not found")
        
        accommodation.status = StudentHostelStatus.RELEASED
        accommodation.check_out_date = datetime.utcnow().isoformat().split('T')[0]
        accommodation.updated_at = datetime.utcnow()
        
        self.session.add(accommodation)
        await self.session.commit()
        await self.session.refresh(accommodation)
        
        logger.info(f"Student released from accommodation: {accommodation_id}")
        return accommodation
    
    # ==================== Room Allocation ====================
    
    async def allocate_room(
        self,
        school_id: str,
        allocation_data: RoomAllocationCreate
    ) -> RoomAllocation:
        """Allocate room to student
        
        Checks:
        - Room exists and has capacity
        - Student exists
        - No duplicate allocation for same term
        """
        # Verify student exists
        result = await self.session.execute(
            select(Student).where(Student.student_id == allocation_data.student_id)
        )
        if not result.scalar_one_or_none():
            raise HostelServiceError(f"Student {allocation_data.student_id} not found")
        
        # Check room capacity
        room = await self.get_room_by_id(school_id, allocation_data.room_id)
        if not room:
            raise HostelServiceError(f"Room {allocation_data.room_id} not found")
        
        if room.current_occupancy >= room.capacity:
            raise HostelServiceError(f"Room {allocation_data.room_id} is at full capacity")
        
        allocation = RoomAllocation(
            school_id=school_id,
            **allocation_data.dict(),
            created_at=datetime.utcnow()
        )
        self.session.add(allocation)
        
        # Update room occupancy
        room.current_occupancy += 1
        self.session.add(room)
        
        await self.session.commit()
        await self.session.refresh(allocation)
        
        logger.info(f"Room allocated to student: {allocation_data.student_id}")
        return allocation
    
    async def deallocate_room(
        self,
        school_id: str,
        allocation_id: str
    ) -> RoomAllocation:
        """Remove student from room allocation"""
        result = await self.session.execute(
            select(RoomAllocation).where(
                and_(
                    RoomAllocation.id == allocation_id,
                    RoomAllocation.school_id == school_id
                )
            )
        )
        allocation = result.scalar_one_or_none()
        if not allocation:
            raise HostelServiceError(f"Allocation {allocation_id} not found")
        
        # Update room occupancy
        room = await self.get_room_by_id(school_id, allocation.room_id)
        if room and room.current_occupancy > 0:
            room.current_occupancy -= 1
            self.session.add(room)
        
        allocation.deallocation_date = datetime.utcnow().isoformat().split('T')[0]
        self.session.add(allocation)
        
        await self.session.commit()
        await self.session.refresh(allocation)
        
        logger.info(f"Room deallocated: {allocation_id}")
        return allocation
    
    # ==================== Attendance Tracking ====================
    
    async def mark_attendance(
        self,
        school_id: str,
        attendance_data: HostelAttendanceCreate
    ) -> HostelAttendance:
        """Record hostel check-in/check-out"""
        attendance = HostelAttendance(
            school_id=school_id,
            **attendance_data.dict(),
            created_at=datetime.utcnow()
        )
        self.session.add(attendance)
        await self.session.commit()
        await self.session.refresh(attendance)
        
        logger.info(f"Attendance marked for student {attendance_data.student_id}")
        return attendance
    
    async def get_hostel_attendance_summary(
        self,
        school_id: str,
        hostel_id: str,
        attendance_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get attendance summary for hostel"""
        query = select(HostelAttendance).where(
            and_(
                HostelAttendance.school_id == school_id,
                HostelAttendance.hostel_id == hostel_id
            )
        )
        
        if attendance_date:
            query = query.where(HostelAttendance.attendance_date == attendance_date)
        
        result = await self.session.execute(query)
        records = result.scalars().all()
        
        checked_in = sum(1 for r in records if r.status == CheckInStatus.CHECKED_IN)
        checked_out = sum(1 for r in records if r.status == CheckInStatus.CHECKED_OUT)
        on_leave = sum(1 for r in records if r.status == CheckInStatus.ON_LEAVE)
        
        return {
            "checked_in": checked_in,
            "checked_out": checked_out,
            "on_leave": on_leave,
            "total": len(records)
        }
    
    # ==================== Fee Management ====================
    
    async def create_hostel_fee(
        self,
        school_id: str,
        fee_data: HostelFeeCreate
    ) -> HostelFee:
        """Create hostel accommodation fee"""
        fee = HostelFee(
            school_id=school_id,
            **fee_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.session.add(fee)
        await self.session.commit()
        await self.session.refresh(fee)
        
        logger.info(f"Hostel fee created for student {fee_data.student_id}")
        return fee
    
    async def update_fee_payment(
        self,
        school_id: str,
        fee_id: str,
        update_data: HostelFeeUpdate
    ) -> HostelFee:
        """Update hostel fee payment"""
        result = await self.session.execute(
            select(HostelFee).where(
                and_(HostelFee.id == fee_id, HostelFee.school_id == school_id)
            )
        )
        fee = result.scalar_one_or_none()
        if not fee:
            raise HostelServiceError(f"Fee {fee_id} not found")
        
        data_dict = update_data.dict(exclude_unset=True)
        
        # Auto-calculate is_paid
        if "amount_paid" in data_dict or "amount_due" in data_dict:
            amount_due = data_dict.get("amount_due", fee.amount_due)
            amount_paid = data_dict.get("amount_paid", fee.amount_paid)
            discount = data_dict.get("discount", fee.discount)
            
            total_covered = amount_paid + discount
            data_dict["is_paid"] = total_covered >= amount_due
        
        for key, value in data_dict.items():
            setattr(fee, key, value)
        
        fee.updated_at = datetime.utcnow()
        self.session.add(fee)
        await self.session.commit()
        await self.session.refresh(fee)
        
        logger.info(f"Fee updated: {fee_id}")
        return fee
    
    async def get_fee_collection_summary(
        self,
        school_id: str,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get fee collection summary"""
        query = select(HostelFee).where(HostelFee.school_id == school_id)
        
        if hostel_id:
            query = query.where(HostelFee.hostel_id == hostel_id)
        
        result = await self.session.execute(query)
        fees = result.scalars().all()
        
        total_due = sum(float(f.amount_due) for f in fees)
        total_paid = sum(float(f.amount_paid) for f in fees)
        total_discount = sum(float(f.discount) for f in fees)
        total_outstanding = total_due - total_paid - total_discount
        
        return {
            "total_due": round(total_due, 2),
            "total_paid": round(total_paid, 2),
            "total_discount": round(total_discount, 2),
            "total_outstanding": round(total_outstanding, 2),
            "collection_rate": round((total_paid / total_due * 100) if total_due > 0 else 0, 2),
            "total_students": len(set(f.student_id for f in fees)),
            "fees_paid": sum(1 for f in fees if f.is_paid),
            "fees_unpaid": sum(1 for f in fees if not f.is_paid)
        }
    
    # ==================== Maintenance Management ====================
    
    async def create_maintenance_record(
        self,
        school_id: str,
        maintenance_data: HostelMaintenanceCreate
    ) -> HostelMaintenance:
        """Create hostel maintenance record"""
        maintenance = HostelMaintenance(
            school_id=school_id,
            **maintenance_data.dict(),
            created_at=datetime.utcnow()
        )
        self.session.add(maintenance)
        await self.session.commit()
        await self.session.refresh(maintenance)
        
        logger.info(f"Maintenance record created: {maintenance.id}")
        return maintenance
    
    async def get_maintenance_backlog(
        self,
        school_id: str,
        hostel_id: Optional[str] = None
    ) -> List[HostelMaintenance]:
        """Get pending/open maintenance issues"""
        query = select(HostelMaintenance).where(
            and_(
                HostelMaintenance.school_id == school_id,
                HostelMaintenance.status.in_(["open", "in_progress"])
            )
        )
        
        if hostel_id:
            query = query.where(HostelMaintenance.hostel_id == hostel_id)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    # ==================== Complaint Management ====================
    
    async def create_complaint(
        self,
        school_id: str,
        complaint_data: HostelComplaintCreate
    ) -> HostelComplaint:
        """Create hostel complaint"""
        complaint = HostelComplaint(
            school_id=school_id,
            **complaint_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.session.add(complaint)
        await self.session.commit()
        await self.session.refresh(complaint)
        
        logger.info(f"Complaint created: {complaint.id}")
        return complaint
    
    async def update_complaint_status(
        self,
        school_id: str,
        complaint_id: str,
        status: str,
        resolution_notes: Optional[str] = None
    ) -> HostelComplaint:
        """Update complaint resolution status"""
        result = await self.session.execute(
            select(HostelComplaint).where(
                and_(
                    HostelComplaint.id == complaint_id,
                    HostelComplaint.school_id == school_id
                )
            )
        )
        complaint = result.scalar_one_or_none()
        if not complaint:
            raise HostelServiceError(f"Complaint {complaint_id} not found")
        
        complaint.status = status
        if resolution_notes:
            complaint.resolution_notes = resolution_notes
        if status == "resolved":
            complaint.resolved_date = datetime.utcnow().isoformat().split('T')[0]
        
        complaint.updated_at = datetime.utcnow()
        self.session.add(complaint)
        await self.session.commit()
        await self.session.refresh(complaint)
        
        logger.info(f"Complaint updated: {complaint_id}")
        return complaint
    
    async def get_complaint_summary(
        self,
        school_id: str,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get complaint statistics for hostel"""
        query = select(HostelComplaint).where(HostelComplaint.school_id == school_id)
        
        if hostel_id:
            query = query.where(HostelComplaint.hostel_id == hostel_id)
        
        result = await self.session.execute(query)
        complaints = result.scalars().all()
        
        return {
            "total": len(complaints),
            "open": sum(1 for c in complaints if c.status == "open"),
            "pending": sum(1 for c in complaints if c.status == "pending"),
            "resolved": sum(1 for c in complaints if c.status == "resolved"),
            "urgent": sum(1 for c in complaints if c.priority == "urgent"),
            "high": sum(1 for c in complaints if c.priority == "high")
        }
    
    # ==================== Visitor Management ====================
    
    async def register_visitor(
        self,
        school_id: str,
        visitor_data: HostelVisitorCreate
    ) -> HostelVisitor:
        """Register hostel visitor"""
        visitor = HostelVisitor(
            school_id=school_id,
            **visitor_data.dict(),
            created_at=datetime.utcnow()
        )
        self.session.add(visitor)
        await self.session.commit()
        await self.session.refresh(visitor)
        
        logger.info(f"Visitor registered: {visitor.id}")
        return visitor
    
    # ==================== Reporting ====================
    
    async def get_hostel_occupancy_report(
        self,
        school_id: str,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive occupancy report"""
        query_hostels = select(Hostel).where(Hostel.school_id == school_id)
        if hostel_id:
            query_hostels = query_hostels.where(Hostel.id == hostel_id)
        
        result = await self.session.execute(query_hostels)
        hostels = result.scalars().all()
        
        report = {
            "total_hostels": len(hostels),
            "total_capacity": 0,
            "total_occupied": 0,
            "hostels": []
        }
        
        for hostel in hostels:
            # Get rooms in hostel
            room_result = await self.session.execute(
                select(Room).where(Room.hostel_id == hostel.id)
            )
            rooms = room_result.scalars().all()
            
            total_capacity = sum(r.capacity for r in rooms)
            total_occupied = sum(r.current_occupancy for r in rooms)
            occupancy_rate = (total_occupied / total_capacity * 100) if total_capacity > 0 else 0
            
            report["total_capacity"] += total_capacity
            report["total_occupied"] += total_occupied
            
            report["hostels"].append({
                "hostel_id": hostel.id,
                "hostel_name": hostel.hostel_name,
                "hostel_type": hostel.hostel_type,
                "total_rooms": len(rooms),
                "capacity": total_capacity,
                "occupied": total_occupied,
                "available": total_capacity - total_occupied,
                "occupancy_rate": round(occupancy_rate, 2),
                "status": hostel.status.value
            })
        
        # Add overall occupancy rate
        overall_rate = (report["total_occupied"] / report["total_capacity"] * 100) \
            if report["total_capacity"] > 0 else 0
        report["overall_occupancy_rate"] = round(overall_rate, 2)
        
        return report
    
    async def get_student_hostel_history(
        self,
        school_id: str,
        student_id: str
    ) -> Dict[str, Any]:
        """Get complete hostel history for a student"""
        # Get accommodation records
        result = await self.session.execute(
            select(StudentHostel).where(
                and_(
                    StudentHostel.school_id == school_id,
                    StudentHostel.student_id == student_id
                )
            )
        )
        accommodations = result.scalars().all()
        
        # Get room allocations
        result = await self.session.execute(
            select(RoomAllocation).where(
                and_(
                    RoomAllocation.school_id == school_id,
                    RoomAllocation.student_id == student_id
                )
            )
        )
        allocations = result.scalars().all()
        
        # Get fees
        result = await self.session.execute(
            select(HostelFee).where(
                and_(
                    HostelFee.school_id == school_id,
                    HostelFee.student_id == student_id
                )
            )
        )
        fees = result.scalars().all()
        
        total_fees = sum(float(f.amount_due) for f in fees)
        total_paid = sum(float(f.amount_paid) for f in fees)
        
        return {
            "student_id": student_id,
            "accommodations": len(accommodations),
            "current_status": accommodations[-1].status.value if accommodations else None,
            "room_allocations": len(allocations),
            "total_fees": round(total_fees, 2),
            "total_paid": round(total_paid, 2),
            "outstanding": round(total_fees - total_paid, 2),
            "payment_status": "paid" if total_paid >= total_fees else "outstanding"
        }
