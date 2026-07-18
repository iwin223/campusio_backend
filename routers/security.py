"""Student Security Module Router"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date, timedelta
from typing import List, Optional
import uuid
import logging

from models.security import (
    StudentSecurityProfile, StudentSecurityProfileCreate, StudentSecurityProfileUpdate,
    DailyQRToken, QRTokenType,
    SecurityScanLog, ScanResult,
    ArrivalEvent, ArrivalEventType,
    ParentNote, ParentNoteCreate,
    LiveBusLocation, LiveBusLocationCreate,
    CollectorTrackingSession,
    CollectorLiveLocation, CollectorLocationCreate,
    ArrivalStatus,
)
from models.student import Student
from models.classroom import Class
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from models.school import School
from services.email_service import email_service
from routers.parent import get_parent_children_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Student Security"])


# ── Request bodies (all mutating endpoints take JSON bodies, never bare
#    scalar params — FastAPI would silently read those from the query string) ──

from sqlmodel import SQLModel


class SchoolScopedRequest(SQLModel):
    school_id: str


class VerifyQRRequest(SQLModel):
    token: str
    gate_lat: Optional[float] = None
    gate_lng: Optional[float] = None


class UpdateArrivalStatusRequest(SQLModel):
    arrival_status: ArrivalStatus

ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)
OFFICER_ROLES = (UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SECURITY_OFFICER)


# ── Helpers ───────────────────────────────────────────────────────────────────

def today_str() -> str:
    return date.today().isoformat()


def token_expires_at() -> datetime:
    """Tokens expire at midnight of the current day"""
    tomorrow = date.today() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)


async def get_or_create_qr_token(db: AsyncSession, student_id: str):
    """Get (or lazily create) today's parent-pickup QR token for a student.
    Returns (token, student), or (None, None) if the student doesn't exist."""
    student_result = await db.exec(select(Student).where(Student.id == student_id))
    student = student_result.first()
    if not student:
        return None, None

    today = today_str()
    result = await db.exec(
        select(DailyQRToken).where(
            and_(
                DailyQRToken.student_id == student_id,
                DailyQRToken.issued_date == today,
                DailyQRToken.token_type == QRTokenType.PARENT_PICKUP,
            )
        )
    )
    token = result.first()
    if not token:
        token = DailyQRToken(
            token=str(uuid.uuid4()),
            token_type=QRTokenType.PARENT_PICKUP,
            school_id=str(student.school_id),
            student_id=student_id,
            issued_date=today,
            expires_at=token_expires_at(),
        )
        db.add(token)
        await db.commit()
        await db.refresh(token)

    return token, student


# ── Student Security Profiles ─────────────────────────────────────────────────

@router.post("/profiles", response_model=StudentSecurityProfile)
async def create_security_profile(
    data: StudentSecurityProfileCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Create a security profile for a student"""
    existing = await db.exec(
        select(StudentSecurityProfile).where(StudentSecurityProfile.student_id == data.student_id)
    )
    if existing.first():
        raise HTTPException(status_code=400, detail="Security profile already exists for this student")

    profile = StudentSecurityProfile(**data.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/profiles/{student_id}", response_model=StudentSecurityProfile)
async def get_security_profile(
    student_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await db.exec(
        select(StudentSecurityProfile).where(StudentSecurityProfile.student_id == student_id)
    )
    profile = result.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Security profile not found")
    return profile


@router.patch("/profiles/{student_id}", response_model=StudentSecurityProfile)
async def update_security_profile(
    student_id: str,
    data: StudentSecurityProfileUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    result = await db.exec(
        select(StudentSecurityProfile).where(StudentSecurityProfile.student_id == student_id)
    )
    profile = result.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Security profile not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.updated_at = datetime.utcnow()

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


# ── QR Token Generation ───────────────────────────────────────────────────────

@router.post("/qr/generate-daily")
async def generate_daily_qr_tokens(
    body: SchoolScopedRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """
    Generate daily QR tokens for all students with parent pickup method.
    Also generates transport dispatch tokens for each route.
    Call this once per school day — idempotent (skips already-issued tokens).
    """
    school_id = body.school_id
    today = today_str()
    expires = token_expires_at()
    created = 0

    # Parent pickup tokens — one per student
    students_result = await db.exec(
        select(StudentSecurityProfile).where(
            and_(
                StudentSecurityProfile.school_id == school_id,
                StudentSecurityProfile.pickup_method == "parent",
            )
        )
    )
    profiles = students_result.all()

    for profile in profiles:
        existing = await db.exec(
            select(DailyQRToken).where(
                and_(
                    DailyQRToken.student_id == profile.student_id,
                    DailyQRToken.issued_date == today,
                    DailyQRToken.token_type == QRTokenType.PARENT_PICKUP,
                )
            )
        )
        if existing.first():
            continue

        token = DailyQRToken(
            token=str(uuid.uuid4()),
            token_type=QRTokenType.PARENT_PICKUP,
            school_id=school_id,
            student_id=profile.student_id,
            issued_date=today,
            expires_at=expires,
        )
        db.add(token)
        created += 1

    await db.commit()
    return {"message": f"Generated {created} QR tokens for {today}", "date": today}


@router.get("/qr/student/{student_id}")
async def get_student_qr_token(
    student_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get (or lazily create) today's QR token for a student."""
    token, student = await get_or_create_qr_token(db, student_id)
    if not token:
        raise HTTPException(status_code=404, detail="Student not found")
    return token


@router.post("/qr/student/{student_id}/email")
async def email_student_qr(
    student_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Email today's pickup QR code to the authenticated parent."""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="No email address on your account")

    token, student = await get_or_create_qr_token(db, student_id)
    if not token:
        raise HTTPException(status_code=404, detail="Student not found")

    school_result = await db.exec(select(School).where(School.id == token.school_id))
    school = school_result.first()
    school_name = school.name if school else "School"

    student_name = f"{student.first_name} {student.last_name}" if student else "your child"

    background_tasks.add_task(
        email_service.send_qr_email,
        to=current_user.email,
        student_name=student_name,
        qr_token=token.token,
        expires_at=token.expires_at.strftime("%I:%M %p").lstrip("0"),
        school_name=school_name,
    )

    return {"message": "QR code emailed successfully"}


@router.post("/qr/my-children/email")
async def email_all_children_qr(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.PARENT)),
):
    """Email today's pickup QR codes for ALL of the parent's linked children in one message."""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="No email address on your account")

    child_ids = await get_parent_children_ids(current_user, db)
    if not child_ids:
        raise HTTPException(status_code=404, detail="No children linked to your account")

    children_payload = []
    school_id = None
    for student_id in child_ids:
        token, student = await get_or_create_qr_token(db, student_id)
        if not token:
            continue
        school_id = school_id or token.school_id
        children_payload.append({
            "name": f"{student.first_name} {student.last_name}",
            "qr_token": token.token,
            "expires_at": token.expires_at.strftime("%I:%M %p").lstrip("0"),
        })

    if not children_payload:
        raise HTTPException(status_code=404, detail="No QR codes available for your children")

    school_result = await db.exec(select(School).where(School.id == school_id))
    school = school_result.first()
    school_name = school.name if school else "School"

    background_tasks.add_task(
        email_service.send_multi_qr_email,
        to=current_user.email,
        children=children_payload,
        school_name=school_name,
    )

    return {"message": "QR codes emailed successfully", "children_count": len(children_payload)}


@router.post("/qr/transport/{route_id}")
async def generate_transport_qr(
    route_id: str,
    body: SchoolScopedRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*OFFICER_ROLES)),
):
    """Generate (or return existing) dispatch QR for a transport route"""
    school_id = body.school_id
    today = today_str()
    result = await db.exec(
        select(DailyQRToken).where(
            and_(
                DailyQRToken.route_id == route_id,
                DailyQRToken.issued_date == today,
                DailyQRToken.token_type == QRTokenType.TRANSPORT_DISPATCH,
            )
        )
    )
    existing = result.first()
    if existing:
        return existing

    token = DailyQRToken(
        token=str(uuid.uuid4()),
        token_type=QRTokenType.TRANSPORT_DISPATCH,
        school_id=school_id,
        route_id=route_id,
        issued_date=today,
        expires_at=token_expires_at(),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


# ── QR Verification ───────────────────────────────────────────────────────────

@router.post("/qr/verify")
async def verify_qr_token(
    body: VerifyQRRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*OFFICER_ROLES)),
):
    """
    Verify a scanned QR token.
    On success: marks token as used, creates a CollectorTrackingSession,
    logs the scan, and returns student info + collector session token for
    the officer's screen to display as a second QR.
    """
    token = body.token
    gate_lat = body.gate_lat
    gate_lng = body.gate_lng
    today = today_str()
    now = datetime.utcnow()

    token_result = await db.exec(
        select(DailyQRToken).where(DailyQRToken.token == token)
    )
    qr = token_result.first()

    # Build scan log regardless of outcome
    scan = SecurityScanLog(
        school_id=current_user.school_id or "",
        token_scanned=token,
        scanned_by_id=current_user.id,
        gate_lat=gate_lat,
        gate_lng=gate_lng,
        result=ScanResult.UNAUTHORIZED,
    )

    if not qr:
        scan.result = ScanResult.UNAUTHORIZED
        db.add(scan)
        await db.commit()
        return {"result": ScanResult.UNAUTHORIZED, "reason": "Token not found"}

    if qr.issued_date != today or qr.expires_at < now:
        scan.result = ScanResult.EXPIRED
        db.add(scan)
        await db.commit()
        return {"result": ScanResult.EXPIRED, "reason": "Token expired"}

    if qr.is_used:
        scan.result = ScanResult.ALREADY_USED
        db.add(scan)
        await db.commit()
        return {"result": ScanResult.ALREADY_USED, "reason": "Token already used"}

    # AUTHORIZED — mark token used
    qr.is_used = True
    qr.used_at = now
    scan.result = ScanResult.AUTHORIZED
    scan.student_id = qr.student_id

    # Create collector tracking session using the embedded token
    collector_session = None
    if qr.token_type == QRTokenType.PARENT_PICKUP:
        collector_session = CollectorTrackingSession(
            session_token=qr.collector_session_token,
            school_id=qr.school_id,
            student_id=qr.student_id,
            scan_log_id=scan.id,
            gate_lat=gate_lat,
            gate_lng=gate_lng,
        )
        db.add(collector_session)
        scan.collector_session_id = qr.collector_session_token

        # Update student arrival status
        profile_result = await db.exec(
            select(StudentSecurityProfile).where(
                StudentSecurityProfile.student_id == qr.student_id
            )
        )
        profile = profile_result.first()
        if profile:
            profile.arrival_status = ArrivalStatus.EN_ROUTE_COLLECTOR
            profile.updated_at = now
            db.add(profile)

        # Log arrival event
        event = ArrivalEvent(
            school_id=qr.school_id,
            student_id=qr.student_id,
            event_type=ArrivalEventType.EN_ROUTE_COLLECTOR,
            triggered_by_id=current_user.id,
            notes=f"Released at gate by {current_user.first_name} {current_user.last_name}",
        )
        db.add(event)

    db.add(qr)
    db.add(scan)
    await db.commit()

    # Fetch student info for the response
    student_result = await db.exec(
        select(Student).where(Student.id == qr.student_id)
    )
    student = student_result.first()

    return {
        "result": ScanResult.AUTHORIZED,
        "token_type": qr.token_type,
        "student": {
            "id": student.id if student else qr.student_id,
            "name": f"{student.first_name} {student.last_name}" if student else "Unknown",
        },
        "collector_session_token": qr.collector_session_token if qr.token_type == QRTokenType.PARENT_PICKUP else None,
        "scan_id": scan.id,
    }


# ── Arrival Status ────────────────────────────────────────────────────────────

@router.get("/students")
async def get_all_students_status(
    school_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*OFFICER_ROLES)),
):
    """All students in the school with their security status.
    Auto-creates a default profile for any student that doesn't have one yet."""

    # Fetch all students in the school
    all_students_result = await db.exec(
        select(Student).where(Student.school_id == school_id)
    )
    all_students = all_students_result.all()

    if not all_students:
        return []

    student_ids = [s.id for s in all_students]

    # Fetch existing profiles
    profiles_result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.student_id.in_(student_ids)
        )
    )
    profiles_by_student = {p.student_id: p for p in profiles_result.all()}

    # Auto-create missing profiles in bulk then re-fetch to avoid SQLAlchemy expiry
    missing = [s for s in all_students if s.id not in profiles_by_student]
    if missing:
        for student in missing:
            db.add(StudentSecurityProfile(student_id=student.id, school_id=school_id))
        await db.commit()
        # Re-fetch both students and profiles — commit() expires all loaded objects
        all_students_result2 = await db.exec(
            select(Student).where(Student.school_id == school_id)
        )
        all_students = all_students_result2.all()
        profiles_result2 = await db.exec(
            select(StudentSecurityProfile).where(
                StudentSecurityProfile.student_id.in_(student_ids)
            )
        )
        profiles_by_student = {p.student_id: p for p in profiles_result2.all()}

    # Resolve class names in one query
    class_ids = {s.class_id for s in all_students if s.class_id}
    class_names: dict[str, str] = {}
    if class_ids:
        classes_result = await db.exec(select(Class).where(Class.id.in_(class_ids)))
        class_names = {c.id: c.name for c in classes_result.all()}

    # Fetch all notes for these students in one query
    notes_result = await db.exec(
        select(ParentNote).where(
            ParentNote.student_id.in_(student_ids)
        ).order_by(ParentNote.created_at.desc())
    )
    notes_by_student: dict[str, list] = {}
    for note in notes_result.all():
        notes_by_student.setdefault(note.student_id, []).append(note)

    students = []
    for student in all_students:
        profile = profiles_by_student[student.id]
        notes = notes_by_student.get(student.id, [])
        students.append({
            "id": student.id,
            "name": f"{student.first_name} {student.last_name}",
            "class": class_names.get(student.class_id, ""),
            "gender": student.gender,
            "pickup_method": profile.pickup_method,
            "transport_route_id": profile.transport_route_id,
            "ghana_post_address": profile.ghana_post_address,
            "neighbourhood": profile.neighbourhood,
            "home_lat": profile.home_lat,
            "home_lng": profile.home_lng,
            "arrival_status": profile.arrival_status,
            "arrival_time": profile.arrival_time,
            "confirmed_at": profile.confirmed_at,
            "parent_notes": [
                {
                    "id": n.id,
                    "text": n.text,
                    "author_id": n.author_id,
                    "is_confirmation": n.is_confirmation,
                    "created_at": n.created_at,
                }
                for n in notes
            ],
        })

    return students


@router.patch("/students/{student_id}/status")
async def update_student_status(
    student_id: str,
    body: UpdateArrivalStatusRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(
        UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN,
        UserRole.SECURITY_OFFICER, UserRole.DRIVER
    )),
):
    """Update a student's arrival status — used by officers and drivers"""
    arrival_status = body.arrival_status
    result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.student_id == student_id
        )
    )
    profile = result.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Security profile not found")

    now = datetime.utcnow()
    profile.arrival_status = arrival_status
    profile.updated_at = now

    if arrival_status == ArrivalStatus.ARRIVED_UNCONFIRMED:
        profile.arrival_time = now

    db.add(profile)

    event_map = {
        ArrivalStatus.EN_ROUTE_BUS: ArrivalEventType.EN_ROUTE_BUS,
        ArrivalStatus.EN_ROUTE_COLLECTOR: ArrivalEventType.EN_ROUTE_COLLECTOR,
        ArrivalStatus.ARRIVED_UNCONFIRMED: ArrivalEventType.ARRIVED,
        ArrivalStatus.SAFE_CONFIRMED: ArrivalEventType.PARENT_CONFIRMED,
    }
    if arrival_status in event_map:
        event = ArrivalEvent(
            school_id=profile.school_id,
            student_id=student_id,
            event_type=event_map[arrival_status],
            triggered_by_id=current_user.id,
        )
        db.add(event)

    await db.commit()
    await db.refresh(profile)
    return {"status": profile.arrival_status, "updated_at": profile.updated_at}


@router.post("/students/{student_id}/confirm")
async def parent_confirm_safe_arrival(
    student_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.PARENT)),
):
    """Parent confirms their child arrived home safely"""
    result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.student_id == student_id
        )
    )
    profile = result.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Security profile not found")

    now = datetime.utcnow()
    profile.arrival_status = ArrivalStatus.SAFE_CONFIRMED
    profile.confirmed_at = now
    profile.updated_at = now
    db.add(profile)

    # Auto-create a confirmation note
    note = ParentNote(
        school_id=profile.school_id,
        student_id=student_id,
        author_id=current_user.id,
        text=f"Confirmed safe arrival at {now.strftime('%H:%M')}.",
        is_confirmation=True,
    )
    db.add(note)

    # Log event
    event = ArrivalEvent(
        school_id=profile.school_id,
        student_id=student_id,
        event_type=ArrivalEventType.PARENT_CONFIRMED,
        triggered_by_id=current_user.id,
    )
    db.add(event)

    # Close any active collector session for this student
    session_result = await db.exec(
        select(CollectorTrackingSession).where(
            and_(
                CollectorTrackingSession.student_id == student_id,
                CollectorTrackingSession.is_active == True,
            )
        )
    )
    session = session_result.first()
    if session:
        session.is_active = False
        session.ended_at = now
        db.add(session)

    await db.commit()
    return {"status": "safe_confirmed", "confirmed_at": now}


# ── Parent-accessible child status ───────────────────────────────────────────

@router.get("/students/{student_id}/status")
async def get_student_security_status(
    student_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Returns security profile + active collector/bus session for ONE student.
    Parents use this for their own children; officers/admins can use it for any student.
    """
    profile_result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.student_id == student_id
        )
    )
    profile = profile_result.first()
    if not profile:
        # Auto-create a default profile so the parent portal never errors on first load
        student_result = await db.exec(select(Student).where(Student.id == student_id))
        student = student_result.first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        profile = StudentSecurityProfile(
            student_id=student_id,
            school_id=str(student.school_id),
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    notes_result = await db.exec(
        select(ParentNote).where(
            ParentNote.student_id == student_id
        ).order_by(ParentNote.created_at.desc())
    )
    notes = notes_result.all()

    collector_result = await db.exec(
        select(CollectorTrackingSession).where(
            and_(
                CollectorTrackingSession.student_id == student_id,
                CollectorTrackingSession.is_active == True,
            )
        )
    )
    collector = collector_result.first()

    return {
        "student_id": student_id,
        "pickup_method": profile.pickup_method,
        "transport_route_id": profile.transport_route_id,
        "ghana_post_address": profile.ghana_post_address,
        "neighbourhood": profile.neighbourhood,
        "home_lat": profile.home_lat,
        "home_lng": profile.home_lng,
        "arrival_status": profile.arrival_status,
        "arrival_time": profile.arrival_time,
        "confirmed_at": profile.confirmed_at,
        "collector_session_token": collector.session_token if collector else None,
        "notes": [
            {
                "id": n.id,
                "text": n.text,
                "author_id": n.author_id,
                "is_confirmation": n.is_confirmation,
                "created_at": str(n.created_at),
            }
            for n in notes
        ],
    }


# ── Parent Notes ──────────────────────────────────────────────────────────────

@router.get("/students/{student_id}/notes")
async def get_student_notes(
    student_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await db.exec(
        select(ParentNote).where(
            ParentNote.student_id == student_id
        ).order_by(ParentNote.created_at.desc())
    )
    return result.all()


@router.post("/students/{student_id}/notes")
async def add_parent_note(
    student_id: str,
    data: ParentNoteCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.PARENT)),
):
    profile_result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.student_id == student_id
        )
    )
    profile = profile_result.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Security profile not found")

    note = ParentNote(
        school_id=profile.school_id,
        student_id=student_id,
        author_id=current_user.id,
        text=data.text,
        is_confirmation=data.is_confirmation,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


# ── Transport Dispatch ────────────────────────────────────────────────────────

@router.post("/transport/{route_id}/dispatch")
async def dispatch_route(
    route_id: str,
    body: SchoolScopedRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*OFFICER_ROLES)),
):
    """
    Dispatch a transport route — sets all enrolled students to en_route_bus
    and logs departure events.
    """
    school_id = body.school_id
    result = await db.exec(
        select(StudentSecurityProfile).where(
            and_(
                StudentSecurityProfile.school_id == school_id,
                StudentSecurityProfile.transport_route_id == route_id,
                StudentSecurityProfile.pickup_method == "transport",
            )
        )
    )
    profiles = result.all()

    if not profiles:
        raise HTTPException(status_code=404, detail="No students found on this route")

    now = datetime.utcnow()
    for profile in profiles:
        profile.arrival_status = ArrivalStatus.EN_ROUTE_BUS
        profile.updated_at = now
        db.add(profile)

        event = ArrivalEvent(
            school_id=school_id,
            student_id=profile.student_id,
            event_type=ArrivalEventType.EN_ROUTE_BUS,
            triggered_by_id=current_user.id,
            notes=f"Route {route_id} dispatched",
        )
        db.add(event)

    await db.commit()
    return {"dispatched": len(profiles), "route_id": route_id, "dispatched_at": now}


# ── Live Bus Location ─────────────────────────────────────────────────────────

@router.post("/transport/{route_id}/location")
async def post_bus_location(
    route_id: str,
    data: LiveBusLocationCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.DRIVER, *ADMIN_ROLES)),
):
    """Driver posts current GPS coordinates — called every 10s from driver's device"""
    loc = LiveBusLocation(
        school_id=current_user.school_id or "",
        route_id=route_id,
        driver_id=current_user.id,
        lat=data.lat,
        lng=data.lng,
        speed_kmh=data.speed_kmh,
        heading=data.heading,
    )
    db.add(loc)
    await db.commit()
    return {"recorded": True, "recorded_at": loc.recorded_at}


@router.get("/transport/{route_id}/location")
async def get_bus_location(
    route_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get the latest bus position for a route"""
    result = await db.exec(
        select(LiveBusLocation).where(
            LiveBusLocation.route_id == route_id
        ).order_by(LiveBusLocation.recorded_at.desc())
    )
    latest = result.first()
    if not latest:
        raise HTTPException(status_code=404, detail="No location data for this route")
    return latest


# ── Collector Location Sharing ────────────────────────────────────────────────

@router.get("/collector/{session_token}")
async def get_collector_session(
    session_token: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Collector opens the link from the officer's screen.
    No login required — token is the authentication.
    Returns session info so the collector's page can confirm who they are collecting.
    """
    result = await db.exec(
        select(CollectorTrackingSession).where(
            CollectorTrackingSession.session_token == session_token
        )
    )
    session = result.first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_active:
        raise HTTPException(status_code=410, detail="This tracking session has ended")

    student_result = await db.exec(
        select(Student).where(Student.id == session.student_id)
    )
    student = student_result.first()

    return {
        "session_id": session.id,
        "session_token": session.session_token,
        "student_name": f"{student.first_name} {student.last_name}" if student else "Student",
        "started_at": session.started_at,
        "is_active": session.is_active,
    }


@router.post("/collector/{session_token}/location")
async def post_collector_location(
    session_token: str,
    data: CollectorLocationCreate,
    db: AsyncSession = Depends(get_session),
):
    """
    Collector's phone posts GPS coordinates.
    No login required — session_token is the auth.
    Called every 10s from the collector-share page.
    """
    result = await db.exec(
        select(CollectorTrackingSession).where(
            CollectorTrackingSession.session_token == session_token
        )
    )
    session = result.first()
    if not session or not session.is_active:
        raise HTTPException(status_code=410, detail="Session not found or already ended")

    loc = CollectorLiveLocation(
        session_id=session.id,
        lat=data.lat,
        lng=data.lng,
    )
    db.add(loc)
    await db.commit()
    return {"recorded": True}


@router.get("/collector/{session_token}/location/live")
async def get_collector_live_location(
    session_token: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Parent polls this endpoint to get the collector's latest position"""
    session_result = await db.exec(
        select(CollectorTrackingSession).where(
            CollectorTrackingSession.session_token == session_token
        )
    )
    session = session_result.first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    loc_result = await db.exec(
        select(CollectorLiveLocation).where(
            CollectorLiveLocation.session_id == session.id
        ).order_by(CollectorLiveLocation.recorded_at.desc())
    )
    latest = loc_result.first()
    if not latest:
        return {"lat": None, "lng": None, "is_active": session.is_active}

    return {
        "lat": latest.lat,
        "lng": latest.lng,
        "recorded_at": latest.recorded_at,
        "is_active": session.is_active,
    }


@router.post("/collector/{session_token}/end")
async def end_collector_session(
    session_token: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """End a collector tracking session — called when parent confirms safe arrival"""
    result = await db.exec(
        select(CollectorTrackingSession).where(
            CollectorTrackingSession.session_token == session_token
        )
    )
    session = result.first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False
    session.ended_at = datetime.utcnow()
    db.add(session)
    await db.commit()
    return {"ended": True, "ended_at": session.ended_at}


# ── Admin Overview ────────────────────────────────────────────────────────────

@router.get("/admin/overview")
async def get_admin_overview(
    school_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*OFFICER_ROLES)),
):
    """
    Single endpoint for the admin tracking page.
    Returns all students with statuses, latest note, and latest bus positions.
    """
    students_result = await db.exec(
        select(StudentSecurityProfile, Student).join(
            Student, Student.id == StudentSecurityProfile.student_id
        ).where(StudentSecurityProfile.school_id == school_id)
    )
    rows = students_result.all()

    # Build class name lookup to avoid N+1 queries
    class_ids = {student.class_id for _, student in rows if student.class_id}
    class_names: dict[str, str] = {}
    if class_ids:
        classes_result = await db.exec(select(Class).where(Class.id.in_(class_ids)))
        for cls in classes_result.all():
            class_names[cls.id] = cls.name

    student_data = []
    for profile, student in rows:
        last_note_result = await db.exec(
            select(ParentNote).where(
                ParentNote.student_id == profile.student_id
            ).order_by(ParentNote.created_at.desc())
        )
        last_note = last_note_result.first()

        collector_result = await db.exec(
            select(CollectorTrackingSession).where(
                and_(
                    CollectorTrackingSession.student_id == profile.student_id,
                    CollectorTrackingSession.is_active == True,
                )
            )
        )
        collector = collector_result.first()

        student_data.append({
            "id": student.id,
            "name": f"{student.first_name} {student.last_name}",
            "class": class_names.get(student.class_id, student.class_id),
            "gender": student.gender,
            "pickup_method": profile.pickup_method,
            "transport_route_id": profile.transport_route_id,
            "ghana_post_address": profile.ghana_post_address,
            "neighbourhood": profile.neighbourhood,
            "home_lat": profile.home_lat,
            "home_lng": profile.home_lng,
            "arrival_status": profile.arrival_status,
            "arrival_time": profile.arrival_time,
            "confirmed_at": profile.confirmed_at,
            "collector_session_token": collector.session_token if collector else None,
            "last_note": {
                "text": last_note.text,
                "author_id": last_note.author_id,
                "created_at": last_note.created_at,
                "is_confirmation": last_note.is_confirmation,
            } if last_note else None,
        })

    return {"students": student_data, "as_of": datetime.utcnow()}


# ── Daily Reset ───────────────────────────────────────────────────────────────

@router.post("/admin/reset-day")
async def reset_daily_status(
    body: SchoolScopedRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """
    Reset all student arrival statuses to pending for a new school day.
    Call this each morning before QR generation.
    """
    school_id = body.school_id
    result = await db.exec(
        select(StudentSecurityProfile).where(
            StudentSecurityProfile.school_id == school_id
        )
    )
    profiles = result.all()

    for profile in profiles:
        profile.arrival_status = ArrivalStatus.PENDING
        profile.arrival_time = None
        profile.confirmed_at = None
        profile.updated_at = datetime.utcnow()
        db.add(profile)

    await db.commit()
    return {"reset": len(profiles), "date": today_str()}
