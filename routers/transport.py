"""Transport Management Router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.encoders import jsonable_encoder
from sqlmodel import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Optional, List
import uuid
import json
import logging
from models.transport import (
    Vehicle, VehicleCreate, VehicleUpdate, VehicleStatus, VehicleType,
    Route, RouteCreate, RouteUpdate, RouteStatus,
    StudentTransport, StudentTransportCreate, StudentTransportUpdate,
    TransportAttendance, TransportAttendanceCreate, TransportAttendanceBulk, AttendanceStatus,
    TransportFee, TransportFeeCreate, TransportFeeUpdate, TransportFeeType,
    VehicleMaintenance, VehicleMaintenanceCreate,
    DriverStaff, DriverStaffCreate, DriverStaffUpdate
)
from models.student import Student
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport", tags=["Transport Management"])


# ============================================================================
# VEHICLE TYPE ENDPOINT
# ============================================================================

@router.get("/vehicle-types", response_model=List[dict])
async def get_vehicle_types():
    """Get all available vehicle types"""
    vehicle_type_labels = {
        "bus": "Bus",
        "van": "Van",
        "minibus": "Mini Bus",
        "shuttle": "Shuttle"
    }
    return [
        {"value": vtype.value, "label": vehicle_type_labels.get(vtype.value, vtype.value.capitalize())}
        for vtype in VehicleType
    ]


# ============================================================================
# VEHICLE ENDPOINTS
# ============================================================================

@router.get("/vehicles", response_model=List[dict])
async def list_vehicles(
    status: Optional[VehicleStatus] = None,
    vehicle_type: Optional[VehicleType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all vehicles for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Vehicle).where(Vehicle.school_id == school_id)
    
    if status:
        query = query.where(Vehicle.status == status)
    if vehicle_type:
        query = query.where(Vehicle.vehicle_type == vehicle_type)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    vehicles = result.scalars().all()
    
    return [
        {
            **jsonable_encoder(v),
            "vehicle_type": v.vehicle_type.value,
            "status": v.status.value
        }
        for v in vehicles
    ]


@router.post("/vehicles", response_model=dict)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new vehicle"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Check if registration number already exists
    result = await session.execute(
        select(Vehicle).where(Vehicle.registration_number == vehicle_data.registration_number)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle with this registration number already exists")
    
    vehicle = Vehicle(
        **vehicle_data.dict(),
        school_id=school_id
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    
    return {
        **jsonable_encoder(vehicle),
        "vehicle_type": vehicle.vehicle_type.value,
        "status": vehicle.status.value
    }


@router.get("/vehicles/{vehicle_id}", response_model=dict)
async def get_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get vehicle details"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Vehicle).where(
            and_(Vehicle.id == vehicle_id, Vehicle.school_id == school_id)
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    return {
        **jsonable_encoder(vehicle),
        "vehicle_type": vehicle.vehicle_type.value,
        "status": vehicle.status.value
    }


@router.put("/vehicles/{vehicle_id}", response_model=dict)
async def update_vehicle(
    vehicle_id: str,
    vehicle_data: VehicleUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update vehicle information"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Vehicle).where(
            and_(Vehicle.id == vehicle_id, Vehicle.school_id == school_id)
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    update_data = vehicle_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vehicle, key, value)
    
    vehicle.updated_at = datetime.utcnow()
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    
    return {
        **jsonable_encoder(vehicle),
        "vehicle_type": vehicle.vehicle_type.value,
        "status": vehicle.status.value
    }


@router.delete("/vehicles/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a vehicle"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Vehicle).where(
            and_(Vehicle.id == vehicle_id, Vehicle.school_id == school_id)
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    await session.delete(vehicle)
    await session.commit()


# ============================================================================
# ROUTE ENDPOINTS
# ============================================================================

@router.get("/routes", response_model=List[dict])
async def list_routes(
    status: Optional[RouteStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all transport routes"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Route).where(Route.school_id == school_id)
    
    if status:
        query = query.where(Route.status == status)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    routes = result.scalars().all()
    
    return [
        {
            **jsonable_encoder(r),
            "status": r.status.value,
            "pickup_days": json.loads(r.pickup_days) if isinstance(r.pickup_days, str) else r.pickup_days,
            "intermediate_stops": json.loads(r.intermediate_stops) if r.intermediate_stops and isinstance(r.intermediate_stops, str) else r.intermediate_stops
        }
        for r in routes
    ]


@router.post("/routes", response_model=dict)
async def create_route(
    route_data: RouteCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a new transport route"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Check if route code already exists
    result = await session.execute(
        select(Route).where(Route.route_code == route_data.route_code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Route with this code already exists")
    
    # Ensure pickup_days is stored as JSON string if it's a list
    pickup_days = route_data.pickup_days
    if isinstance(pickup_days, list):
        pickup_days = json.dumps(pickup_days)
    
    intermediate_stops = route_data.intermediate_stops
    if isinstance(intermediate_stops, list):
        intermediate_stops = json.dumps(intermediate_stops)
    
    route = Route(
        **route_data.dict(exclude={"pickup_days", "intermediate_stops"}),
        school_id=school_id,
        pickup_days=pickup_days,
        intermediate_stops=intermediate_stops
    )
    session.add(route)
    await session.commit()
    await session.refresh(route)
    
    return {
        **jsonable_encoder(route),
        "status": route.status.value,
        "pickup_days": json.loads(route.pickup_days) if isinstance(route.pickup_days, str) else route.pickup_days,
        "intermediate_stops": json.loads(route.intermediate_stops) if route.intermediate_stops and isinstance(route.intermediate_stops, str) else route.intermediate_stops
    }


@router.get("/routes/{route_id}", response_model=dict)
async def get_route(
    route_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get route details"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Route).where(
            and_(Route.id == route_id, Route.school_id == school_id)
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    return {
        **jsonable_encoder(route),
        "status": route.status.value,
        "pickup_days": json.loads(route.pickup_days) if isinstance(route.pickup_days, str) else route.pickup_days,
        "intermediate_stops": json.loads(route.intermediate_stops) if route.intermediate_stops and isinstance(route.intermediate_stops, str) else route.intermediate_stops
    }


@router.get("/routes/{route_id}/students", response_model=List[dict])
async def get_route_students(
    route_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all students enrolled in a specific route"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify route exists
    result = await session.execute(
        select(Route).where(
            and_(Route.id == route_id, Route.school_id == school_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get students enrolled in this route
    query = select(StudentTransport).where(
        and_(
            StudentTransport.route_id == route_id,
            StudentTransport.school_id == school_id
        )
    ).order_by(StudentTransport.created_at).offset(skip).limit(limit)
    
    result = await session.execute(query)
    enrollments = result.scalars().all()
    
    # Fetch student data for each enrollment
    enrollment_responses = []
    for e in enrollments:
        # Get student data
        student_result = await session.execute(
            select(Student).where(Student.id == e.student_id)
        )
        student = student_result.scalar_one_or_none()
        
        enrollment_dict = jsonable_encoder(e)
        if student:
            enrollment_dict["first_name"] = student.first_name
            enrollment_dict["last_name"] = student.last_name
            enrollment_dict["student_id"] = student.student_id
        
        enrollment_responses.append(enrollment_dict)
    
    return enrollment_responses


@router.put("/routes/{route_id}", response_model=dict)
async def update_route(
    route_id: str,
    route_data: RouteUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update route information"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Route).where(
            and_(Route.id == route_id, Route.school_id == school_id)
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    update_data = route_data.dict(exclude_unset=True)
    
    # Handle JSON fields
    if "pickup_days" in update_data and isinstance(update_data["pickup_days"], list):
        update_data["pickup_days"] = json.dumps(update_data["pickup_days"])
    if "intermediate_stops" in update_data and isinstance(update_data["intermediate_stops"], list):
        update_data["intermediate_stops"] = json.dumps(update_data["intermediate_stops"])
    
    for key, value in update_data.items():
        setattr(route, key, value)
    
    route.updated_at = datetime.utcnow()
    session.add(route)
    await session.commit()
    await session.refresh(route)
    
    return {
        **jsonable_encoder(route),
        "status": route.status.value,
        "pickup_days": json.loads(route.pickup_days) if isinstance(route.pickup_days, str) else route.pickup_days,
        "intermediate_stops": json.loads(route.intermediate_stops) if route.intermediate_stops and isinstance(route.intermediate_stops, str) else route.intermediate_stops
    }


@router.delete("/routes/{route_id}", status_code=204)
async def delete_route(
    route_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a route"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Route).where(
            and_(Route.id == route_id, Route.school_id == school_id)
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    await session.delete(route)
    await session.commit()


# ============================================================================
# STUDENT TRANSPORT ENROLLMENT
# ============================================================================

@router.post("/enrollments", response_model=dict)
async def enroll_student_transport(
    enrollment_data: StudentTransportCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.PARENT)),
    session: AsyncSession = Depends(get_session)
):
    """Enroll a student in transport"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify student exists and belongs to school
    result = await session.execute(
        select(Student).where(
            and_(Student.id == enrollment_data.student_id, Student.school_id == school_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Verify route exists
    result = await session.execute(
        select(Route).where(
            and_(Route.id == enrollment_data.route_id, Route.school_id == school_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Check if already enrolled in this route
    result = await session.execute(
        select(StudentTransport).where(
            and_(
                StudentTransport.student_id == enrollment_data.student_id,
                StudentTransport.route_id == enrollment_data.route_id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Student is already enrolled in this route")
    
    enrollment = StudentTransport(
        **enrollment_data.dict(),
        school_id=school_id
    )
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    
    return jsonable_encoder(enrollment)


@router.get("/enrollments", response_model=List[dict])
async def get_all_enrollments(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all student transport enrollments for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(StudentTransport).where(
            StudentTransport.school_id == school_id
        )
    )
    enrollments = result.scalars().all()
    
    # Fetch student and route data for each enrollment
    enrollment_responses = []
    for e in enrollments:
        # Get student data
        student_result = await session.execute(
            select(Student).where(Student.id == e.student_id)
        )
        student = student_result.scalar_one_or_none()
        
        # Get route data
        route_result = await session.execute(
            select(Route).where(Route.id == e.route_id)
        )
        route = route_result.scalar_one_or_none()
        
        enrollment_dict = jsonable_encoder(e)
        if student:
            enrollment_dict["student"] = jsonable_encoder(student)
        if route:
            enrollment_dict["route"] = {
                "id": route.id,
                "route_name": route.route_name,
                "route_code": route.route_code,
                "status": route.status.value
            }
        
        enrollment_responses.append(enrollment_dict)
    
    return enrollment_responses


@router.get("/enrollment/{student_id}", response_model=List[dict])
async def get_student_routes(
    student_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all routes for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(StudentTransport).where(
            and_(
                StudentTransport.student_id == student_id,
                StudentTransport.school_id == school_id
            )
        )
    )
    enrollments = result.scalars().all()
    
    return [jsonable_encoder(e) for e in enrollments]


@router.put("/enrollments/{enrollment_id}", response_model=dict)
async def update_enrollment(
    enrollment_id: str,
    enrollment_data: StudentTransportUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update student transport enrollment"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(StudentTransport).where(
            and_(
                StudentTransport.id == enrollment_id,
                StudentTransport.school_id == school_id
            )
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    update_data = enrollment_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(enrollment, key, value)
    
    enrollment.updated_at = datetime.utcnow()
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    
    return jsonable_encoder(enrollment)


@router.delete("/enrollments/{enrollment_id}", status_code=204)
async def remove_enrollment(
    enrollment_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Remove student from transport"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(StudentTransport).where(
            and_(
                StudentTransport.id == enrollment_id,
                StudentTransport.school_id == school_id
            )
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    await session.delete(enrollment)
    await session.commit()


# ============================================================================
# TRANSPORT ATTENDANCE
# ============================================================================

@router.post("/attendance", response_model=dict)
async def mark_attendance(
    attendance_data: TransportAttendanceCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Mark student attendance for transport"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify route exists
    result = await session.execute(
        select(Route).where(Route.id == attendance_data.route_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Verify vehicle exists
    result = await session.execute(
        select(Vehicle).where(Vehicle.id == attendance_data.vehicle_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    attendance = TransportAttendance(
        **attendance_data.dict(),
        school_id=school_id
    )
    session.add(attendance)
    await session.commit()
    await session.refresh(attendance)
    
    return {
        **jsonable_encoder(attendance),
        "status": attendance.status.value,
        "trip_type": attendance.trip_type
    }


@router.post("/attendance/bulk", response_model=dict)
async def mark_bulk_attendance(
    bulk_data: TransportAttendanceBulk,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Mark attendance for multiple students"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    records = []
    for att_data in bulk_data.attendance_records:
        attendance = TransportAttendance(
            **att_data.dict(),
            school_id=school_id
        )
        session.add(attendance)
        records.append(attendance)
    
    await session.commit()
    
    return {
        "total_records": len(records),
        "created_at": datetime.utcnow().isoformat(),
        "message": f"Successfully marked attendance for {len(records)} student(s)"
    }


@router.get("/attendance/{route_id}", response_model=List[dict])
async def get_route_attendance(
    route_id: str,
    attendance_date: Optional[str] = None,
    trip_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get attendance records for a route"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(TransportAttendance).where(
        and_(
            TransportAttendance.route_id == route_id,
            TransportAttendance.school_id == school_id
        )
    )
    
    if attendance_date:
        query = query.where(TransportAttendance.attendance_date == attendance_date)
    if trip_type:
        query = query.where(TransportAttendance.trip_type == trip_type)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    records = result.scalars().all()
    
    return [
        {
            **jsonable_encoder(r),
            "status": r.status.value
        }
        for r in records
    ]


# ============================================================================
# TRANSPORT FEES
# ============================================================================

@router.post("/fees", response_model=dict)
async def create_transport_fee(
    fee_data: TransportFeeCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create transport fee for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify student exists
    result = await session.execute(
        select(Student).where(Student.id == fee_data.student_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Verify route exists
    result = await session.execute(
        select(Route).where(Route.id == fee_data.route_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Create fee and calculate is_paid (amount_paid + discount >= amount_due)
    fee_dict = fee_data.dict()
    amount_paid = fee_dict.get('amount_paid', 0.0)
    amount_due = fee_dict.get('amount_due', 0.0)
    discount = fee_dict.get('discount', 0.0)
    total_covered = amount_paid + discount
    is_paid = total_covered >= amount_due
    
    fee = TransportFee(
        **fee_dict,
        school_id=school_id,
        is_paid=is_paid
    )
    session.add(fee)
    await session.commit()
    await session.refresh(fee)
    
    # Auto-post to GL if any payment is made on creation (partial or full)
    journal_entry_id = None
    if amount_paid > 0:
        try:
            journal_entry_id = await _create_transport_journal_entry(
                session=session,
                school_id=school_id,
                fee_id=fee.id,
                student_id=fee.student_id,
                route_id=fee.route_id,
                payment_amount=amount_paid,
                payment_method=fee_dict.get("payment_method", "cash")
            )
            
            # Update fee with GL posting info
            fee.gl_journal_entry_id = journal_entry_id
            fee.gl_posted_date = datetime.utcnow().isoformat().split('T')[0]
            session.add(fee)
            await session.commit()
            await session.refresh(fee)
            
            logger.info(f"Created journal entry {journal_entry_id} for transport fee {fee.id} (payment: GHS {amount_paid})")
        except Exception as e:
            logger.error(f"Error posting transport fee to GL on creation: {str(e)}")
            # Continue anyway - fee is recorded even if GL posting fails
    
    response = {
        **jsonable_encoder(fee),
        "fee_type": fee.fee_type.value
    }
    
    if journal_entry_id:
        response["journal_entry_id"] = journal_entry_id
    
    return response


@router.get("/fees", response_model=List[dict])
async def get_all_transport_fees(
    is_paid: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all transport fees for the school with pagination, including student and route details"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(TransportFee).where(TransportFee.school_id == school_id)
    
    if is_paid is not None:
        query = query.where(TransportFee.is_paid == is_paid)
    
    query = query.order_by(TransportFee.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    fees = result.scalars().all()
    
    # Fetch student and route details for each fee
    response = []
    for f in fees:
        fee_data = {
            **jsonable_encoder(f),
            "fee_type": f.fee_type.value
        }
        
        # Get student details
        student_result = await session.execute(
            select(Student).where(Student.id == f.student_id)
        )
        student = student_result.scalar_one_or_none()
        if student:
            fee_data["student"] = {
                "id": student.id,
                "first_name": student.first_name,
                "last_name": student.last_name
            }
        
        # Get route details
        route_result = await session.execute(
            select(Route).where(Route.id == f.route_id)
        )
        route = route_result.scalar_one_or_none()
        if route:
            fee_data["route"] = {
                "id": route.id,
                "route_name": route.route_name,
                "route_code": route.route_code,
                "fee_amount": route.fee_amount
            }
        
        response.append(fee_data)
    
    return response


@router.get("/fees/{student_id}", response_model=List[dict])
async def get_student_transport_fees(
    student_id: str,
    is_paid: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get transport fees for a student with route details"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(TransportFee).where(
        and_(
            TransportFee.student_id == student_id,
            TransportFee.school_id == school_id
        )
    )
    
    if is_paid is not None:
        query = query.where(TransportFee.is_paid == is_paid)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    fees = result.scalars().all()
    
    # Fetch route details for each fee
    response = []
    for f in fees:
        fee_data = {
            **jsonable_encoder(f),
            "fee_type": f.fee_type.value
        }
        
        # Get route details
        route_result = await session.execute(
            select(Route).where(Route.id == f.route_id)
        )
        route = route_result.scalar_one_or_none()
        if route:
            fee_data["route"] = {
                "id": route.id,
                "route_name": route.route_name,
                "route_code": route.route_code,
                "fee_amount": route.fee_amount
            }
        
        response.append(fee_data)
    
    return response


@router.put("/fees/{fee_id}", response_model=dict)
async def update_transport_fee(
    fee_id: str,
    fee_data: TransportFeeUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update transport fee payment status and auto-post to GL"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(TransportFee).where(
            and_(TransportFee.id == fee_id, TransportFee.school_id == school_id)
        )
    )
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    
    update_data = fee_data.dict(exclude_unset=True)
    old_amount_paid = fee.amount_paid
    
    # Auto-calculate is_paid based on amount_paid and amount_due
    if "amount_paid" in update_data or "amount_due" in update_data:
        amount_due = update_data.get("amount_due", fee.amount_due)
        amount_paid = update_data.get("amount_paid", fee.amount_paid)
        discount = update_data.get("discount", fee.discount)
        
        total_covered = amount_paid + discount
        update_data["is_paid"] = total_covered >= amount_due
    
    for key, value in update_data.items():
        setattr(fee, key, value)
    
    fee.updated_at = datetime.utcnow()
    session.add(fee)
    await session.commit()
    await session.refresh(fee)
    
    # Auto-post to GL if payment was recorded
    journal_entry_id = None
    if "amount_paid" in update_data and update_data["amount_paid"] > old_amount_paid:
        payment_amount = update_data["amount_paid"] - old_amount_paid
        try:
            journal_entry_id = await _create_transport_journal_entry(
                session=session,
                school_id=school_id,
                fee_id=fee_id,
                student_id=fee.student_id,
                route_id=fee.route_id,
                payment_amount=payment_amount,
                payment_method=update_data.get("payment_method", "cash")
            )
            
            # Update fee with GL posting info
            fee.gl_journal_entry_id = journal_entry_id
            fee.gl_posted_date = datetime.utcnow().isoformat().split('T')[0]
            session.add(fee)
            await session.commit()
            
            logger.info(f"Created journal entry {journal_entry_id} for transport fee payment {fee_id}")
        except Exception as e:
            logger.error(f"Error posting transport fee to GL: {str(e)}")
            # Continue anyway - payment is recorded even if GL posting fails
    
    response = {
        **jsonable_encoder(fee),
        "fee_type": fee.fee_type.value
    }
    
    if journal_entry_id:
        response["journal_entry_id"] = journal_entry_id
    
    return response


@router.delete("/fees/{fee_id}", status_code=204)
async def delete_transport_fee(
    fee_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a transport fee"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(TransportFee).where(
            and_(TransportFee.id == fee_id, TransportFee.school_id == school_id)
        )
    )
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    
    await session.delete(fee)
    await session.commit()
    logger.info(f"Deleted transport fee {fee_id}")


@router.get("/fees-summary", response_model=dict)
async def get_transport_fees_summary(
    academic_term_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get transport fees summary for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(TransportFee).where(TransportFee.school_id == school_id)
    
    if academic_term_id:
        query = query.where(TransportFee.academic_term_id == academic_term_id)
    
    result = await session.execute(query)
    fees = result.scalars().all()
    
    total_due = sum(f.amount_due for f in fees)
    total_paid = sum(f.amount_paid for f in fees)
    total_discount = sum(f.discount for f in fees)
    total_outstanding = total_due - total_paid - total_discount
    
    paid_count = sum(1 for f in fees if f.is_paid)
    unpaid_count = len(fees) - paid_count
    
    return {
        "total_due": total_due,
        "total_paid": total_paid,
        "total_discount": total_discount,
        "total_outstanding": total_outstanding,
        "collection_rate": round((total_paid / total_due * 100) if total_due > 0 else 0, 2),
        "total_students": len(set(f.student_id for f in fees)),
        "fees_paid": paid_count,
        "fees_unpaid": unpaid_count
    }


# ============================================================================
# VEHICLE MAINTENANCE
# ============================================================================

@router.post("/maintenance", response_model=dict)
async def record_maintenance(
    maintenance_data: VehicleMaintenanceCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Record vehicle maintenance"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Verify vehicle exists
    result = await session.execute(
        select(Vehicle).where(Vehicle.id == maintenance_data.vehicle_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    maintenance = VehicleMaintenance(
        **maintenance_data.dict(),
        school_id=school_id
    )
    session.add(maintenance)
    await session.commit()
    await session.refresh(maintenance)
    
    return jsonable_encoder(maintenance)


@router.get("/maintenance/{vehicle_id}", response_model=List[dict])
async def get_vehicle_maintenance_history(
    vehicle_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get maintenance history for a vehicle"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(VehicleMaintenance).where(
        and_(
            VehicleMaintenance.vehicle_id == vehicle_id,
            VehicleMaintenance.school_id == school_id
        )
    ).order_by(VehicleMaintenance.maintenance_date.desc())
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    records = result.scalars().all()
    
    return [jsonable_encoder(r) for r in records]


# ============================================================================
# DRIVER/CONDUCTOR STAFF
# ============================================================================

@router.post("/drivers", response_model=dict)
async def register_driver(
    driver_data: DriverStaffCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Register a driver or conductor"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Check if license already registered
    result = await session.execute(
        select(DriverStaff).where(DriverStaff.license_number == driver_data.license_number)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="License number already registered")
    
    driver = DriverStaff(
        **driver_data.dict(),
        school_id=school_id
    )
    session.add(driver)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "ix_driver_staff_staff_id" in str(e):
            raise HTTPException(status_code=409, detail="This staff member is already registered as a driver")
        elif "license_number" in str(e):
            raise HTTPException(status_code=400, detail="License number already registered")
        else:
            raise HTTPException(status_code=422, detail="Duplicate entry detected")
    await session.refresh(driver)
    
    return jsonable_encoder(driver)


@router.get("/drivers", response_model=List[dict])
async def list_drivers(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all drivers and conductors"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    logger.info(f"List drivers called with role={role}, is_active={is_active}")
    
    query = select(DriverStaff).where(DriverStaff.school_id == school_id)
    
    if role:
        logger.info(f"Filtering by role: {role}")
        query = query.where(DriverStaff.role == role)
    if is_active is not None:
        logger.info(f"Filtering by is_active: {is_active}")
        query = query.where(DriverStaff.is_active == is_active)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    drivers = result.scalars().all()
    
    logger.info(f"Found {len(drivers)} drivers")
    
    return [jsonable_encoder(d) for d in drivers]


@router.get("/drivers/{driver_id}", response_model=dict)
async def get_driver(
    driver_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get driver details"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(DriverStaff).where(
            and_(DriverStaff.id == driver_id, DriverStaff.school_id == school_id)
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    return jsonable_encoder(driver)


@router.put("/drivers/{driver_id}", response_model=dict)
async def update_driver(
    driver_id: str,
    driver_data: DriverStaffUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update driver information"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(DriverStaff).where(
            and_(DriverStaff.id == driver_id, DriverStaff.school_id == school_id)
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    update_data = driver_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(driver, key, value)
    
    driver.updated_at = datetime.utcnow()
    session.add(driver)
    await session.commit()
    await session.refresh(driver)
    
    return jsonable_encoder(driver)


@router.put("/drivers/{driver_id}/verify", response_model=dict)
async def verify_driver(
    driver_id: str,
    verification_notes: str = "",
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Verify a driver"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(DriverStaff).where(
            and_(DriverStaff.id == driver_id, DriverStaff.school_id == school_id)
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    driver.is_verified = True
    driver.verification_date = datetime.utcnow().isoformat()
    driver.notes = verification_notes or driver.notes
    driver.updated_at = datetime.utcnow()
    
    session.add(driver)
    await session.commit()
    await session.refresh(driver)
    
    logger.info(f"Driver {driver_id} verified by {current_user.id}")
    
    return jsonable_encoder(driver)


@router.delete("/drivers/{driver_id}", status_code=204)
async def delete_driver(
    driver_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a driver"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(DriverStaff).where(
            and_(DriverStaff.id == driver_id, DriverStaff.school_id == school_id)
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    await session.delete(driver)
    await session.commit()
    
    logger.info(f"Deleted driver {driver_id}")


# ============================================================================
# GL AUTO-POSTING HELPER FOR TRANSPORT FEES
# ============================================================================

async def _create_transport_journal_entry(
    session: AsyncSession,
    school_id: str,
    fee_id: str,
    student_id: str,
    route_id: str,
    payment_amount: float,
    payment_method: str
) -> str:
    """
    Create GL journal entry for transport fee payment.
    
    Posts:
    - Dr. GL account based on payment method (1001=Cash, 1010=Bank, 1015=Mobile)
    - Cr. 4155 (Transport Fee Revenue)
    
    Args:
        session: AsyncSession
        school_id: School identifier
        fee_id: Transport fee ID for reference
        student_id: Student ID
        route_id: Route ID
        payment_amount: Amount paid
        payment_method: Payment method (cash, bank_transfer, mobile_money, cheque)
        
    Returns:
        Journal entry ID
        
    Raises:
        Exception: If GL accounts not found or GL posting fails
    """
    from services.journal_entry_service import JournalEntryService
    from models.finance import JournalEntryCreate, JournalLineItemCreate, ReferenceType
    from models.finance.chart_of_accounts import GLAccount
    
    # Map payment method to GL bank account
    GL_BANK_ACCOUNTS = {
        "cash": "1001",              # Cash in Hand
        "bank_transfer": "1010",     # Business Checking Account
        "bank": "1010",              # Alias
        "mobile_money": "1015",      # Mobile Money Account
        "mobile": "1015",            # Alias
        "cheque": "1010",            # Bank Account
    }
    
    GL_TRANSPORT_REVENUE = "4155"   # Transport Fee Revenue
    
    # Get bank account code based on payment method
    bank_account_code = GL_BANK_ACCOUNTS.get(payment_method.lower(), "1001")
    
    try:
        # Get bank GL account
        bank_result = await session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == bank_account_code,
                    GLAccount.is_active == True
                )
            )
        )
        bank_account = bank_result.scalar_one_or_none()
        
        if not bank_account:
            raise Exception(f"GL Account {bank_account_code} ({payment_method}) not found or inactive")
        
        # Get revenue GL account
        revenue_result = await session.execute(
            select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.account_code == GL_TRANSPORT_REVENUE,
                    GLAccount.is_active == True
                )
            )
        )
        revenue_account = revenue_result.scalar_one_or_none()
        
        if not revenue_account:
            raise Exception(f"GL Account {GL_TRANSPORT_REVENUE} (Transport Revenue) not found or inactive")
        
        # Get student for description
        student_result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"
        
        # Get route for description
        route_result = await session.execute(
            select(Route).where(Route.id == route_id)
        )
        route = route_result.scalar_one_or_none()
        route_name = route.route_name if route else "Unknown Route"
        
        # Create journal line items
        line_items = [
            # Debit: Bank account (payment received)
            JournalLineItemCreate(
                gl_account_id=bank_account.id,
                debit_amount=float(payment_amount),
                credit_amount=0.0,
                description=f"Transport fee payment from {student_name} ({route_name})"
            ),
            # Credit: Revenue account (fee income)
            JournalLineItemCreate(
                gl_account_id=revenue_account.id,
                debit_amount=0.0,
                credit_amount=float(payment_amount),
                description=f"Transport fee income from {student_name} ({route_name})"
            )
        ]
        
        # Create journal entry
        entry_data = JournalEntryCreate(
            entry_date=datetime.utcnow().isoformat().split('T')[0],
            reference_type=ReferenceType.FEE_PAYMENT,
            reference_id=fee_id,
            description=f"Transport fee payment from {student_name} ({route_name})",
            line_items=line_items,
            notes=f"Auto-posted from transport fee {fee_id} - Payment method: {payment_method}"
        )
        
        # Use JournalEntryService to create and post entry
        journal_service = JournalEntryService(session)
        entry = await journal_service.create_entry(
            school_id=school_id,
            entry_data=entry_data,
            created_by="SYSTEM"
        )
        
        # Post the entry immediately
        posted_entry = await journal_service.post_entry(
            school_id=school_id,
            entry_id=entry.id,
            posted_by="SYSTEM",
            approval_notes="Auto-posted from transport fee payment"
        )
        
        return posted_entry.id
        
    except Exception as e:
        logger.error(f"Error creating transport fee journal entry: {str(e)}")
        raise
