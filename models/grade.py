"""Grade and Report Card models"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class AssessmentType(str, Enum):
    CLASS_WORK = "class_work"
    HOMEWORK = "homework"
    QUIZ = "quiz"
    MID_TERM = "mid_term"
    END_OF_TERM = "end_of_term"
    PROJECT = "project"


class Grade(SQLModel, table=True):
    __tablename__ = "grades"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    class_id: str = Field(index=True)
    subject_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
    assessment_type: AssessmentType
    score: float
    max_score: float
    weight: float = 1.0
    remarks: Optional[str] = None
    recorded_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GradeCreate(SQLModel):
    student_id: str
    class_id: str
    subject_id: str
    academic_term_id: str
    assessment_type: AssessmentType
    score: float
    max_score: float
    weight: float = 1.0
    remarks: Optional[str] = None


class GradeScale(SQLModel, table=True):
    __tablename__ = "grade_scales"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    grade: str
    min_score: float
    max_score: float
    description: str
    gpa_point: float


class ReportCard(SQLModel, table=True):
    __tablename__ = "report_cards"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    student_id: str = Field(index=True)
    class_id: str = Field(index=True)
    academic_term_id: str = Field(index=True)
    total_score: float
    average_score: float
    position: Optional[int] = None
    class_size: int
    attendance_percentage: float
    class_teacher_remarks: Optional[str] = None
    head_teacher_remarks: Optional[str] = None
    conduct: Optional[str] = None
    interest: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str
