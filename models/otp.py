"""OTP models for two-factor authentication"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class OTPBase(SQLModel):
    user_id: str = Field(foreign_key="users.id", index=True)
    code: str  # 6-digit code
    is_used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime  # Default 10 minutes from creation


class OTP(OTPBase, table=True):
    __tablename__ = "otps"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    attempts: int = 0  # Track failed attempts
    max_attempts: int = 3  # Lock after 3 failed attempts


class OTPSettings(SQLModel, table=True):
    """Store OTP settings per user"""
    __tablename__ = "otp_settings"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", unique=True, index=True)
    is_enabled: bool = True  # Whether 2FA is enabled
    is_mandatory: bool = False  # Whether 2FA is mandatory (for admin roles)
    method: str = "email"  # "email" or "sms" or "totp"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OTPVerificationRequest(SQLModel):
    """Request schema for OTP verification"""
    email: str
    otp_code: str


class OTPVerificationResponse(SQLModel):
    """Response after OTP verification"""
    access_token: str
    token_type: str
    user: dict


class OTPAdminSettings(SQLModel, table=True):
    """Store school-wide OTP configuration set by admins"""
    __tablename__ = "otp_admin_settings"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(foreign_key="schools.id", unique=True, index=True)
    is_enabled: bool = True  # Whether OTP is enabled for the school
    expiry_minutes: int = 10  # How long OTP codes are valid
    max_attempts: int = 3  # Max failed attempts before code expires
    default_method: str = "sms"  # Default delivery method: "email" or "sms"
    require_for_roles: str = Field(default="school_admin,hr")  # Comma-separated roles
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OTPAdminSettingsRequest(SQLModel):
    """Request schema for admin OTP settings update"""
    is_enabled: bool = True
    expiry_minutes: int = 10
    max_attempts: int = 3
    default_method: str = "sms"
    require_for_roles: list[str]  # List of role IDs that require OTP


class OTPAdminSettingsResponse(SQLModel):
    """Response schema for admin OTP settings"""
    is_enabled: bool
    expiry_minutes: int
    max_attempts: int
    default_method: str
    require_for_roles: list[str]
