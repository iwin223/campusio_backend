"""Payroll models for salary management and processing"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class PaySchedule(str, Enum):
    """Payment schedule frequency"""
    MONTHLY = "monthly"
    BIWEEKLY = "biweekly"
    WEEKLY = "weekly"


class PayrollStatus(str, Enum):
    """Status of payroll run"""
    DRAFT = "draft"
    GENERATED = "generated"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"


class PayrollCategory(str, Enum):
    """Categories for payroll line items"""
    BASIC_SALARY = "basic_salary"
    ALLOWANCE_HOUSING = "allowance_housing"
    ALLOWANCE_TRANSPORT = "allowance_transport"
    ALLOWANCE_MEALS = "allowance_meals"
    ALLOWANCE_UTILITIES = "allowance_utilities"
    ALLOWANCE_OTHER = "allowance_other"
    TAX_INCOME = "tax_income"
    DEDUCTION_PENSION = "deduction_pension"
    DEDUCTION_NSSF = "deduction_nssf"
    DEDUCTION_LOAN = "deduction_loan"
    DEDUCTION_ADVANCE = "deduction_advance"
    DEDUCTION_OTHER = "deduction_other"


class PayrollContract(SQLModel, table=True):
    """Staff payroll contract - defines salary and deduction rules"""
    __tablename__ = "payroll_contracts"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    basic_salary: float
    pay_schedule: PaySchedule = PaySchedule.MONTHLY
    currency: str = Field(default="GHS")
    
    # Allowances (all optional)
    allowance_housing: float = Field(default=0.0)
    allowance_transport: float = Field(default=0.0)
    allowance_meals: float = Field(default=0.0)
    allowance_utilities: float = Field(default=0.0)
    allowance_other: float = Field(default=0.0)
    allowance_other_description: Optional[str] = None
    
    # Deductions (all optional)
    tax_rate_percent: float = Field(default=0.0)  # Income tax percentage
    pension_rate_percent: float = Field(default=0.0)  # Pension contribution %
    nssf_rate_percent: float = Field(default=0.0)  # NSSF contribution %
    other_deduction: float = Field(default=0.0)
    other_deduction_description: Optional[str] = None
    
    # Contract dates
    effective_from: datetime = Field(index=True)
    effective_to: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True, index=True)
    
    # Audit fields
    created_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PayrollContractCreate(SQLModel):
    """Validation model for creating payroll contracts"""
    staff_id: str
    basic_salary: float
    pay_schedule: PaySchedule = PaySchedule.MONTHLY
    currency: str = "GHS"
    allowance_housing: float = 0.0
    allowance_transport: float = 0.0
    allowance_meals: float = 0.0
    allowance_utilities: float = 0.0
    allowance_other: float = 0.0
    allowance_other_description: Optional[str] = None
    tax_rate_percent: float = 0.0
    pension_rate_percent: float = 0.0
    nssf_rate_percent: float = 0.0
    other_deduction: float = 0.0
    other_deduction_description: Optional[str] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    notes: Optional[str] = None


class PayrollContractUpdate(SQLModel):
    """Validation model for updating payroll contracts"""
    basic_salary: Optional[float] = None
    pay_schedule: Optional[PaySchedule] = None
    allowance_housing: Optional[float] = None
    allowance_transport: Optional[float] = None
    allowance_meals: Optional[float] = None
    allowance_utilities: Optional[float] = None
    allowance_other: Optional[float] = None
    allowance_other_description: Optional[str] = None
    tax_rate_percent: Optional[float] = None
    pension_rate_percent: Optional[float] = None
    nssf_rate_percent: Optional[float] = None
    other_deduction: Optional[float] = None
    other_deduction_description: Optional[str] = None
    effective_to: Optional[datetime] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class PayrollRun(SQLModel, table=True):
    """Monthly/periodic payroll run - aggregates all payroll for a period"""
    __tablename__ = "payroll_runs"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    period_year: int = Field(index=True)
    period_month: int = Field(index=True)
    period_name: str = Field(default="")  # e.g., "January 2026"
    
    status: PayrollStatus = Field(default=PayrollStatus.DRAFT, index=True)
    
    # Totals
    total_gross: float = Field(default=0.0)
    total_allowances: float = Field(default=0.0)
    total_deductions: float = Field(default=0.0)
    total_net: float = Field(default=0.0)
    
    # Staff count
    staff_count: int = Field(default=0)
    
    # Audit fields
    generated_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PayrollRunCreate(SQLModel):
    """Validation model for creating payroll runs"""
    period_year: int
    period_month: int
    notes: Optional[str] = None


class PayrollLineItem(SQLModel, table=True):
    """Individual staff payroll for a payroll run"""
    __tablename__ = "payroll_line_items"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    payroll_run_id: str = Field(index=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    
    # Calculation components
    basic_salary: float
    total_allowances: float
    gross_amount: float
    
    # Deductions breakdown
    tax_amount: float = Field(default=0.0)
    pension_amount: float = Field(default=0.0)
    nssf_amount: float = Field(default=0.0)
    other_deductions: float = Field(default=0.0)
    
    total_deductions: float
    net_amount: float
    
    # JSON field for detailed breakdown (flexibility for future)
    breakdown: Optional[str] = None  # JSON string with itemized breakdown
    
    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PayrollAdjustment(SQLModel, table=True):
    """Manual adjustments to payroll (bonus, penalty, refund, etc.)"""
    __tablename__ = "payroll_adjustments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    payroll_run_id: str = Field(index=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    
    adjustment_type: str  # "bonus", "penalty", "refund", "advance_recovery", etc.
    amount: float
    reason: str
    
    # Audit
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PayrollAdjustmentCreate(SQLModel):
    """Validation model for creating adjustments"""
    staff_id: str
    adjustment_type: str
    amount: float
    reason: str


class PayslipResponse(SQLModel):
    """Response model for payslip view"""
    payroll_run_id: str
    period_name: str
    staff_id: str
    staff_name: str
    
    basic_salary: float
    total_allowances: float
    gross_amount: float
    
    tax_amount: float
    pension_amount: float
    nssf_amount: float
    other_deductions: float
    total_deductions: float
    
    net_amount: float
    currency: str
    
    generated_at: datetime
    posted_at: Optional[datetime] = None
