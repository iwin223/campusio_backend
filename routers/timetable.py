"""Timetable router"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from datetime import datetime
from typing import Optional, List
from models.timetable import Timetable, TimetableCreate, Period, PeriodCreate, DayOfWeek, PeriodType
from models.classroom import Class, Subject
from models.staff import Staff
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles
from services.timetable_pdf_service import TimetablePDFService

router = APIRouter(prefix="/timetable", tags=["Timetable"])

# Default Ghana school periods
DEFAULT_PERIODS = [
    {"name": "Assembly", "period_number": 0, "start_time": "07:30", "end_time": "08:00", "period_type": "assembly"},
    {"name": "Period 1", "period_number": 1, "start_time": "08:00", "end_time": "08:40", "period_type": "lesson"},
    {"name": "Period 2", "period_number": 2, "start_time": "08:40", "end_time": "09:20", "period_type": "lesson"},
    {"name": "Period 3", "period_number": 3, "start_time": "09:20", "end_time": "10:00", "period_type": "lesson"},
    {"name": "Break", "period_number": 4, "start_time": "10:00", "end_time": "10:30", "period_type": "break"},
    {"name": "Period 4", "period_number": 5, "start_time": "10:30", "end_time": "11:10", "period_type": "lesson"},
    {"name": "Period 5", "period_number": 6, "start_time": "11:10", "end_time": "11:50", "period_type": "lesson"},
    {"name": "Period 6", "period_number": 7, "start_time": "11:50", "end_time": "12:30", "period_type": "lesson"},
    {"name": "Lunch", "period_number": 8, "start_time": "12:30", "end_time": "13:30", "period_type": "lunch"},
    {"name": "Period 7", "period_number": 9, "start_time": "13:30", "end_time": "14:10", "period_type": "lesson"},
    {"name": "Period 8", "period_number": 10, "start_time": "14:10", "end_time": "14:50", "period_type": "lesson"},
]


@router.post("/periods/seed-defaults", response_model=dict)
async def seed_default_periods(
    current_user: User = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Seed default Ghana school periods"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Check if periods already exist
    existing = await session.execute(
        select(Period).where(Period.school_id == school_id).limit(1)
    )
    if existing.scalar_one_or_none():
        return {"message": "Periods already exist", "created": 0}
    
    created_count = 0
    for p in DEFAULT_PERIODS:
        period = Period(
            school_id=school_id,
            name=p["name"],
            period_number=p["period_number"],
            start_time=p["start_time"],
            end_time=p["end_time"],
            period_type=PeriodType(p["period_type"])
        )
        session.add(period)
        created_count += 1
    
    await session.commit()
    return {"message": f"Created {created_count} default periods", "created": created_count}


@router.post("/periods", response_model=dict)
async def create_period(
    period_data: PeriodCreate,
    current_user: User = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Create a period definition"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    period = Period(school_id=school_id, **period_data.model_dump())
    session.add(period)
    await session.commit()
    await session.refresh(period)
    
    return {
        "id": period.id,
        "name": period.name,
        "period_number": period.period_number,
        "start_time": period.start_time,
        "end_time": period.end_time,
        "period_type": period.period_type,
        "message": "Period created"
    }


@router.patch("/periods/{period_id}", response_model=dict)
async def update_period(
    period_id: str,
    period_data: PeriodCreate,
    current_user: User = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Update a period definition"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")

    result = await session.execute(
        select(Period).where(
            and_(Period.id == period_id, Period.school_id == school_id, Period.is_active == True)
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    period.name = period_data.name
    period.period_number = period_data.period_number
    period.start_time = period_data.start_time
    period.end_time = period_data.end_time
    period.period_type = period_data.period_type

    session.add(period)
    await session.commit()
    await session.refresh(period)

    return {
        "id": period.id,
        "name": period.name,
        "period_number": period.period_number,
        "start_time": period.start_time,
        "end_time": period.end_time,
        "period_type": period.period_type,
        "message": "Period updated"
    }


@router.delete("/periods/{period_id}", response_model=dict)
async def delete_period(
    period_id: str,
    current_user: User = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Deactivate a period definition"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")

    result = await session.execute(
        select(Period).where(
            and_(Period.id == period_id, Period.school_id == school_id, Period.is_active == True)
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    period.is_active = False
    session.add(period)
    await session.commit()

    return {"message": "Period deleted"}


@router.get("/periods", response_model=list[dict])
async def list_periods(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List all period definitions"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "period_number": p.period_number,
            "start_time": p.start_time,
            "end_time": p.end_time,
            "period_type": p.period_type
        }
        for p in periods
    ]


@router.post("", response_model=dict)
async def create_timetable_entry(
    timetable_data: TimetableCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a timetable entry"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    existing = await session.execute(
        select(Timetable).where(
            Timetable.school_id == school_id,
            Timetable.class_id == timetable_data.class_id,
            Timetable.period_id == timetable_data.period_id,
            Timetable.day_of_week == timetable_data.day_of_week,
            Timetable.academic_term_id == timetable_data.academic_term_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Time slot already occupied for this class")
    
    timetable = Timetable(school_id=school_id, **timetable_data.model_dump())
    session.add(timetable)
    await session.commit()
    await session.refresh(timetable)
    
    return {
        "id": timetable.id,
        "class_id": timetable.class_id,
        "subject_id": timetable.subject_id,
        "teacher_id": timetable.teacher_id,
        "day_of_week": timetable.day_of_week,
        "message": "Timetable entry created"
    }


@router.get("/class/{class_id}", response_model=dict)
async def get_class_timetable(
    class_id: str,
    academic_term_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get weekly timetable for a class"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}
    
    result = await session.execute(
        select(Timetable).where(
            Timetable.class_id == class_id,
            Timetable.academic_term_id == academic_term_id
        )
    )
    entries = result.scalars().all()
    
    subject_ids = list(set(e.subject_id for e in entries))
    teacher_ids = list(set(e.teacher_id for e in entries))
    
    subjects = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subject_result.scalars().all()}
    
    teachers = {}
    if teacher_ids:
        teacher_result = await session.execute(select(Staff).where(Staff.id.in_(teacher_ids)))
        teachers = {t.id: t for t in teacher_result.scalars().all()}
    
    schedule = {day.value: [] for day in DayOfWeek}
    
    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        teacher = teachers.get(entry.teacher_id)
        
        schedule[entry.day_of_week.value].append({
            "id": entry.id,
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_id": entry.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "teacher_id": entry.teacher_id,
            "teacher_name": f"{teacher.first_name} {teacher.last_name}" if teacher else "Unknown",
            "room": entry.room
        })
    
    for day in schedule:
        schedule[day].sort(key=lambda x: x["period_number"])
    
    return {
        "class_id": class_id,
        "class_name": cls.name,
        "academic_term_id": academic_term_id,
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "period_number": p.period_number,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "period_type": p.period_type
            }
            for p in sorted(periods.values(), key=lambda x: x.period_number)
        ],
        "schedule": schedule
    }


@router.delete("/{entry_id}", response_model=dict)
async def delete_timetable_entry(
    entry_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Delete a timetable entry"""
    result = await session.execute(select(Timetable).where(Timetable.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != entry.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await session.delete(entry)
    await session.commit()
    
    return {"message": "Timetable entry deleted"}



@router.get("/teacher/{teacher_id}", response_model=dict)
async def get_teacher_timetable(
    teacher_id: str,
    academic_term_id: str = "term_1_2026",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get weekly timetable for a teacher"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get teacher info
    teacher_result = await session.execute(select(Staff).where(Staff.id == teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Get periods
    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}
    
    # Get timetable entries for this teacher
    result = await session.execute(
        select(Timetable).where(
            Timetable.teacher_id == teacher_id,
            Timetable.academic_term_id == academic_term_id
        )
    )
    entries = result.scalars().all()
    
    # Get subjects and classes
    subject_ids = list(set(e.subject_id for e in entries))
    class_ids = list(set(e.class_id for e in entries))
    
    subjects = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subject_result.scalars().all()}
    
    classes = {}
    if class_ids:
        class_result = await session.execute(select(Class).where(Class.id.in_(class_ids)))
        classes = {c.id: c for c in class_result.scalars().all()}
    
    # Build schedule
    schedule = {day.value: [] for day in DayOfWeek}
    
    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        cls = classes.get(entry.class_id)
        
        schedule[entry.day_of_week.value].append({
            "id": entry.id,
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_id": entry.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "class_id": entry.class_id,
            "class_name": cls.name if cls else "Unknown",
            "room": entry.room
        })
    
    for day in schedule:
        schedule[day].sort(key=lambda x: x["period_number"])
    
    return {
        "teacher_id": teacher_id,
        "teacher_name": f"{teacher.first_name} {teacher.last_name}",
        "academic_term_id": academic_term_id,
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "period_number": p.period_number,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "period_type": p.period_type
            }
            for p in sorted(periods.values(), key=lambda x: x.period_number)
        ],
        "schedule": schedule,
        "total_periods_per_week": len(entries)
    }


@router.get("/my-schedule", response_model=dict)
async def get_my_timetable(
    academic_term_id: str = "term_1_2026",
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Get weekly timetable for current teacher"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get periods
    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}
    
    # Get timetable entries for current teacher
    result = await session.execute(
        select(Timetable).where(
            Timetable.teacher_id == current_user.id,
            Timetable.academic_term_id == academic_term_id
        )
    )
    entries = result.scalars().all()
    
    # Get subjects and classes
    subject_ids = list(set(e.subject_id for e in entries))
    class_ids = list(set(e.class_id for e in entries))
    
    subjects = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subject_result.scalars().all()}
    
    classes = {}
    if class_ids:
        class_result = await session.execute(select(Class).where(Class.id.in_(class_ids)))
        classes = {c.id: c for c in class_result.scalars().all()}
    
    # Build schedule organized by day
    timetable = {day.value: [] for day in DayOfWeek}
    
    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        cls = classes.get(entry.class_id)
        
        timetable[entry.day_of_week.value].append({
            "id": entry.id,
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_id": entry.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "class_id": entry.class_id,
            "class_name": cls.name if cls else "Unknown",
            "room": entry.room
        })
    
    # Sort each day by period number
    for day in timetable:
        timetable[day].sort(key=lambda x: x["period_number"])
    
    return {
        "timetable": timetable,
        "message": "success" if timetable else "No classes assigned"
    }


@router.post("/bulk", response_model=dict)
async def create_bulk_timetable_entries(
    entries: List[TimetableCreate],
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create multiple timetable entries at once"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    created_count = 0
    skipped_count = 0
    
    for entry_data in entries:
        # Check for existing entry
        existing = await session.execute(
            select(Timetable).where(
                Timetable.school_id == school_id,
                Timetable.class_id == entry_data.class_id,
                Timetable.period_id == entry_data.period_id,
                Timetable.day_of_week == entry_data.day_of_week,
                Timetable.academic_term_id == entry_data.academic_term_id
            )
        )
        if existing.scalar_one_or_none():
            skipped_count += 1
            continue
        
        timetable = Timetable(school_id=school_id, **entry_data.model_dump())
        session.add(timetable)
        created_count += 1
    
    await session.commit()
    
    return {
        "message": f"Created {created_count} entries, skipped {skipped_count} (already exist)",
        "created": created_count,
        "skipped": skipped_count
    }


@router.get("/days", response_model=List[str])
async def get_days_of_week():
    """Get list of school days"""
    return [day.value for day in DayOfWeek]


# PDF Export Endpoints
pdf_service = TimetablePDFService()

@router.get("/class/{class_id}/export-pdf")
async def export_class_timetable_pdf(
    class_id: str,
    academic_term_id: str = "term_1_2026",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Export class timetable as PDF"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")

    # Get timetable data (reuse existing logic)
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}

    result = await session.execute(
        select(Timetable).where(
            Timetable.class_id == class_id,
            Timetable.academic_term_id == academic_term_id
        )
    )
    entries = result.scalars().all()

    subject_ids = list(set(e.subject_id for e in entries))
    teacher_ids = list(set(e.teacher_id for e in entries))

    subjects = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subject_result.scalars().all()}

    teachers = {}
    if teacher_ids:
        teacher_result = await session.execute(select(Staff).where(Staff.id.in_(teacher_ids)))
        teachers = {t.id: t for t in teacher_result.scalars().all()}

    schedule = {day.value: [] for day in DayOfWeek}

    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        teacher = teachers.get(entry.teacher_id)

        schedule[entry.day_of_week.value].append({
            "id": entry.id,
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_id": entry.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "teacher_id": entry.teacher_id,
            "teacher_name": f"{teacher.first_name} {teacher.last_name}" if teacher else "Unknown",
            "room": entry.room
        })

    for day in schedule:
        schedule[day].sort(key=lambda x: x["period_number"])

    timetable_data = {
        "class_id": class_id,
        "class_name": cls.name,
        "academic_term_id": academic_term_id,
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "period_number": p.period_number,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "period_type": p.period_type
            }
            for p in sorted(periods.values(), key=lambda x: x.period_number)
        ],
        "schedule": schedule
    }

    # Format for PDF
    formatted_data = pdf_service.format_timetable_for_pdf(timetable_data)

    # Generate PDF
    pdf_bytes = pdf_service.generate_pdf(formatted_data)

    # Return PDF response
    filename = f"class_timetable_{cls.name.replace(' ', '_')}_{academic_term_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/teacher/{teacher_id}/export-pdf")
async def export_teacher_timetable_pdf(
    teacher_id: str,
    academic_term_id: str = "term_1_2026",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Export teacher timetable as PDF"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")

    # Get teacher info
    teacher_result = await session.execute(select(Staff).where(Staff.id == teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Get periods
    periods_result = await session.execute(
        select(Period).where(
            Period.school_id == school_id,
            Period.is_active == True
        ).order_by(Period.period_number)
    )
    periods = {p.id: p for p in periods_result.scalars().all()}

    # Get timetable entries for this teacher
    result = await session.execute(
        select(Timetable).where(
            Timetable.teacher_id == teacher_id,
            Timetable.academic_term_id == academic_term_id
        )
    )
    entries = result.scalars().all()

    # Get subjects and classes
    subject_ids = list(set(e.subject_id for e in entries))
    class_ids = list(set(e.class_id for e in entries))

    subjects = {}
    if subject_ids:
        subject_result = await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
        subjects = {s.id: s for s in subject_result.scalars().all()}

    classes = {}
    if class_ids:
        class_result = await session.execute(select(Class).where(Class.id.in_(class_ids)))
        classes = {c.id: c for c in class_result.scalars().all()}

    # Build schedule
    schedule = {day.value: [] for day in DayOfWeek}

    for entry in entries:
        period = periods.get(entry.period_id)
        subject = subjects.get(entry.subject_id)
        cls = classes.get(entry.class_id)

        schedule[entry.day_of_week.value].append({
            "id": entry.id,
            "period_id": entry.period_id,
            "period_name": period.name if period else "Unknown",
            "period_number": period.period_number if period else 0,
            "start_time": period.start_time if period else "",
            "end_time": period.end_time if period else "",
            "subject_id": entry.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "class_id": entry.class_id,
            "class_name": cls.name if cls else "Unknown",
            "room": entry.room
        })

    for day in schedule:
        schedule[day].sort(key=lambda x: x["period_number"])

    timetable_data = {
        "teacher_id": teacher_id,
        "teacher_name": f"{teacher.first_name} {teacher.last_name}",
        "academic_term_id": academic_term_id,
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "period_number": p.period_number,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "period_type": p.period_type
            }
            for p in sorted(periods.values(), key=lambda x: x.period_number)
        ],
        "schedule": schedule,
        "total_periods_per_week": len(entries)
    }

    # Format for PDF
    formatted_data = pdf_service.format_timetable_for_pdf(timetable_data)

    # Generate PDF
    pdf_bytes = pdf_service.generate_pdf(formatted_data)

    # Return PDF response
    filename = f"teacher_timetable_{teacher.first_name}_{teacher.last_name}_{academic_term_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
