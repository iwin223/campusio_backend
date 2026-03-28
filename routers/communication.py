"""Communication router - Announcements and Messages"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional
from models.communication import Announcement, AnnouncementCreate, AnnouncementType, AnnouncementAudience, Message, MessageCreate
from models.user import User, UserRole
from database import get_session
from auth import get_current_user, require_roles

router = APIRouter(prefix="/communication", tags=["Communication"])


@router.post("/announcements", response_model=dict)
async def create_announcement(
    announcement_data: AnnouncementCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session)
):
    """Create an announcement"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    announcement = Announcement(
        school_id=school_id,
        created_by=current_user.id,
        **announcement_data.model_dump()
    )
    session.add(announcement)
    await session.commit()
    await session.refresh(announcement)
    
    return {
        "id": announcement.id,
        "title": announcement.title,
        "announcement_type": announcement.announcement_type,
        "audience": announcement.audience,
        "is_published": announcement.is_published,
        "message": "Announcement created"
    }


@router.get("/announcements", response_model=dict)
async def list_announcements(
    announcement_type: Optional[AnnouncementType] = None,
    is_published: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List announcements"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    query = select(Announcement).where(Announcement.school_id == school_id)
    count_query = select(func.count(Announcement.id)).where(Announcement.school_id == school_id)
    
    if announcement_type:
        query = query.where(Announcement.announcement_type == announcement_type)
        count_query = count_query.where(Announcement.announcement_type == announcement_type)
    
    if is_published is not None:
        query = query.where(Announcement.is_published == is_published)
        count_query = count_query.where(Announcement.is_published == is_published)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Announcement.publish_date.desc())
    
    result = await session.execute(query)
    announcements = result.scalars().all()
    
    creator_ids = list(set(a.created_by for a in announcements))
    creators = {}
    if creator_ids:
        creator_result = await session.execute(select(User).where(User.id.in_(creator_ids)))
        creators = {u.id: f"{u.first_name} {u.last_name}" for u in creator_result.scalars().all()}
    
    return {
        "items": [
            {
                "id": a.id,
                "title": a.title,
                "content": a.content,
                "announcement_type": a.announcement_type,
                "audience": a.audience,
                "is_published": a.is_published,
                "publish_date": a.publish_date,
                "created_by": creators.get(a.created_by, "Unknown"),
                "created_at": a.created_at.isoformat()
            }
            for a in announcements
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.post("/messages", response_model=dict)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Send a message"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    message = Message(
        school_id=school_id,
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        subject=message_data.subject,
        content=message_data.content,
        parent_message_id=message_data.parent_message_id
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    
    return {
        "id": message.id,
        "receiver_id": message.receiver_id,
        "subject": message.subject,
        "message": "Message sent"
    }


@router.get("/messages/inbox", response_model=dict)
async def get_inbox(
    is_read: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get inbox messages"""
    query = select(Message).where(Message.receiver_id == current_user.id)
    count_query = select(func.count(Message.id)).where(Message.receiver_id == current_user.id)
    
    if is_read is not None:
        query = query.where(Message.is_read == is_read)
        count_query = count_query.where(Message.is_read == is_read)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Message.created_at.desc())
    
    result = await session.execute(query)
    messages = result.scalars().all()
    
    sender_ids = list(set(m.sender_id for m in messages))
    senders = {}
    if sender_ids:
        sender_result = await session.execute(select(User).where(User.id.in_(sender_ids)))
        senders = {u.id: f"{u.first_name} {u.last_name}" for u in sender_result.scalars().all()}
    
    return {
        "items": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": senders.get(m.sender_id, "Unknown"),
                "subject": m.subject,
                "content": m.content[:100] + "..." if len(m.content) > 100 else m.content,
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/messages/{message_id}", response_model=dict)
async def get_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get message details"""
    result = await session.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.sender_id != current_user.id and message.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if message.receiver_id == current_user.id and not message.is_read:
        message.is_read = True
        session.add(message)
        await session.commit()
    
    sender_result = await session.execute(select(User).where(User.id == message.sender_id))
    sender = sender_result.scalar_one_or_none()
    
    receiver_result = await session.execute(select(User).where(User.id == message.receiver_id))
    receiver = receiver_result.scalar_one_or_none()
    
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_name": f"{sender.first_name} {sender.last_name}" if sender else "Unknown",
        "receiver_id": message.receiver_id,
        "receiver_name": f"{receiver.first_name} {receiver.last_name}" if receiver else "Unknown",
        "subject": message.subject,
        "content": message.content,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat()
    }
