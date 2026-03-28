"""Attendance models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class Attendance(SQLModel, table=True):
    __tablename__ = "attendance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    class_id: str = Field(index=True)
    attendance_date: str = Field(index=True)
    status: AttendanceStatus
    remarks: Optional[str] = None
    recorded_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AttendanceCreate(SQLModel):
    student_id: str
    class_id: str
    attendance_date: str
    status: AttendanceStatus
    remarks: Optional[str] = None


class AttendanceBulkCreate(SQLModel):
    class_id: str
    attendance_date: str
    records: list[dict]


class StaffAttendance(SQLModel, table=True):
    __tablename__ = "staff_attendance"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    staff_id: str = Field(index=True)
    attendance_date: str = Field(index=True)
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: AttendanceStatus
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
