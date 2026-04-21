"""Ticketing system models"""
from sqlmodel import SQLModel, Field
from sqlalchemy import String
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class TicketCategory(str, Enum):
    TECHNICAL = "technical"
    ACADEMIC = "academic"
    FINANCE = "finance"
    HR = "hr"
    OTHER = "other"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Ticket(SQLModel, table=True):
    """Main ticket entity"""
    __tablename__ = "tickets"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    created_by_id: str = Field(index=True)
    category: TicketCategory = Field(sa_column=String(50))
    priority: TicketPriority = Field(sa_column=String(50))
    title: str
    description: str
    status: TicketStatus = Field(default=TicketStatus.OPEN, sa_column=String(50))
    assigned_to_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None


class TicketComment(SQLModel, table=True):
    """Comments/updates on tickets"""
    __tablename__ = "ticket_comments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(index=True)
    author_id: str = Field(index=True)
    comment: str
    is_internal: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketAttachment(SQLModel, table=True):
    """File attachments for tickets"""
    __tablename__ = "ticket_attachments"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(index=True)
    file_url: str
    file_name: str
    file_size: int
    file_type: str
    uploaded_by_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TicketNotification(SQLModel, table=True):
    """Audit trail of notifications sent"""
    __tablename__ = "ticket_notifications"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(index=True)
    sent_to_phone: str
    sent_via: str  # whatsapp, sms, email
    status: str  # pending, sent, failed, delivered
    message_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response schemas
class TicketCreate(SQLModel):
    category: TicketCategory
    priority: TicketPriority
    title: str
    description: str


class TicketUpdate(SQLModel):
    status: Optional[TicketStatus] = None
    assigned_to_id: Optional[str] = None


class TicketResponse(SQLModel):
    id: str
    school_id: str
    created_by_id: str
    category: TicketCategory
    priority: TicketPriority
    title: str
    description: str
    status: TicketStatus
    assigned_to_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    resolution_summary: Optional[str]


class TicketDetailResponse(TicketResponse):
    comments: list[dict] = []
    attachments: list[dict] = []


class TicketCommentCreate(SQLModel):
    comment: str
    is_internal: bool = False


class TicketCommentResponse(SQLModel):
    id: str
    ticket_id: str
    author_id: str
    comment: str
    is_internal: bool
    created_at: datetime


class TicketCloseRequest(SQLModel):
    resolution_summary: str
