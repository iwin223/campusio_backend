"""School and Academic Term models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class SchoolType(str, Enum):
    BASIC = "basic"
    JHS = "jhs"
    COMBINED = "combined"


class School(SQLModel, table=True):
    __tablename__ = "schools"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    code: str = Field(unique=True, index=True)
    school_type: SchoolType
    address: str
    city: str
    region: str
    phone: str
    email: str
    logo_url: Optional[str] = None
    motto: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SchoolCreate(SQLModel):
    name: str
    code: str
    school_type: SchoolType
    address: str
    city: str
    region: str
    phone: str
    email: str
    logo_url: Optional[str] = None
    motto: Optional[str] = None


class SchoolUpdate(SQLModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    motto: Optional[str] = None
    is_active: Optional[bool] = None


class TermType(str, Enum):
    FIRST = "first"
    SECOND = "second"
    THIRD = "third"


class AcademicTerm(SQLModel, table=True):
    __tablename__ = "academic_terms"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    academic_year: str
    term: TermType
    start_date: str
    end_date: str
    is_current: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AcademicTermCreate(SQLModel):
    academic_year: str
    term: TermType
    start_date: str
    end_date: str
    is_current: bool = False


class AcademicTermUpdate(SQLModel):
    academic_year: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
