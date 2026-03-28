"""Transport Management Router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.encoders import jsonable_encoder
from sqlmodel import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
import uuid
import json
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

router = APIRouter(prefix="/transport", tags=["Transport Management"])


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
    
    return [jsonable_encoder(e) for e in enrollments]


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
    
    fee = TransportFee(
        **fee_data.dict(),
        school_id=school_id
    )
    session.add(fee)
    await session.commit()
    await session.refresh(fee)
    
    return {
        **jsonable_encoder(fee),
        "fee_type": fee.fee_type.value
    }


@router.get("/fees/{student_id}", response_model=List[dict])
async def get_student_transport_fees(
    student_id: str,
    is_paid: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get transport fees for a student"""
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
    
    return [
        {
            **jsonable_encoder(f),
            "fee_type": f.fee_type.value
        }
        for f in fees
    ]


@router.put("/fees/{fee_id}", response_model=dict)
async def update_transport_fee(
    fee_id: str,
    fee_data: TransportFeeUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Update transport fee payment status"""
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
    
    return {
        **jsonable_encoder(fee),
        "fee_type": fee.fee_type.value
    }


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
    await session.commit()
    await session.refresh(driver)
    
    return jsonable_encoder(driver)


@router.get("/drivers", response_model=List[dict])
async def list_drivers(
    role: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all drivers and conductors"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(DriverStaff).where(DriverStaff.school_id == school_id)
    
    if role:
        query = query.where(DriverStaff.role == role)
    if is_active is not None:
        query = query.where(DriverStaff.is_active == is_active)
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    drivers = result.scalars().all()
    
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
