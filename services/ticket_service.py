"""Ticket service - Business logic for ticketing system"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from models.ticket import (
    Ticket, TicketComment, TicketAttachment, TicketNotification,
    TicketCreate, TicketStatus
)
from models.user import User

logger = logging.getLogger(__name__)


class TicketService:
    """Service for managing tickets"""
    
    @staticmethod
    async def create_ticket(
        session: AsyncSession,
        school_id: str,
        created_by_id: str,
        ticket_data: TicketCreate
    ) -> Ticket:
        """Create a new ticket"""
        ticket = Ticket(
            school_id=school_id,
            created_by_id=created_by_id,
            category=ticket_data.category,
            priority=ticket_data.priority,
            title=ticket_data.title,
            description=ticket_data.description,
            status=TicketStatus.OPEN
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        logger.info(f"Ticket created: {ticket.id} by user {created_by_id}")
        return ticket
    
    @staticmethod
    async def get_school_tickets(
        session: AsyncSession,
        school_id: str,
        status: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> tuple[List[Ticket], int]:
        """Get tickets for a specific school"""
        query = select(Ticket).where(Ticket.school_id == school_id)
        count_query = select(func.count(Ticket.id)).where(Ticket.school_id == school_id)
        
        if status:
            query = query.where(Ticket.status == status)
            count_query = count_query.where(Ticket.status == status)
        
        if category:
            query = query.where(Ticket.category == category)
            count_query = count_query.where(Ticket.category == category)
        
        # Get total count
        result = await session.execute(count_query)
        total = result.scalar() or 0
        
        # Get paginated results
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Ticket.created_at.desc())
        result = await session.execute(query)
        tickets = result.scalars().all()
        
        return tickets, total
    
    @staticmethod
    async def get_all_tickets(
        session: AsyncSession,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> tuple[List[Ticket], int]:
        """Get all tickets (for super admin)"""
        query = select(Ticket)
        count_query = select(func.count(Ticket.id))
        
        if status:
            query = query.where(Ticket.status == status)
            count_query = count_query.where(Ticket.status == status)
        
        if priority:
            query = query.where(Ticket.priority == priority)
            count_query = count_query.where(Ticket.priority == priority)
        
        # Get total count
        result = await session.execute(count_query)
        total = result.scalar() or 0
        
        # Get paginated results
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Ticket.created_at.desc())
        result = await session.execute(query)
        tickets = result.scalars().all()
        
        return tickets, total
    
    @staticmethod
    async def get_ticket_by_id(
        session: AsyncSession,
        ticket_id: str
    ) -> Optional[Ticket]:
        """Get ticket by ID"""
        query = select(Ticket).where(Ticket.id == ticket_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_ticket_status(
        session: AsyncSession,
        ticket_id: str,
        status: TicketStatus,
        assigned_to_id: Optional[str] = None
    ) -> Optional[Ticket]:
        """Update ticket status"""
        ticket = await TicketService.get_ticket_by_id(session, ticket_id)
        if not ticket:
            return None
        
        ticket.status = status
        if assigned_to_id:
            ticket.assigned_to_id = assigned_to_id
        ticket.updated_at = datetime.utcnow()
        
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        logger.info(f"Ticket {ticket_id} status updated to {status}")
        return ticket
    
    @staticmethod
    async def add_comment(
        session: AsyncSession,
        ticket_id: str,
        author_id: str,
        comment: str,
        is_internal: bool = False
    ) -> Optional[TicketComment]:
        """Add comment to ticket"""
        # Verify ticket exists
        ticket = await TicketService.get_ticket_by_id(session, ticket_id)
        if not ticket:
            return None
        
        ticket_comment = TicketComment(
            ticket_id=ticket_id,
            author_id=author_id,
            comment=comment,
            is_internal=is_internal
        )
        session.add(ticket_comment)
        
        # Update ticket's updated_at
        ticket.updated_at = datetime.utcnow()
        session.add(ticket)
        
        await session.commit()
        await session.refresh(ticket_comment)
        logger.info(f"Comment added to ticket {ticket_id}")
        return ticket_comment
    
    @staticmethod
    async def get_ticket_comments(
        session: AsyncSession,
        ticket_id: str
    ) -> List[TicketComment]:
        """Get all comments for a ticket"""
        query = select(TicketComment).where(
            TicketComment.ticket_id == ticket_id
        ).order_by(TicketComment.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def close_ticket(
        session: AsyncSession,
        ticket_id: str,
        resolution_summary: str
    ) -> Optional[Ticket]:
        """Close ticket with resolution"""
        ticket = await TicketService.get_ticket_by_id(session, ticket_id)
        if not ticket:
            return None
        
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.utcnow()
        ticket.resolution_summary = resolution_summary
        ticket.updated_at = datetime.utcnow()
        
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        logger.info(f"Ticket {ticket_id} closed with resolution")
        return ticket
    
    @staticmethod
    async def log_notification(
        session: AsyncSession,
        ticket_id: str,
        sent_to_phone: str,
        sent_via: str,
        status: str,
        message_id: Optional[str] = None
    ) -> TicketNotification:
        """Log notification for audit trail"""
        notification = TicketNotification(
            ticket_id=ticket_id,
            sent_to_phone=sent_to_phone,
            sent_via=sent_via,
            status=status,
            message_id=message_id
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification
    
    @staticmethod
    async def get_ticket_statistics(
        session: AsyncSession,
        school_id: Optional[str] = None
    ) -> dict:
        """Get ticket statistics"""
        if school_id:
            base_query = select(Ticket).where(Ticket.school_id == school_id)
        else:
            base_query = select(Ticket)
        
        # Count by status
        open_count = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.OPEN)
        )
        in_progress_count = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.IN_PROGRESS)
        )
        resolved_count = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.RESOLVED)
        )
        closed_count = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.CLOSED)
        )
        
        # Extract scalar values once to avoid result object being closed
        open_val = open_count.scalar() or 0
        in_progress_val = in_progress_count.scalar() or 0
        resolved_val = resolved_count.scalar() or 0
        closed_val = closed_count.scalar() or 0
        
        return {
            "open": open_val,
            "in_progress": in_progress_val,
            "resolved": resolved_val,
            "closed": closed_val,
            "total": open_val + in_progress_val + resolved_val + closed_val
        }
