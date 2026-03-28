"""Email routes for sending notifications"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from models.user import User, UserRole
from auth import get_current_user, require_roles
from services.email_service import email_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["Email"])


class SendEmailRequest(BaseModel):
    """Request schema for sending emails"""
    recipients: List[EmailStr]
    subject: str
    html_body: str
    text_body: Optional[str] = None


class SendAnnouncementEmailRequest(BaseModel):
    """Request schema for sending announcement emails"""
    recipients: List[EmailStr]
    title: str
    content: str
    announcement_type: str = "general"


class SendFeeReminderRequest(BaseModel):
    """Request schema for fee reminder emails"""
    recipient_email: EmailStr
    student_name: str
    student_id: str
    amount_due: float
    due_date: str


class EmailResponse(BaseModel):
    """Response schema for email operations"""
    success: bool
    message: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None


@router.post("/send", response_model=EmailResponse)
async def send_email(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN))
):
    """
    Send a custom email (admin only)
    Email is processed in background to avoid blocking
    """
    async def send_task():
        result = await email_service.send_email(
            to=request.recipients,
            subject=request.subject,
            html_body=request.html_body,
            text_body=request.text_body
        )
        if not result["success"]:
            logger.error(f"Background email send failed: {result.get('error')}")
    
    background_tasks.add_task(send_task)
    
    return EmailResponse(
        success=True,
        message=f"Email queued for {len(request.recipients)} recipient(s)"
    )


@router.post("/announcement", response_model=EmailResponse)
async def send_announcement_email(
    request: SendAnnouncementEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN))
):
    """
    Send an announcement email with formatted template
    """
    async def send_task():
        result = await email_service.send_announcement_email(
            to=request.recipients,
            title=request.title,
            content=request.content,
            announcement_type=request.announcement_type
        )
        if not result["success"]:
            logger.error(f"Background announcement email failed: {result.get('error')}")
    
    background_tasks.add_task(send_task)
    
    return EmailResponse(
        success=True,
        message=f"Announcement email queued for {len(request.recipients)} recipient(s)"
    )


@router.post("/fee-reminder", response_model=EmailResponse)
async def send_fee_reminder_email(
    request: SendFeeReminderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN))
):
    """
    Send a fee reminder email to a parent/guardian
    """
    async def send_task():
        result = await email_service.send_fee_reminder(
            to=request.recipient_email,
            student_name=request.student_name,
            student_id=request.student_id,
            amount_due=request.amount_due,
            due_date=request.due_date
        )
        if not result["success"]:
            logger.error(f"Background fee reminder email failed: {result.get('error')}")
    
    background_tasks.add_task(send_task)
    
    return EmailResponse(
        success=True,
        message=f"Fee reminder email queued for {request.recipient_email}"
    )


@router.get("/test")
async def test_email_service(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN))
):
    """
    Test email service configuration (super admin only)
    """
    from config import get_settings
    settings = get_settings()
    
    is_configured = bool(settings.elastic_email_api_key)
    
    return {
        "configured": is_configured,
        "from_email": settings.elastic_email_from_email,
        "from_name": settings.elastic_email_from_name,
        "status": "ready" if is_configured else "not_configured"
    }
