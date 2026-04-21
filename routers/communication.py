"""Communication router - Announcements and Messages"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional
from models.communication import Announcement, AnnouncementCreate, AnnouncementType, AnnouncementAudience, Message, MessageCreate, MessageType
from models.user import User, UserRole
from models.student import Student 
from models.student import Parent
from models.staff import Staff, TeacherAssignment
from models.classroom import Class, Subject
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
    if not school_id and current_user.role != UserRole.SUPER_ADMIN:
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
    """Send a message with optional context (student, class, message type)"""
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=403, detail="No school context")
    
    # Normalize receiver_id to user_id (in case it's a staff_id or parent_id)
    normalized_receiver_id = message_data.receiver_id
    
    # Check if receiver_id exists as a User
    user_check = await session.execute(
        select(User.id).where(User.id == message_data.receiver_id)
    )
    if user_check.scalar_one_or_none() is None:
        # Not a user_id, try to resolve from Staff or Parent
        # Check Staff table
        staff_check = await session.execute(
            select(Staff.user_id).where(Staff.id == message_data.receiver_id)
        )
        staff_user_id = staff_check.scalar_one_or_none()
        if staff_user_id:
            normalized_receiver_id = staff_user_id
        else:
            # Check Parent table
            parent_check = await session.execute(
                select(Parent.user_id).where(Parent.id == message_data.receiver_id)
            )
            parent_user_id = parent_check.scalar_one_or_none()
            if parent_user_id:
                normalized_receiver_id = parent_user_id
    
    message = Message(
        school_id=school_id,
        sender_id=current_user.id,
        receiver_id=normalized_receiver_id,
        subject=message_data.subject,
        content=message_data.content,
        parent_message_id=message_data.parent_message_id,
        student_id=message_data.student_id,
        class_id=message_data.class_id,
        message_type=message_data.message_type
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    
    # Get sender info
    sender_result = await session.execute(
        select(User).where(User.id == current_user.id)
    )
    sender = sender_result.scalar_one_or_none()
    sender_name = f"{sender.first_name} {sender.last_name}" if sender else "Unknown"
    
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_name": sender_name,
        "receiver_id": message.receiver_id,
        "subject": message.subject,
        "content": message.content,
        "is_read": message.is_read,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "message_type": message.message_type.value if message.message_type else "general",
        "student_id": message.student_id,
        "created_at": message.created_at.isoformat()
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


# ============================================================================
# NEW ENDPOINTS FOR PARENT-TEACHER CHAT
# ============================================================================

@router.get("/teachers/by-student/{student_id}", response_model=dict)
async def get_teachers_for_student(
    student_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all teachers for a specific student.
    Used by parents to find teachers to message about their child.
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    try:
        # Verify the student exists and belongs to this school
        student_result = await session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.school_id == school_id
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Get the student's class
        if not student.class_id:
            return {"items": [], "message": "Student has no class assigned"}
        
        # Get all teachers for this class and their subjects
        query = select(
            TeacherAssignment.staff_id,
            TeacherAssignment.subject_id,
            Staff.first_name,
            Staff.last_name,
            Staff.email,
            Staff.phone
        ).join(
            Staff,
            TeacherAssignment.staff_id == Staff.id
        ).where(
            TeacherAssignment.class_id == student.class_id,
            TeacherAssignment.school_id == school_id
        )
        
        result = await session.execute(query)
        rows = result.all()
        
        # Get subject names
        subject_ids = [row[1] for row in rows if row[1]]
        subjects = {}
        if subject_ids:
            subject_result = await session.execute(
                select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
            )
            subjects = {row[0]: row[1] for row in subject_result.all()}
        
        # Get user information for staff (to get user_id for messaging)
        staff_ids = [row[0] for row in rows]
        staff_users = {}
        if staff_ids:
            user_result = await session.execute(
                select(Staff.id, Staff.user_id).where(Staff.id.in_(staff_ids))
            )
            staff_users = {row[0]: row[1] for row in user_result.all()}
        
        # Group by staff_id to combine subjects for teachers with multiple subjects
        teachers_dict = {}
        for row in rows:
            staff_id = row[0]
            if staff_id not in teachers_dict:
                teachers_dict[staff_id] = {
                    "user_id": staff_users.get(row[0]),
                    "staff_id": row[0],
                    "first_name": row[2],
                    "last_name": row[3],
                    "email": row[4],
                    "phone": row[5],
                    "subjects": []
                }
            
            subject_name = subjects.get(row[1], "Unknown Subject")
            if subject_name not in teachers_dict[staff_id]["subjects"]:
                teachers_dict[staff_id]["subjects"].append(subject_name)
        
        teachers = list(teachers_dict.values())
        
        return {
            "items": teachers,
            "total": len(teachers),
            "student_id": student_id,
            "student_name": f"{student.first_name} {student.last_name}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching teachers: {str(e)}")


@router.get("/conversations", response_model=dict)
async def get_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all active conversations for the current user.
    Returns one entry per unique conversation partner with the last message info.
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    try:
        # Build list of IDs to search for (user_id and parent_id/staff_id if applicable)
        search_ids = [current_user.id]
        
        # If user is a parent, also find messages with their parent_id
        if current_user.role == UserRole.PARENT or str(current_user.role) == "parent":
            parent_result = await session.execute(
                select(Parent).where(Parent.user_id == current_user.id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                search_ids.append(parent.id)
        
        # If user is staff, also find messages with their staff_id
        if current_user.role in [UserRole.TEACHER, UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN] or \
           str(current_user.role) in ["teacher", "super_admin", "school_admin"]:
            staff_result = await session.execute(
                select(Staff).where(Staff.user_id == current_user.id)
            )
            staff = staff_result.scalar_one_or_none()
            if staff:
                search_ids.append(staff.id)
        
        # Get all messages where user is sender or receiver (including all their possible IDs)
        query = select(Message).where(
            (Message.sender_id.in_(search_ids)) | (Message.receiver_id.in_(search_ids)),
            Message.school_id == school_id
        ).order_by(Message.created_at.desc())
        
        result = await session.execute(query)
        all_messages = result.scalars().all()
        
        # Group by conversation partner (the other person in the conversation)
        conversations = {}
        for msg in all_messages:
            # Normalize the sender_id to user_id if needed
            sender_id = msg.sender_id
            if sender_id != current_user.id:
                # Check if sender is a user
                sender_check = await session.execute(
                    select(User.id).where(User.id == sender_id)
                )
                if sender_check.scalar_one_or_none() is None:
                    # Try to resolve from Staff or Parent
                    staff_check = await session.execute(
                        select(Staff.user_id).where(Staff.id == sender_id)
                    )
                    resolved_user_id = staff_check.scalar_one_or_none()
                    if resolved_user_id:
                        sender_id = resolved_user_id
                    else:
                        parent_check = await session.execute(
                            select(Parent.user_id).where(Parent.id == sender_id)
                        )
                        resolved_user_id = parent_check.scalar_one_or_none()
                        if resolved_user_id:
                            sender_id = resolved_user_id
            
            # Normalize receiver_id to user_id if needed
            receiver_id = msg.receiver_id
            if receiver_id != current_user.id:
                # Check if receiver is a user
                receiver_check = await session.execute(
                    select(User.id).where(User.id == receiver_id)
                )
                if receiver_check.scalar_one_or_none() is None:
                    # Try to resolve from Staff or Parent
                    staff_check = await session.execute(
                        select(Staff.user_id).where(Staff.id == receiver_id)
                    )
                    resolved_user_id = staff_check.scalar_one_or_none()
                    if resolved_user_id:
                        receiver_id = resolved_user_id
                    else:
                        parent_check = await session.execute(
                            select(Parent.user_id).where(Parent.id == receiver_id)
                        )
                        resolved_user_id = parent_check.scalar_one_or_none()
                        if resolved_user_id:
                            receiver_id = resolved_user_id
            
            # Determine the other user ID
            other_user_id = receiver_id if sender_id == current_user.id else sender_id
            
            if other_user_id not in conversations:
                conversations[other_user_id] = {
                    "last_message": msg,
                    "unread_count": 0
                }
            
            # Count unread messages from this person
            if receiver_id == current_user.id and not msg.is_read:
                conversations[other_user_id]["unread_count"] += 1
        
        # Get user info for all conversation partners
        partner_ids = list(conversations.keys())
        partners = {}
        if partner_ids:
            # First, try to get direct User records
            partner_result = await session.execute(
                select(User).where(User.id.in_(partner_ids))
            )
            partners = {u.id: u for u in partner_result.scalars().all()}
        
        # For any IDs not found in User table, try to resolve them
        # (they might be parent_id or staff_id stored in receiver_id/sender_id)
        unresolved_ids = [pid for pid in partner_ids if pid not in partners]
        
        if unresolved_ids:
            # Try to find these IDs in Parent table
            parent_results = await session.execute(
                select(Parent).where(Parent.id.in_(unresolved_ids))
            )
            for parent_record in parent_results.scalars().all():
                if parent_record.user_id and parent_record.user_id not in partners:
                    # Get the User record for this parent's user_id
                    user_result = await session.execute(
                        select(User).where(User.id == parent_record.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        partners[parent_record.id] = user
                    else:
                        # Create a synthetic user object from parent data
                        synthetic_user = User(
                            id=parent_record.id,
                            first_name=parent_record.first_name,
                            last_name=parent_record.last_name
                        )
                        synthetic_user.role = "parent"
                        partners[parent_record.id] = synthetic_user
                else:
                    # Parent exists but no user_id - create synthetic record
                    synthetic_user = User(
                        id=parent_record.id,
                        first_name=parent_record.first_name,
                        last_name=parent_record.last_name
                    )
                    synthetic_user.role = "parent"
                    partners[parent_record.id] = synthetic_user
            
            # Try to find remaining unresolved IDs in Staff table
            still_unresolved = [pid for pid in unresolved_ids if pid not in partners]
            if still_unresolved:
                staff_results = await session.execute(
                    select(Staff).where(Staff.id.in_(still_unresolved))
                )
                for staff_record in staff_results.scalars().all():
                    if staff_record.user_id and staff_record.user_id not in partners:
                        # Get the User record for this staff's user_id
                        user_result = await session.execute(
                            select(User).where(User.id == staff_record.user_id)
                        )
                        user = user_result.scalar_one_or_none()
                        if user:
                            partners[staff_record.id] = user
                        else:
                            # Create a synthetic user object from staff data
                            synthetic_user = User(
                                id=staff_record.id,
                                first_name=staff_record.first_name,
                                last_name=staff_record.last_name
                            )
                            synthetic_user.role = staff_record.staff_type or "staff"
                            partners[staff_record.id] = synthetic_user
                    else:
                        # Staff exists but no user_id - create synthetic record
                        synthetic_user = User(
                            id=staff_record.id,
                            first_name=staff_record.first_name,
                            last_name=staff_record.last_name
                        )
                        synthetic_user.role = staff_record.staff_type or "staff"
                        partners[staff_record.id] = synthetic_user
        

        
        # Build response
        conv_list = []
        for partner_id, conv_data in conversations.items():
            partner = partners.get(partner_id)
            last_msg = conv_data["last_message"]
            
            # Determine name and role
            if partner and (partner.first_name or partner.last_name):
                partner_name = f"{(partner.first_name or '').strip()} {(partner.last_name or '').strip()}".strip()
                partner_role = (partner.role or "unknown") if partner.role else "unknown"
            elif partner and partner.email:
                # Fallback to email if name not available
                partner_name = partner.email.split('@')[0] if '@' in partner.email else partner.email
                partner_role = "unknown"
            else:
                partner_name = "Unknown"
                partner_role = "unknown"
            
            conv_list.append({
                "conversation_id": partner_id,
                "other_user_id": partner_id,
                "other_user_name": partner_name,
                "other_user_role": partner_role,
                "last_message": last_msg.content[:100] + "..." if len(last_msg.content) > 100 else last_msg.content,
                "last_message_time": last_msg.created_at.isoformat(),
                "unread_count": conv_data["unread_count"]
            })
        
        # Sort by last_message_time descending
        conv_list.sort(key=lambda x: x["last_message_time"], reverse=True)
        
        # Pagination
        total = len(conv_list)
        offset = (page - 1) * limit
        paginated_list = conv_list[offset:offset + limit]
        
        return {
            "items": paginated_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 1
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conversations: {str(e)}")


@router.get("/conversations/with/{other_user_id}", response_model=dict)
async def get_conversation_messages(
    other_user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all messages in a conversation with a specific user.
    Messages are returned in chronological order (oldest first).
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    try:
        # Build list of current user IDs to search with (user_id + parent_id/staff_id if applicable)
        current_user_search_ids = [current_user.id]
        if current_user.role == UserRole.PARENT or str(current_user.role) == "parent":
            parent_result = await session.execute(
                select(Parent).where(Parent.user_id == current_user.id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                current_user_search_ids.append(parent.id)
        
        if current_user.role in [UserRole.TEACHER, UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN] or \
           str(current_user.role) in ["teacher", "super_admin", "school_admin"]:
            staff_result = await session.execute(
                select(Staff).where(Staff.user_id == current_user.id)
            )
            staff = staff_result.scalar_one_or_none()
            if staff:
                current_user_search_ids.append(staff.id)
        
        # Also build list of other user IDs (might be parent_id, staff_id, or user_id)
        other_user_search_ids = [other_user_id]
        
        # If other_user_id is a parent_id, also search for their user_id
        parent_result = await session.execute(
            select(Parent).where(Parent.id == other_user_id)
        )
        other_parent = parent_result.scalar_one_or_none()
        if other_parent and other_parent.user_id:
            other_user_search_ids.append(other_parent.user_id)
        
        # If other_user_id is a staff_id, also search for their user_id
        staff_result = await session.execute(
            select(Staff).where(Staff.id == other_user_id)
        )
        other_staff = staff_result.scalar_one_or_none()
        if other_staff and other_staff.user_id:
            other_user_search_ids.append(other_staff.user_id)
        
        # Get messages between current user (any ID) and other user (any ID)
        query = select(Message).where(
            (
                Message.sender_id.in_(current_user_search_ids) & 
                Message.receiver_id.in_(other_user_search_ids)
            ) |
            (
                Message.sender_id.in_(other_user_search_ids) & 
                Message.receiver_id.in_(current_user_search_ids)
            ),
            Message.school_id == school_id
        ).order_by(Message.created_at.asc())
        
        # Get total count
        count_result = await session.execute(
            select(func.count(Message.id)).where(
                (
                    Message.sender_id.in_(current_user_search_ids) & 
                    Message.receiver_id.in_(other_user_search_ids)
                ) |
                (
                    Message.sender_id.in_(other_user_search_ids) & 
                    Message.receiver_id.in_(current_user_search_ids)
                ),
                Message.school_id == school_id
            )
        )
        total = count_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await session.execute(query)
        messages = result.scalars().all()
        
        # Get sender/receiver info
        user_ids = set([other_user_id, current_user.id])
        user_result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = {u.id: u for u in user_result.scalars().all()}
        
        # Mark as read for current user
        for msg in messages:
            if msg.receiver_id == current_user.id and not msg.is_read:
                msg.is_read = True
                msg.read_at = datetime.utcnow()
        
        await session.commit()
        
        # Format response
        message_list = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": f"{users.get(m.sender_id).first_name} {users.get(m.sender_id).last_name}" if users.get(m.sender_id) else "Unknown",
                "receiver_id": m.receiver_id,
                "subject": m.subject,
                "content": m.content,
                "is_read": m.is_read,
                "read_at": m.read_at.isoformat() if m.read_at else None,
                "message_type": m.message_type.value,
                "student_id": m.student_id,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
        
        return {
            "items": message_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 1
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conversation: {str(e)}")


@router.put("/messages/{message_id}/read", response_model=dict)
async def mark_message_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Mark a specific message as read and set the read_at timestamp.
    Only the receiver can mark a message as read.
    """
    try:
        result = await session.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Only the receiver can mark message as read
        if message.receiver_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only receiver can mark message as read")
        
        message.is_read = True
        message.read_at = datetime.utcnow()
        session.add(message)
        await session.commit()
        
        return {
            "id": message.id,
            "is_read": message.is_read,
            "read_at": message.read_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking message as read: {str(e)}")


@router.get("/messages/search", response_model=dict)
async def search_messages(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Search messages by subject or content.
    Returns messages where user is sender or receiver.
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="No school context")
    
    try:
        # Build search query - match in subject or content
        search_pattern = f"%{query}%"
        
        search_query = select(Message).where(
            (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id),
            Message.school_id == school_id,
            (Message.subject.ilike(search_pattern)) | (Message.content.ilike(search_pattern))
        ).order_by(Message.created_at.desc())
        
        # Get total count
        count_result = await session.execute(
            select(func.count(Message.id)).where(
                (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id),
                Message.school_id == school_id,
                (Message.subject.ilike(search_pattern)) | (Message.content.ilike(search_pattern))
            )
        )
        total = count_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        search_query = search_query.offset(offset).limit(limit)
        
        result = await session.execute(search_query)
        messages = result.scalars().all()
        
        # Get user info for senders
        sender_ids = list(set([m.sender_id for m in messages]))
        senders = {}
        if sender_ids:
            sender_result = await session.execute(
                select(User).where(User.id.in_(sender_ids))
            )
            senders = {u.id: f"{u.first_name} {u.last_name}" for u in sender_result.scalars().all()}
        
        # Format response
        message_list = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": senders.get(m.sender_id, "Unknown"),
                "subject": m.subject,
                "content": m.content[:150] + "..." if len(m.content) > 150 else m.content,
                "message_type": m.message_type,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
        
        return {
            "items": message_list,
            "total": total,
            "page": page,
            "limit": limit,
            "query": query,
            "pages": (total + limit - 1) // limit if total > 0 else 1
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching messages: {str(e)}")

