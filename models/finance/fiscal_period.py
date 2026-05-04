"""Fiscal Period models for accounting period management

Fiscal periods represent accounting periods (month, quarter, year) during which
transactions can be posted. Periods can be closed to prevent further postings
and enforce audit procedures.
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class FiscalPeriodStatus(str, Enum):
    """Status of a fiscal period in its lifecycle"""
    OPEN = "open"              # Transactions can be posted to this period
    LOCKED = "locked"          # Period audit is complete, no new postings but data visible
    CLOSED = "closed"          # Period is finalized and archived, no modifications allowed
    ARCHIVED = "archived"      # Moved to archive for historical records


class FiscalPeriodType(str, Enum):
    """Type of fiscal period"""
    MONTHLY = "monthly"        # Month (standard for schools)
    QUARTERLY = "quarterly"    # Quarter (3 months)
    SEMI_ANNUAL = "semi_annual"  # 6 months
    ANNUAL = "annual"          # Full fiscal year


class FiscalPeriod(SQLModel, table=True):
    """Fiscal accounting period - controls posting windows
    
    Fiscal periods define the timeframes during which transactions can be posted.
    Each period has a lifecycle:
    1. OPEN - Transactions can be posted
    2. LOCKED - Period audit complete, ready for closing entries
    3. CLOSED - Closing entries posted, period finalized
    4. ARCHIVED - Moved to archive for historical access
    
    Properties:
    - No transactions can be posted to LOCKED or CLOSED periods
    - Period close procedures (closing entries, RE calc) happen during OPEN→LOCKED→CLOSED
    - Multiple periods can be created (monthly, quarterly, annual)
    """
    __tablename__ = "fiscal_periods"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Period identification
    period_name: str  # "March 2026", "Q1 2026", "FY 2026"
    period_type: FiscalPeriodType = Field(index=True)
    
    # Date range
    start_date: datetime = Field(index=True)  # First day of period
    end_date: datetime = Field(index=True)    # Last day of period
    fiscal_year: int = Field(index=True)      # Fiscal year for grouping (e.g., 2026)
    
    # Status and control
    status: FiscalPeriodStatus = Field(default=FiscalPeriodStatus.OPEN, index=True)
    allow_posting: bool = Field(default=True)  # Can transactions be posted?
    allow_adjustment_entries: bool = Field(default=True)  # Can adj entries be posted?
    
    # Control flags
    is_current_period: bool = Field(default=False)  # Is this the current posting period?
    
    # Status tracking
    status_changed_by: Optional[str] = None  # User who changed status
    status_changed_date: Optional[datetime] = None  # When status changed
    
    # Audit trail
    locked_date: Optional[datetime] = None  # When period was locked
    locked_by: Optional[str] = None  # Who locked it
    closed_date: Optional[datetime] = None  # When period was closed
    closed_by: Optional[str] = None  # Who closed it
    archived_date: Optional[datetime] = None  # When archived
    
    # Details
    notes: Optional[str] = None  # Notes about this period (closing issues, etc)
    
    # Timestamps
    created_by: str  # Who created this period
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """Ensure fiscal year + type is unique per school"""
        # Index on (school_id, fiscal_year, period_type) for uniqueness
        pass


class FiscalPeriodCreate(SQLModel):
    """Validation model for creating fiscal periods"""
    period_name: str
    period_type: FiscalPeriodType = FiscalPeriodType.MONTHLY
    start_date: datetime
    end_date: datetime
    fiscal_year: int
    notes: Optional[str] = None


class FiscalPeriodUpdate(SQLModel):
    """Validation model for updating fiscal periods"""
    period_name: Optional[str] = None
    notes: Optional[str] = None
    allow_adjustment_entries: Optional[bool] = None


class FiscalPeriodStatusChange(SQLModel):
    """Model for changing period status (lock/close/archive)"""
    status: FiscalPeriodStatus
    notes: Optional[str] = None


class FiscalPeriodResponse(SQLModel):
    """Response model for fiscal period queries"""
    id: str
    school_id: str
    period_name: str
    period_type: FiscalPeriodType
    start_date: datetime
    end_date: datetime
    fiscal_year: int
    status: FiscalPeriodStatus
    allow_posting: bool
    allow_adjustment_entries: bool
    is_current_period: bool
    locked_date: Optional[datetime]
    closed_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
