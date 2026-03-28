"""Report Card Template models"""
from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
import json


class ReportTemplate(SQLModel, table=True):
    """Store customizable report card templates per school"""
    __tablename__ = "report_templates"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    name: str = Field(index=True)  # e.g., "Standard Format", "Compact Format"
    description: Optional[str] = None
    html_content: str  # Jinja2 template HTML
    template_fields: Optional[str] = None  # JSON string of fields array
    template_buttons: Optional[str] = None  # JSON string of buttons array
    is_default: bool = False  # Only one default per school
    is_active: bool = True
    version: int = 1  # Track template versions
    created_by: str  # User ID who created
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReportTemplateCreate(SQLModel):
    """Create new report template"""
    name: str
    description: Optional[str] = None
    html_content: str
    template_fields: Optional[str] = None  # JSON string
    template_buttons: Optional[str] = None  # JSON string
    is_default: bool = False


class ReportTemplateUpdate(SQLModel):
    """Update existing template"""
    name: Optional[str] = None
    description: Optional[str] = None
    html_content: Optional[str] = None
    template_fields: Optional[str] = None  # JSON string
    template_buttons: Optional[str] = None  # JSON string
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class ReportTemplateResponse(SQLModel):
    """Response model for template"""
    id: str
    school_id: str
    name: str
    description: Optional[str]
    html_content: str
    template_fields: Optional[str] = None
    template_buttons: Optional[str] = None
    is_default: bool
    is_active: bool
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_at: datetime
    updated_at: datetime
