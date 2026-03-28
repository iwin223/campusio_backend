"""Fee and Payment models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class FeeType(str, Enum):
    TUITION = "tuition"
    EXAMINATION = "examination"
    SPORTS = "sports"
    ICT = "ict"
    LIBRARY = "library"
    MAINTENANCE = "maintenance"
    PTA = "pta"
    OTHER = "other"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


class PaymentMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    CHEQUE = "cheque"


class FeeStructure(SQLModel, table=True):
    __tablename__ = "fee_structures"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
    class_level: str
    fee_type: FeeType
    amount: float
    description: Optional[str] = None
    is_mandatory: bool = True
    due_date: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeeStructureCreate(SQLModel):
    academic_term_id: str
    class_level: str
    fee_type: FeeType
    amount: float
    description: Optional[str] = None
    is_mandatory: bool = True
    due_date: str


class Fee(SQLModel, table=True):
    __tablename__ = "fees"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
    fee_structure_id: str = Field(index=True)
    amount_due: float
    amount_paid: float = 0
    discount: float = 0
    discount_reason: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FeeCreate(SQLModel):
    student_id: str
    academic_term_id: str
    fee_structure_id: str
    amount_due: float
    discount: float = 0
    discount_reason: Optional[str] = None


class FeePayment(SQLModel, table=True):
    __tablename__ = "fee_payments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    fee_id: str = Field(index=True)
    student_id: str = Field(index=True)
    amount: float
    payment_method: PaymentMethod
    reference_number: Optional[str] = None
    receipt_number: str
    payment_date: str
    remarks: Optional[str] = None
    received_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeePaymentCreate(SQLModel):
    fee_id: str
    amount: float
    payment_method: PaymentMethod
    reference_number: Optional[str] = None
    payment_date: str
    remarks: Optional[str] = None
