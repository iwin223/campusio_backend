"""Transport Management Models"""
from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class VehicleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class VehicleType(str, Enum):
    BUS = "bus"
    VAN = "van"
    MINIBUS = "minibus"
    SHUTTLE = "shuttle"


class RouteStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class TransportFeeType(str, Enum):
    MONTHLY = "monthly"
    TERM = "term"
    ANNUAL = "annual"
    PER_TRIP = "per_trip"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class Vehicle(SQLModel, table=True):
    """Vehicle/Bus model"""
    __tablename__ = "vehicles"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    registration_number: str = Field(unique=True, index=True)
    vehicle_type: VehicleType
    make: str
    model: str
    year: int
    color: Optional[str] = None
    seating_capacity: int
    current_occupancy: int = 0
    driver_id: Optional[str] = Field(default=None, index=True)
    conductor_id: Optional[str] = Field(default=None, index=True)
    
    # Maintenance tracking
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    insurance_expiry: Optional[str] = None
    roadworthiness_expiry: Optional[str] = None
    
    status: VehicleStatus = VehicleStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VehicleCreate(SQLModel):
    registration_number: str
    vehicle_type: VehicleType
    make: str
    model: str
    year: int
    color: Optional[str] = None
    seating_capacity: int
    driver_id: Optional[str] = None
    conductor_id: Optional[str] = None
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    insurance_expiry: Optional[str] = None
    roadworthiness_expiry: Optional[str] = None
    notes: Optional[str] = None


class VehicleUpdate(SQLModel):
    registration_number: Optional[str] = None
    vehicle_type: Optional[VehicleType] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    seating_capacity: Optional[int] = None
    driver_id: Optional[str] = None
    conductor_id: Optional[str] = None
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    insurance_expiry: Optional[str] = None
    roadworthiness_expiry: Optional[str] = None
    status: Optional[VehicleStatus] = None
    notes: Optional[str] = None


class Route(SQLModel, table=True):
    """Route model"""
    __tablename__ = "routes"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    route_name: str = Field(index=True)
    start_point: str
    end_point: str
    route_code: str = Field(unique=True, index=True)
    distance_km: float
    estimated_duration_minutes: int
    vehicle_id: Optional[str] = Field(default=None, index=True)
    
    # Schedule
    pickup_time: str  # HH:MM format
    dropoff_time: str  # HH:MM format
    pickup_days: str  # JSON string of days (e.g., "['Monday', 'Tuesday', ...]")
    
    # Route details
    intermediate_stops: Optional[str] = None  # JSON string of stop names
    student_count: int = 0
    fee_amount: float
    status: RouteStatus = RouteStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RouteCreate(SQLModel):
    route_name: str
    start_point: str
    end_point: str
    route_code: str
    distance_km: float
    estimated_duration_minutes: int
    vehicle_id: Optional[str] = None
    pickup_time: str
    dropoff_time: str
    pickup_days: str
    intermediate_stops: Optional[str] = None
    fee_amount: float
    notes: Optional[str] = None


class RouteUpdate(SQLModel):
    route_name: Optional[str] = None
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    route_code: Optional[str] = None
    distance_km: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    vehicle_id: Optional[str] = None
    pickup_time: Optional[str] = None
    dropoff_time: Optional[str] = None
    pickup_days: Optional[str] = None
    intermediate_stops: Optional[str] = None
    fee_amount: Optional[float] = None
    status: Optional[RouteStatus] = None
    notes: Optional[str] = None


class StudentTransport(SQLModel, table=True):
    """Student Transport Enrollment"""
    __tablename__ = "student_transport"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    route_id: str = Field(index=True)
    
    # Pickup and dropoff points
    pickup_point: Optional[str] = None
    dropoff_point: Optional[str] = None
    
    # Contact info
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    
    is_active: bool = True
    enrollment_date: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudentTransportCreate(SQLModel):
    student_id: str
    route_id: str
    pickup_point: Optional[str] = None
    dropoff_point: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    enrollment_date: str
    notes: Optional[str] = None


class StudentTransportUpdate(SQLModel):
    route_id: Optional[str] = None
    pickup_point: Optional[str] = None
    dropoff_point: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class TransportAttendance(SQLModel, table=True):
    """Daily transport attendance tracking"""
    __tablename__ = "transport_attendance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    route_id: str = Field(index=True)
    student_id: str = Field(index=True)
    vehicle_id: str = Field(index=True)
    
    attendance_date: str  # DATE format YYYY-MM-DD
    status: AttendanceStatus = AttendanceStatus.PRESENT
    
    # Trip information
    trip_type: str  # 'pickup' or 'dropoff'
    timestamp: Optional[str] = None  # ISO format datetime
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransportAttendanceCreate(SQLModel):
    route_id: str
    student_id: str
    vehicle_id: str
    attendance_date: str
    status: AttendanceStatus = AttendanceStatus.PRESENT
    trip_type: str
    timestamp: Optional[str] = None
    notes: Optional[str] = None


class TransportAttendanceBulk(SQLModel):
    """Bulk attendance submission"""
    attendance_records: List[TransportAttendanceCreate]


class TransportFee(SQLModel, table=True):
    """Transport fees for students"""
    __tablename__ = "transport_fees"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    route_id: str = Field(index=True)
    academic_term_id: Optional[str] = Field(default=None, index=True)
    
    fee_type: TransportFeeType
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
    
    # GL Integration (auto-posting)
    gl_journal_entry_id: Optional[str] = None
    gl_posted_date: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TransportFeeCreate(SQLModel):
    student_id: str
    route_id: str
    academic_term_id: Optional[str] = None
    fee_type: TransportFeeType
    amount_due: float
    amount_paid: float = 0.0
    discount: float = 0.0
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class TransportFeeUpdate(SQLModel):
    amount_due: Optional[float] = None
    amount_paid: Optional[float] = None
    discount: Optional[float] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    is_paid: Optional[bool] = None
    notes: Optional[str] = None


class VehicleMaintenance(SQLModel, table=True):
    """Vehicle maintenance record"""
    __tablename__ = "vehicle_maintenance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    vehicle_id: str = Field(index=True)
    
    maintenance_date: str
    maintenance_type: str  # e.g., "Oil Change", "Tire Replacement", "Inspection"
    description: str
    cost: float
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VehicleMaintenanceCreate(SQLModel):
    vehicle_id: str
    maintenance_date: str
    maintenance_type: str
    description: str
    cost: float
    notes: Optional[str] = None


class DriverStaff(SQLModel, table=True):
    """Driver and Conductor staff assignment"""
    __tablename__ = "driver_staff"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(unique=True, index=True)  # References Staff model
    
    license_number: str = Field(unique=True, index=True)
    license_expiry: str
    role: str  # 'driver' or 'conductor'
    
    # Insurance details
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    
    is_active: bool = True
    is_verified: bool = False
    verification_date: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DriverStaffCreate(SQLModel):
    staff_id: str
    license_number: str
    license_expiry: str
    role: str
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    notes: Optional[str] = None


class DriverStaffUpdate(SQLModel):
    license_number: Optional[str] = None
    license_expiry: Optional[str] = None
    role: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    verification_date: Optional[str] = None
    notes: Optional[str] = None
