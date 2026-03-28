"""Hostel Management Models"""
from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class HostelStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FULL = "full"
    MAINTENANCE = "maintenance"


class RoomType(str, Enum):
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    DORMITORY = "dormitory"


class RoomStatus(str, Enum):
    VACANT = "vacant"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


class StudentHostelStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    GRADUATED = "graduated"
    TRANSFERRED = "transferred"


class HostelFeeType(str, Enum):
    MONTHLY = "monthly"
    TERM = "term"
    ANNUAL = "annual"
    SEMESTER = "semester"


class CheckInStatus(str, Enum):
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    ON_LEAVE = "on_leave"


class Hostel(SQLModel, table=True):
    """Hostel/Dormitory model"""
    __tablename__ = "hostels"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    hostel_name: str = Field(index=True)
    hostel_code: str = Field(unique=True, index=True)
    hostel_type: str  # Boys, Girls, Mixed
    capacity: int
    current_occupancy: int = 0
    
    # Contact and location
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    warden_email: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    
    # Facilities
    has_wifi: bool = False
    has_laundry: bool = False
    has_kitchen: bool = False
    has_common_room: bool = False
    has_security: bool = False
    
    status: HostelStatus = HostelStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HostelCreate(SQLModel):
    hostel_name: str
    hostel_code: str
    hostel_type: str
    capacity: int
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    warden_email: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    has_wifi: bool = False
    has_laundry: bool = False
    has_kitchen: bool = False
    has_common_room: bool = False
    has_security: bool = False
    notes: Optional[str] = None


class HostelUpdate(SQLModel):
    hostel_name: Optional[str] = None
    hostel_code: Optional[str] = None
    hostel_type: Optional[str] = None
    capacity: Optional[int] = None
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    warden_email: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    has_wifi: Optional[bool] = None
    has_laundry: Optional[bool] = None
    has_kitchen: Optional[bool] = None
    has_common_room: Optional[bool] = None
    has_security: Optional[bool] = None
    status: Optional[HostelStatus] = None
    notes: Optional[str] = None


class Room(SQLModel, table=True):
    """Room model in a hostel"""
    __tablename__ = "rooms"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    room_number: str = Field(index=True)
    room_type: RoomType
    capacity: int
    current_occupancy: int = 0
    
    # Room details
    floor: int = 1
    has_bathroom: bool = True
    has_ac: bool = False
    has_heater: bool = False
    has_desk: bool = True
    has_bed: bool = True
    
    status: RoomStatus = RoomStatus.VACANT
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RoomCreate(SQLModel):
    hostel_id: str
    room_number: str
    room_type: RoomType
    capacity: int
    floor: int = 1
    has_bathroom: bool = True
    has_ac: bool = False
    has_heater: bool = False
    has_desk: bool = True
    has_bed: bool = True
    notes: Optional[str] = None


class RoomUpdate(SQLModel):
    room_number: Optional[str] = None
    room_type: Optional[RoomType] = None
    capacity: Optional[int] = None
    floor: Optional[int] = None
    has_bathroom: Optional[bool] = None
    has_ac: Optional[bool] = None
    has_heater: Optional[bool] = None
    has_desk: Optional[bool] = None
    has_bed: Optional[bool] = None
    status: Optional[RoomStatus] = None
    notes: Optional[str] = None


class StudentHostel(SQLModel, table=True):
    """Student Hostel Accommodation"""
    __tablename__ = "student_hostels"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(unique=True, index=True)
    hostel_id: str = Field(index=True)
    room_id: Optional[str] = Field(default=None, index=True)
    
    # Enrollment details
    check_in_date: str
    check_out_date: Optional[str] = None
    academic_year: str
    
    # Contact information
    parent_contact: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    
    status: StudentHostelStatus = StudentHostelStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudentHostelCreate(SQLModel):
    student_id: str
    hostel_id: str
    room_id: Optional[str] = None
    check_in_date: str
    academic_year: str
    parent_contact: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None


class StudentHostelUpdate(SQLModel):
    room_id: Optional[str] = None
    check_out_date: Optional[str] = None
    parent_contact: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    status: Optional[StudentHostelStatus] = None
    notes: Optional[str] = None


class RoomAllocation(SQLModel, table=True):
    """Track room allocations to students"""
    __tablename__ = "room_allocations"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    room_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    
    allocation_date: str
    deallocation_date: Optional[str] = None
    bed_number: Optional[str] = None
    academic_year: str
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoomAllocationCreate(SQLModel):
    student_id: str
    room_id: str
    hostel_id: str
    allocation_date: str
    academic_year: str
    bed_number: Optional[str] = None
    notes: Optional[str] = None


class HostelAttendance(SQLModel, table=True):
    """Hostel check-in/check-out attendance"""
    __tablename__ = "hostel_attendance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    
    attendance_date: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    status: CheckInStatus = CheckInStatus.CHECKED_IN
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HostelAttendanceCreate(SQLModel):
    student_id: str
    hostel_id: str
    attendance_date: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    status: CheckInStatus = CheckInStatus.CHECKED_IN
    notes: Optional[str] = None


class HostelFee(SQLModel, table=True):
    """Hostel accommodation fees"""
    __tablename__ = "hostel_fees"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    academic_term_id: Optional[str] = Field(default=None, index=True)
    
    fee_type: HostelFeeType
    amount_due: float
    amount_paid: float = 0.0
    discount: float = 0.0
    
    # Payment details
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    
    # Status tracking
    is_paid: bool = False
    due_date: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HostelFeeCreate(SQLModel):
    student_id: str
    hostel_id: str
    academic_term_id: Optional[str] = None
    fee_type: HostelFeeType
    amount_due: float
    discount: float = 0.0
    due_date: Optional[str] = None
    notes: Optional[str] = None


class HostelFeeUpdate(SQLModel):
    amount_due: Optional[float] = None
    amount_paid: Optional[float] = None
    discount: Optional[float] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    is_paid: Optional[bool] = None
    notes: Optional[str] = None


class HostelMaintenance(SQLModel, table=True):
    """Hostel/Room maintenance record"""
    __tablename__ = "hostel_maintenance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    room_id: Optional[str] = Field(default=None, index=True)
    
    maintenance_date: str
    maintenance_type: str  # e.g., "Cleaning", "Repair", "Inspection"
    description: str
    cost: float = 0.0
    status: str = "completed"  # pending, completed, cancelled
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HostelMaintenanceCreate(SQLModel):
    hostel_id: str
    room_id: Optional[str] = None
    maintenance_date: str
    maintenance_type: str
    description: str
    cost: float = 0.0
    status: str = "completed"
    notes: Optional[str] = None


class HostelVisitor(SQLModel, table=True):
    """Record of hostel visitors"""
    __tablename__ = "hostel_visitors"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    student_id: str = Field(index=True)
    
    visitor_name: str
    visitor_phone: Optional[str] = None
    relationship: str  # Parent, Guardian, Friend, etc.
    
    visit_date: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HostelVisitorCreate(SQLModel):
    student_id: str
    hostel_id: str
    visitor_name: str
    visitor_phone: Optional[str] = None
    relationship: str
    visit_date: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    notes: Optional[str] = None


class HostelComplaint(SQLModel, table=True):
    """Hostel-related complaints/issues"""
    __tablename__ = "hostel_complaints"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    hostel_id: str = Field(index=True)
    student_id: str = Field(index=True)
    room_id: Optional[str] = Field(default=None, index=True)
    
    complaint_type: str  # Maintenance, Noise, Cleanliness, etc.
    title: str
    description: str
    
    status: str = "open"  # open, resolved, pending
    priority: str = "normal"  # low, normal, high, urgent
    
    reported_date: str
    resolved_date: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HostelComplaintCreate(SQLModel):
    hostel_id: str
    student_id: str
    room_id: Optional[str] = None
    complaint_type: str
    title: str
    description: str
    priority: str = "normal"
    reported_date: str
    resolution_notes: Optional[str] = None


class HostelComplaintUpdate(SQLModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_date: Optional[str] = None
