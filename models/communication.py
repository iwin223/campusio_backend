"""Communication models - Announcements and Messages"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class AnnouncementType(str, Enum):
    GENERAL = "general"
    ACADEMIC = "academic"
    EVENT = "event"
    EMERGENCY = "emergency"
    FEE = "fee"


class AnnouncementAudience(str, Enum):
    ALL = "all"
    TEACHERS = "teachers"
    STUDENTS = "students"
    PARENTS = "parents"
    SPECIFIC_CLASS = "specific_class"


class Announcement(SQLModel, table=True):
    __tablename__ = "announcements"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    title: str
    content: str
    announcement_type: AnnouncementType
    audience: AnnouncementAudience
    target_class_id: Optional[str] = Field(default=None, index=True)
    is_published: bool = True
    publish_date: str
    expiry_date: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AnnouncementCreate(SQLModel):
    title: str
    content: str
    announcement_type: AnnouncementType
    audience: AnnouncementAudience
    target_class_id: Optional[str] = None
    is_published: bool = True
    publish_date: str
    expiry_date: Optional[str] = None


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    sender_id: str = Field(index=True)
    receiver_id: str = Field(index=True)
    subject: str
    content: str
    is_read: bool = False
    parent_message_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageCreate(SQLModel):
    receiver_id: str
    subject: str
    content: str
    parent_message_id: Optional[str] = None


class EmailNotification(SQLModel, table=True):
    __tablename__ = "email_notifications"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    recipient_email: str
    subject: str
    content: str
    notification_type: str
    status: str = "pending"
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
