"""Fees router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
import uuid
from models.fee import Fee, FeeCreate, FeeStructure, FeeStructureCreate, FeePayment, FeePaymentCreate, PaymentStatus, PaymentMethod, FeeType
from models.student import Student
from models.classroom import Class
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/fees", tags=["Fees & Payments"])


# Fee Types with descriptions
FEE_TYPES_INFO = [
    {"type": "tuition", "name": "Tuition Fee", "description": "Main school fees for academic instruction"},
    {"type": "examination", "name": "Examination Fee", "description": "Fees for mid-term and end-of-term exams"},
    {"type": "sports", "name": "Sports Fee", "description": "Sports and physical education activities"},
    {"type": "ict", "name": "ICT Fee", "description": "Computer lab and IT resources"},
    {"type": "library", "name": "Library Fee", "description": "Library access and resources"},
    {"type": "maintenance", "name": "Maintenance Fee", "description": "School facilities maintenance"},
    {"type": "pta", "name": "PTA Levy", "description": "Parent-Teacher Association contributions"},
    {"type": "other", "name": "Other", "description": "Miscellaneous fees"},
]


@router.get("/types", response_model=List[dict])
async def get_fee_types():
    """Get all available fee types with descriptions"""
    return FEE_TYPES_INFO


@router.get("/summary", response_model=dict)
async def get_fee_summary(
    academic_term_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get fee collection summary for the school"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Fee).where(Fee.school_id == school_id)
    if academic_term_id:
        query = query.where(Fee.academic_term_id == academic_term_id)
    
    result = await session.execute(query)
    fees = result.scalars().all()
    
    total_expected = sum(f.amount_due for f in fees)
    total_collected = sum(f.amount_paid for f in fees)
    total_discount = sum(f.discount for f in fees)
    total_outstanding = total_expected - total_collected - total_discount
    
    # Count by status
    status_counts = {
        "paid": sum(1 for f in fees if f.status == PaymentStatus.PAID),
        "partial": sum(1 for f in fees if f.status == PaymentStatus.PARTIAL),
        "pending": sum(1 for f in fees if f.status == PaymentStatus.PENDING),
        "overdue": sum(1 for f in fees if f.status == PaymentStatus.OVERDUE),
    }
    
    collection_rate = round((total_collected / total_expected * 100) if total_expected > 0 else 0, 1)
    
    return {
        "total_expected": total_expected,
        "total_collected": total_collected,
        "total_discount": total_discount,
        "total_outstanding": total_outstanding,
        "collection_rate": collection_rate,
        "total_students_with_fees": len(set(f.student_id for f in fees)),
        "status_breakdown": status_counts
    }


@router.get("/outstanding", response_model=dict)
async def get_outstanding_fees(
    class_id: Optional[str] = None,
    min_amount: float = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get students with outstanding fees"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get fees that are not fully paid
    query = select(Fee).where(
        Fee.school_id == school_id,
        Fee.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE])
    )
    
    result = await session.execute(query)
    fees = result.scalars().all()
    
    # Group by student
    student_balances = {}
    for fee in fees:
        balance = fee.amount_due - fee.amount_paid - fee.discount
        if balance > min_amount:
            if fee.student_id not in student_balances:
                student_balances[fee.student_id] = {
                    "student_id": fee.student_id,
                    "total_due": 0,
                    "total_paid": 0,
                    "balance": 0,
                    "fee_count": 0
                }
            student_balances[fee.student_id]["total_due"] += fee.amount_due
            student_balances[fee.student_id]["total_paid"] += fee.amount_paid
            student_balances[fee.student_id]["balance"] += balance
            student_balances[fee.student_id]["fee_count"] += 1
    
    # Get student details
    student_ids = list(student_balances.keys())
    if student_ids:
        students_result = await session.execute(
            select(Student).where(Student.id.in_(student_ids))
        )
        students = {s.id: s for s in students_result.scalars().all()}
        
        # Filter by class if specified
        for sid, data in student_balances.items():
            student = students.get(sid)
            if student:
                if class_id and student.class_id != class_id:
                    continue
                data["student_name"] = f"{student.first_name} {student.last_name}"
                data["student_number"] = student.student_id
                data["class_id"] = student.class_id
    
    outstanding_list = sorted(
        [v for v in student_balances.values() if "student_name" in v],
        key=lambda x: x["balance"],
        reverse=True
    )
    
    return {
        "total_students": len(outstanding_list),
        "total_outstanding": sum(s["balance"] for s in outstanding_list),
        "students": outstanding_list
    }


@router.post("/structures", response_model=dict)
async def create_fee_structure(
    structure_data: FeeStructureCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a fee structure"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    structure = FeeStructure(school_id=school_id, **structure_data.model_dump())
    session.add(structure)
    await session.commit()
    await session.refresh(structure)
    
    return {
        "id": structure.id,
        "academic_term_id": structure.academic_term_id,
        "class_level": structure.class_level,
        "fee_type": structure.fee_type,
        "amount": structure.amount,
        "due_date": structure.due_date,
        "message": "Fee structure created"
    }


@router.get("/structures", response_model=list[dict])
async def list_fee_structures(
    academic_term_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List fee structures"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(FeeStructure).where(FeeStructure.school_id == school_id)
    
    if academic_term_id:
        query = query.where(FeeStructure.academic_term_id == academic_term_id)
    
    result = await session.execute(query)
    structures = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "academic_term_id": s.academic_term_id,
            "class_level": s.class_level,
            "fee_type": s.fee_type,
            "amount": s.amount,
            "description": s.description,
            "is_mandatory": s.is_mandatory,
            "due_date": s.due_date
        }
        for s in structures
    ]


@router.post("", response_model=dict)
async def create_student_fee(
    fee_data: FeeCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Create a fee record for a student"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    fee = Fee(school_id=school_id, **fee_data.model_dump())
    session.add(fee)
    await session.commit()
    await session.refresh(fee)
    
    return {
        "id": fee.id,
        "student_id": fee.student_id,
        "amount_due": fee.amount_due,
        "status": fee.status,
        "message": "Fee created"
    }


@router.get("/student/{student_id}", response_model=dict)
async def get_student_fees(
    student_id: str,
    academic_term_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all fees for a student"""
    student_result = await session.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = select(Fee).where(Fee.student_id == student_id)
    
    if academic_term_id:
        query = query.where(Fee.academic_term_id == academic_term_id)
    
    result = await session.execute(query)
    fees = result.scalars().all()
    
    structure_ids = [f.fee_structure_id for f in fees]
    structures = {}
    if structure_ids:
        structure_result = await session.execute(
            select(FeeStructure).where(FeeStructure.id.in_(structure_ids))
        )
        for s in structure_result.scalars().all():
            structures[s.id] = s
    
    fee_list = []
    for fee in fees:
        structure = structures.get(fee.fee_structure_id)
        fee_list.append({
            "id": fee.id,
            "fee_type": structure.fee_type if structure else "unknown",
            "description": structure.description if structure else "N/A",
            "amount_due": fee.amount_due,
            "amount_paid": fee.amount_paid,
            "balance": fee.amount_due - fee.amount_paid - fee.discount,
            "discount": fee.discount,
            "status": fee.status,
            "due_date": structure.due_date if structure else None
        })
    
    total_due = sum(f["amount_due"] for f in fee_list)
    total_paid = sum(f["amount_paid"] for f in fee_list)
    total_discount = sum(f["discount"] for f in fee_list)
    
    return {
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "summary": {
            "total_fees": total_due,
            "total_paid": total_paid,
            "total_discount": total_discount,
            "balance": total_due - total_paid - total_discount
        },
        "fees": fee_list
    }


@router.post("/payments", response_model=dict)
async def record_payment(
    payment_data: FeePaymentCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Record a fee payment"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    fee_result = await session.execute(select(Fee).where(Fee.id == payment_data.fee_id))
    fee = fee_result.scalar_one_or_none()
    
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    
    receipt_number = f"RCP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    payment = FeePayment(
        school_id=school_id,
        fee_id=payment_data.fee_id,
        student_id=fee.student_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        reference_number=payment_data.reference_number,
        receipt_number=receipt_number,
        payment_date=payment_data.payment_date,
        remarks=payment_data.remarks,
        received_by=current_user.id
    )
    session.add(payment)
    
    fee.amount_paid += payment_data.amount
    balance = fee.amount_due - fee.amount_paid - fee.discount
    
    if balance <= 0:
        fee.status = PaymentStatus.PAID
    else:
        fee.status = PaymentStatus.PARTIAL
    
    fee.updated_at = datetime.utcnow()
    session.add(fee)
    
    await session.commit()
    await session.refresh(payment)
    
    return {
        "id": payment.id,
        "receipt_number": receipt_number,
        "amount": payment.amount,
        "fee_balance": balance,
        "fee_status": fee.status,
        "message": "Payment recorded successfully"
    }


@router.get("/payments/student/{student_id}", response_model=list[dict])
async def get_student_payments(
    student_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payment history for a student"""
    result = await session.execute(
        select(FeePayment).where(FeePayment.student_id == student_id).order_by(FeePayment.payment_date.desc())
    )
    payments = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "fee_id": p.fee_id,
            "amount": p.amount,
            "payment_method": p.payment_method,
            "reference_number": p.reference_number,
            "receipt_number": p.receipt_number,
            "payment_date": p.payment_date,
            "remarks": p.remarks,
            "created_at": p.created_at.isoformat()
        }
        for p in payments
    ]



@router.post("/assign-class", response_model=dict)
async def assign_fee_to_class(
    structure_id: str,
    class_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Assign a fee structure to all students in a class"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get fee structure
    structure_result = await session.execute(
        select(FeeStructure).where(FeeStructure.id == structure_id)
    )
    structure = structure_result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    
    # Get students in class
    students_result = await session.execute(
        select(Student).where(
            Student.class_id == class_id,
            Student.school_id == school_id,
            Student.status == "active"
        )
    )
    students = students_result.scalars().all()
    
    if not students:
        raise HTTPException(status_code=404, detail="No students found in class")
    
    # Check for existing fee assignments
    existing_result = await session.execute(
        select(Fee.student_id).where(
            Fee.fee_structure_id == structure_id,
            Fee.student_id.in_([s.id for s in students])
        )
    )
    existing_ids = set(existing_result.scalars().all())
    
    created_count = 0
    for student in students:
        if student.id not in existing_ids:
            fee = Fee(
                school_id=school_id,
                student_id=student.id,
                academic_term_id=structure.academic_term_id,
                fee_structure_id=structure_id,
                amount_due=structure.amount,
                status=PaymentStatus.PENDING
            )
            session.add(fee)
            created_count += 1
    
    await session.commit()
    
    return {
        "message": f"Fee assigned to {created_count} students",
        "total_students": len(students),
        "new_assignments": created_count,
        "already_assigned": len(existing_ids)
    }


@router.get("/class/{class_id}", response_model=dict)
async def get_class_fee_status(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get fee collection status for a class"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Get class info
    class_result = await session.execute(select(Class).where(Class.id == class_id))
    classroom = class_result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Get students in class
    students_result = await session.execute(
        select(Student).where(
            Student.class_id == class_id,
            Student.status == "active"
        ).order_by(Student.last_name, Student.first_name)
    )
    students = students_result.scalars().all()
    student_ids = [s.id for s in students]
    
    # Get all fees for these students
    fees_result = await session.execute(
        select(Fee).where(Fee.student_id.in_(student_ids)) if student_ids else select(Fee).where(False)
    )
    fees = fees_result.scalars().all()
    
    # Get fee structures
    structure_ids = list(set(f.fee_structure_id for f in fees))
    structures = {}
    if structure_ids:
        struct_result = await session.execute(
            select(FeeStructure).where(FeeStructure.id.in_(structure_ids))
        )
        structures = {s.id: s for s in struct_result.scalars().all()}
    
    # Group fees by student
    student_fees = {s.id: [] for s in students}
    for fee in fees:
        if fee.student_id in student_fees:
            student_fees[fee.student_id].append(fee)
    
    # Build response
    students_data = []
    class_total_due = 0
    class_total_paid = 0
    
    for student in students:
        student_fee_list = student_fees.get(student.id, [])
        total_due = sum(f.amount_due for f in student_fee_list)
        total_paid = sum(f.amount_paid for f in student_fee_list)
        total_discount = sum(f.discount for f in student_fee_list)
        balance = total_due - total_paid - total_discount
        
        class_total_due += total_due
        class_total_paid += total_paid
        
        # Determine overall status
        if not student_fee_list:
            status = "no_fees"
        elif balance <= 0:
            status = "paid"
        elif total_paid > 0:
            status = "partial"
        else:
            status = "pending"
        
        students_data.append({
            "student_id": student.id,
            "student_name": f"{student.first_name} {student.last_name}",
            "student_number": student.student_id,
            "total_due": total_due,
            "total_paid": total_paid,
            "balance": balance,
            "status": status,
            "fee_count": len(student_fee_list)
        })
    
    return {
        "class_id": class_id,
        "class_name": classroom.name,
        "total_students": len(students),
        "class_summary": {
            "total_due": class_total_due,
            "total_paid": class_total_paid,
            "balance": class_total_due - class_total_paid,
            "collection_rate": round((class_total_paid / class_total_due * 100) if class_total_due > 0 else 0, 1)
        },
        "students": students_data
    }


@router.get("/receipt/{payment_id}", response_model=dict)
async def get_payment_receipt(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get payment receipt details"""
    payment_result = await session.execute(
        select(FeePayment).where(FeePayment.id == payment_id)
    )
    payment = payment_result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Get student info
    student_result = await session.execute(
        select(Student).where(Student.id == payment.student_id)
    )
    student = student_result.scalar_one_or_none()
    
    # Get fee and structure info
    fee_result = await session.execute(
        select(Fee).where(Fee.id == payment.fee_id)
    )
    fee = fee_result.scalar_one_or_none()
    
    structure = None
    if fee:
        struct_result = await session.execute(
            select(FeeStructure).where(FeeStructure.id == fee.fee_structure_id)
        )
        structure = struct_result.scalar_one_or_none()
    
    return {
        "receipt_number": payment.receipt_number,
        "payment_date": payment.payment_date,
        "amount": payment.amount,
        "payment_method": payment.payment_method,
        "reference_number": payment.reference_number,
        "student": {
            "id": student.id if student else None,
            "name": f"{student.first_name} {student.last_name}" if student else "Unknown",
            "student_id": student.student_id if student else None
        },
        "fee_type": structure.fee_type if structure else "unknown",
        "fee_description": structure.description if structure else None,
        "remarks": payment.remarks,
        "created_at": payment.created_at.isoformat()
    }
