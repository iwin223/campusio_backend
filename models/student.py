"""Student and Parent models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class StudentStatus(str, Enum):
    ACTIVE = "active"
    GRADUATED = "graduated"
    TRANSFERRED = "transferred"
    WITHDRAWN = "withdrawn"


class Student(SQLModel, table=True):
    __tablename__ = "students"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)  # School-specific ID
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    date_of_birth: str
    gender: Gender
    admission_date: str
    class_id: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = None
    nationality: str = "Ghanaian"
    religion: Optional[str] = None
    blood_group: Optional[str] = None
    medical_conditions: Optional[str] = None
    photo_url: Optional[str] = None
    status: StudentStatus = StudentStatus.ACTIVE
    user_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudentCreate(SQLModel):
    student_id: str
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    date_of_birth: str
    gender: Gender
    admission_date: str
    class_id: Optional[str] = None
    address: Optional[str] = None
    nationality: str = "Ghanaian"
    religion: Optional[str] = None
    blood_group: Optional[str] = None
    medical_conditions: Optional[str] = None
    photo_url: Optional[str] = None


class Parent(SQLModel, table=True):
    __tablename__ = "parents"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    first_name: str
    last_name: str
    relationship: str
    phone: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[str] = None
    is_emergency_contact: bool = False
    user_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParentCreate(SQLModel):
    first_name: str
    last_name: str
    relationship: str
    phone: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[str] = None
    is_emergency_contact: bool = False


class StudentParent(SQLModel, table=True):
    __tablename__ = "student_parents"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    student_id: str = Field(index=True)
    parent_id: str = Field(index=True)
