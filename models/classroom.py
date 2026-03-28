"""Class and Subject models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class ClassLevel(str, Enum):
    KG1 = "kg1"
    KG2 = "kg2"
    PRIMARY_1 = "primary_1"
    PRIMARY_2 = "primary_2"
    PRIMARY_3 = "primary_3"
    PRIMARY_4 = "primary_4"
    PRIMARY_5 = "primary_5"
    PRIMARY_6 = "primary_6"
    JHS_1 = "jhs_1"
    JHS_2 = "jhs_2"
    JHS_3 = "jhs_3"


class Class(SQLModel, table=True):
    __tablename__ = "classes"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    name: str
    level: ClassLevel
    section: Optional[str] = None
    capacity: int = 40
    room_number: Optional[str] = None
    academic_term_id: Optional[str] = Field(default=None, index=True)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ClassCreate(SQLModel):
    name: str
    level: ClassLevel
    section: Optional[str] = None
    capacity: int = 40
    room_number: Optional[str] = None
    academic_term_id: Optional[str] = None


class SubjectCategory(str, Enum):
    CORE = "core"
    ELECTIVE = "elective"


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    name: str
    code: str
    category: SubjectCategory = SubjectCategory.CORE
    description: Optional[str] = None
    credit_hours: int = 1
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SubjectCreate(SQLModel):
    name: str
    code: str
    category: SubjectCategory = SubjectCategory.CORE
    description: Optional[str] = None
    credit_hours: int = 1


class ClassSubject(SQLModel, table=True):
    __tablename__ = "class_subjects"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    class_id: str = Field(index=True)
    subject_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
