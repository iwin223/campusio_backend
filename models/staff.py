"""Staff and Teacher models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class StaffType(str, Enum):
    TEACHING = "teaching"
    NON_TEACHING = "non_teaching"
    ADMIN = "admin"


class StaffStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"
    TERMINATED = "terminated"


class Staff(SQLModel, table=True):
    __tablename__ = "staff"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    email: str
    phone: str
    date_of_birth: str
    gender: str
    staff_type: StaffType
    position: str
    department: Optional[str] = None
    qualification: Optional[str] = None
    date_joined: str
    address: Optional[str] = None
    photo_url: Optional[str] = None
    status: StaffStatus = StaffStatus.ACTIVE
    user_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StaffCreate(SQLModel):
    staff_id: str
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    email: str
    phone: str
    date_of_birth: str
    gender: str
    staff_type: StaffType
    position: str
    department: Optional[str] = None
    qualification: Optional[str] = None
    date_joined: str
    address: Optional[str] = None
    photo_url: Optional[str] = None


class TeacherAssignment(SQLModel, table=True):
    __tablename__ = "teacher_assignments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    class_id: str = Field(index=True)
    subject_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
    is_class_teacher: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
