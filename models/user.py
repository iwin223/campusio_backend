"""User models for authentication and RBAC"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    SCHOOL_ADMIN = "school_admin"
    HR = "hr"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole
    school_id: Optional[str] = Field(default=None, index=True)
    is_active: bool = True


class User(UserBase, table=True):
    __tablename__ = "users"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    password_hash: str
    plain_text_password: Optional[str] = None  # Only for portal accounts
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None


class UserCreate(SQLModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole
    school_id: Optional[str] = None


class UserLogin(SQLModel):
    email: str
    password: str


class UserResponse(SQLModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    role: UserRole
    school_id: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
