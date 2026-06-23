"""Student Security Module Models"""
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String, ForeignKey
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class ArrivalStatus(str, Enum):
    PENDING = "pending"
    EN_ROUTE_BUS = "en_route_bus"
    EN_ROUTE_COLLECTOR = "en_route_collector"
    ARRIVED_UNCONFIRMED = "arrived_unconfirmed"
    SAFE_CONFIRMED = "safe_confirmed"


class QRTokenType(str, Enum):
    PARENT_PICKUP = "parent_pickup"
    TRANSPORT_DISPATCH = "transport_dispatch"
    COLLECTOR_SHARE = "collector_share"


class ScanResult(str, Enum):
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    EXPIRED = "expired"
    ALREADY_USED = "already_used"


class ArrivalEventType(str, Enum):
    DISPATCHED = "dispatched"
    EN_ROUTE_BUS = "en_route_bus"
    EN_ROUTE_COLLECTOR = "en_route_collector"
    ARRIVED = "arrived"
    PARENT_CONFIRMED = "parent_confirmed"


# ── Student Security Profile ──────────────────────────────────────────────────

class StudentSecurityProfile(SQLModel, table=True):
    __tablename__ = "student_security_profiles"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    student_id: str = Field(index=True)
    school_id: str = Field(index=True)

    ghana_post_address: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    neighbourhood: Optional[str] = None

    pickup_method: str = Field(default="parent")  # "parent" | "transport"
    transport_route_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String, ForeignKey("routes.id", ondelete="SET NULL"), index=True)
    )

    authorized_pickup_name: Optional[str] = None
    authorized_pickup_phone: Optional[str] = None
    authorized_pickup_relationship: Optional[str] = None

    # Current day state — reset each school day
    arrival_status: ArrivalStatus = Field(default=ArrivalStatus.PENDING)
    arrival_time: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudentSecurityProfileCreate(SQLModel):
    student_id: str
    school_id: str
    ghana_post_address: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    neighbourhood: Optional[str] = None
    pickup_method: str = "parent"
    transport_route_id: Optional[str] = None
    authorized_pickup_name: Optional[str] = None
    authorized_pickup_phone: Optional[str] = None
    authorized_pickup_relationship: Optional[str] = None


class StudentSecurityProfileUpdate(SQLModel):
    ghana_post_address: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    neighbourhood: Optional[str] = None
    pickup_method: Optional[str] = None
    transport_route_id: Optional[str] = None
    authorized_pickup_name: Optional[str] = None
    authorized_pickup_phone: Optional[str] = None
    authorized_pickup_relationship: Optional[str] = None
    arrival_status: Optional[ArrivalStatus] = None
    arrival_time: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


# ── Daily QR Token ────────────────────────────────────────────────────────────

class DailyQRToken(SQLModel, table=True):
    __tablename__ = "daily_qr_tokens"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    token: str = Field(index=True, unique=True)
    token_type: QRTokenType
    school_id: str = Field(index=True)

    student_id: Optional[str] = Field(default=None, index=True)
    route_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String, ForeignKey("routes.id", ondelete="SET NULL"), index=True)
    )

    # Embedded collector session token — dormant until a successful scan activates it
    collector_session_token: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True)

    issued_date: str  # YYYY-MM-DD
    expires_at: datetime

    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = None
    used_by_scan_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Security Scan Log ─────────────────────────────────────────────────────────

class SecurityScanLog(SQLModel, table=True):
    __tablename__ = "security_scan_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)

    token_scanned: str
    scanned_by_id: str = Field(index=True)  # FK → User (security_officer)

    result: ScanResult
    student_id: Optional[str] = Field(default=None, index=True)

    gate_lat: Optional[float] = None
    gate_lng: Optional[float] = None

    # If authorized, this links to the collector session created
    collector_session_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Arrival Event ─────────────────────────────────────────────────────────────

class ArrivalEvent(SQLModel, table=True):
    __tablename__ = "arrival_events"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)

    event_type: ArrivalEventType
    triggered_by_id: str  # FK → User
    notes: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Parent Note ───────────────────────────────────────────────────────────────

class ParentNote(SQLModel, table=True):
    __tablename__ = "parent_notes"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    author_id: str  # FK → User (parent)

    text: str
    is_confirmation: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParentNoteCreate(SQLModel):
    text: str
    is_confirmation: bool = False


# ── Live Bus Location ─────────────────────────────────────────────────────────

class LiveBusLocation(SQLModel, table=True):
    __tablename__ = "live_bus_locations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    route_id: str = Field(sa_column=Column(String, ForeignKey("routes.id", ondelete="CASCADE"), index=True))
    driver_id: str = Field(sa_column=Column(String, ForeignKey("driver_staff.id", ondelete="CASCADE"), index=True))

    lat: float
    lng: float
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None

    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class LiveBusLocationCreate(SQLModel):
    lat: float
    lng: float
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None


# ── Collector Tracking Session ────────────────────────────────────────────────

class CollectorTrackingSession(SQLModel, table=True):
    __tablename__ = "collector_tracking_sessions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_token: str = Field(index=True, unique=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)

    scan_log_id: str  # FK → SecurityScanLog
    collector_name: Optional[str] = None  # Captured at gate if provided

    gate_lat: Optional[float] = None
    gate_lng: Optional[float] = None

    is_active: bool = Field(default=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


# ── Collector Live Location ───────────────────────────────────────────────────

class CollectorLiveLocation(SQLModel, table=True):
    __tablename__ = "collector_live_locations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)  # FK → CollectorTrackingSession

    lat: float
    lng: float

    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class CollectorLocationCreate(SQLModel):
    lat: float
    lng: float
