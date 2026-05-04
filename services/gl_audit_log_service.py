"""GL Audit Log Service - Immutable audit trail for all GL changes

Provides complete audit trail for compliance and fraud detection:
- Records all GL account changes
- Tracks journal entry posting and reversal
- Logs expense approval and GL posting workflow
- Immutable design (records can only be created, never deleted)
- Batch queries for reconciliation and audit procedures
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func, desc
from datetime import datetime, timedelta
import json

from models.finance.gl_audit_log import (
    GLAuditLog,
    AuditActionType,
    AuditEntityType,
    GLAuditLogCreate,
)

logger = logging.getLogger(__name__)


class AuditLogError(Exception):
    """Base exception for audit log service errors"""
    pass


class GLAuditLogService:
    """Service for managing GL audit trails
    
    Design principles:
    - IMMUTABLE: Records can only be created, never deleted or modified
    - COMPLETE: Every GL change is logged with full context
    - TRACEABLE: Links to user, IP address, timestamp, and related entities
    - QUERYABLE: Efficient filtering for audits and compliance procedures
    
    Typical usage:
    - Call log_action() whenever a GL change occurs
    - Query logs for compliance audits
    - Reconcile against source documents
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with async database session
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
    
    # ==================== Core Logging Operations ====================
    
    async def log_action(
        self,
        school_id: str,
        entity_type: AuditEntityType,
        entity_id: str,
        action: AuditActionType,
        user_id: str,
        user_name: str,
        user_role: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> GLAuditLog:
        """Log a GL change action
        
        This is the primary logging method. Should be called whenever:
        - GL account is created/updated
        - Journal entry is posted/reversed
        - Expense is approved/posted
        - Period is locked/closed
        - Reconciliation is completed
        
        Args:
            school_id: School identifier
            entity_type: Type of entity being logged (GL_ACCOUNT, JOURNAL_ENTRY, etc.)
            entity_id: ID of the entity that changed
            action: Action that occurred (CREATED, POSTED, REVERSED, etc.)
            user_id: User who made the change
            user_name: Display name of user
            user_role: Role of user (admin, finance, etc.)
            old_values: Previous values (for updates)
            new_values: New values
            ip_address: IP address of user (for fraud detection)
            user_agent: User agent string (for forensics)
            related_entity_id: ID of related entity (e.g., JE ID for GL posting)
            batch_id: Batch ID for grouping related actions
            
        Returns:
            Created GLAuditLog record
        """
        try:
            # Generate change summary
            change_summary = self._generate_change_summary(
                action, old_values, new_values
            )
            
            # Create audit log
            audit_log = GLAuditLog(
                school_id=school_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user_id=user_id,
                user_name=user_name,
                user_role=user_role,
                timestamp=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent,
                old_values=old_values,
                new_values=new_values,
                change_summary=change_summary,
                related_entity_id=related_entity_id,
                batch_id=batch_id,
            )
            
            self.session.add(audit_log)
            await self.session.commit()
            await self.session.refresh(audit_log)
            
            logger.info(
                f"Logged {action.value} for {entity_type.value} {entity_id} "
                f"(user: {user_name}, ip: {ip_address})"
            )
            
            return audit_log
        except Exception as e:
            logger.error(f"Error logging audit action: {str(e)}")
            raise AuditLogError(f"Failed to log audit action: {str(e)}")
    
    # ==================== Read Operations ====================
    
    async def get_log_by_id(self, school_id: str, log_id: str) -> Optional[GLAuditLog]:
        """Get audit log entry by ID
        
        Args:
            school_id: School identifier
            log_id: Audit log ID
            
        Returns:
            GLAuditLog if found, None otherwise
        """
        try:
            result = await self.session.execute(
                select(GLAuditLog).where(
                    and_(
                        GLAuditLog.school_id == school_id,
                        GLAuditLog.id == log_id
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching log {log_id}: {str(e)}")
            return None
    
    async def get_logs_for_entity(
        self,
        school_id: str,
        entity_type: AuditEntityType,
        entity_id: str,
        limit: int = 100,
    ) -> List[GLAuditLog]:
        """Get all audit logs for a specific entity
        
        Returns logs in reverse chronological order (most recent first).
        
        Args:
            school_id: School identifier
            entity_type: Type of entity
            entity_id: Entity ID
            limit: Maximum number of logs to return
            
        Returns:
            List of GLAuditLog records
        """
        try:
            result = await self.session.execute(
                select(GLAuditLog).where(
                    and_(
                        GLAuditLog.school_id == school_id,
                        GLAuditLog.entity_type == entity_type,
                        GLAuditLog.entity_id == entity_id,
                    )
                ).order_by(desc(GLAuditLog.timestamp)).limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching logs for entity {entity_id}: {str(e)}")
            return []
    
    async def get_logs_by_action(
        self,
        school_id: str,
        action: AuditActionType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[GLAuditLog]:
        """Get audit logs for a specific action type
        
        Useful for finding all GL account creations, all reversals, etc.
        
        Args:
            school_id: School identifier
            action: Action type to filter by
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            limit: Maximum number of logs
            
        Returns:
            List of GLAuditLog records
        """
        try:
            query = select(GLAuditLog).where(
                and_(
                    GLAuditLog.school_id == school_id,
                    GLAuditLog.action == action,
                )
            )
            
            if start_date:
                query = query.where(GLAuditLog.timestamp >= start_date)
            
            if end_date:
                query = query.where(GLAuditLog.timestamp <= end_date)
            
            query = query.order_by(desc(GLAuditLog.timestamp)).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching logs by action {action}: {str(e)}")
            return []
    
    async def get_logs_by_user(
        self,
        school_id: str,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[GLAuditLog]:
        """Get all audit logs for actions performed by a user
        
        Useful for user activity audits and fraud investigation.
        
        Args:
            school_id: School identifier
            user_id: User ID to filter by
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            limit: Maximum number of logs
            
        Returns:
            List of GLAuditLog records
        """
        try:
            query = select(GLAuditLog).where(
                and_(
                    GLAuditLog.school_id == school_id,
                    GLAuditLog.user_id == user_id,
                )
            )
            
            if start_date:
                query = query.where(GLAuditLog.timestamp >= start_date)
            
            if end_date:
                query = query.where(GLAuditLog.timestamp <= end_date)
            
            query = query.order_by(desc(GLAuditLog.timestamp)).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching logs by user {user_id}: {str(e)}")
            return []
    
    async def get_logs_by_date_range(
        self,
        school_id: str,
        start_date: datetime,
        end_date: datetime,
        entity_type: Optional[AuditEntityType] = None,
        action: Optional[AuditActionType] = None,
        limit: int = 500,
    ) -> List[GLAuditLog]:
        """Get audit logs within a date range
        
        Useful for period-end audits and compliance procedures.
        
        Args:
            school_id: School identifier
            start_date: Start of date range
            end_date: End of date range
            entity_type: Filter by entity type (optional)
            action: Filter by action type (optional)
            limit: Maximum number of logs
            
        Returns:
            List of GLAuditLog records
        """
        try:
            query = select(GLAuditLog).where(
                and_(
                    GLAuditLog.school_id == school_id,
                    GLAuditLog.timestamp >= start_date,
                    GLAuditLog.timestamp <= end_date,
                )
            )
            
            if entity_type:
                query = query.where(GLAuditLog.entity_type == entity_type)
            
            if action:
                query = query.where(GLAuditLog.action == action)
            
            query = query.order_by(desc(GLAuditLog.timestamp)).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching logs by date range: {str(e)}")
            return []
    
    async def get_logs_by_batch(
        self,
        school_id: str,
        batch_id: str,
    ) -> List[GLAuditLog]:
        """Get all logs in a batch
        
        Batches group related actions (e.g., all logs from a period close).
        
        Args:
            school_id: School identifier
            batch_id: Batch ID
            
        Returns:
            List of GLAuditLog records
        """
        try:
            result = await self.session.execute(
                select(GLAuditLog).where(
                    and_(
                        GLAuditLog.school_id == school_id,
                        GLAuditLog.batch_id == batch_id,
                    )
                ).order_by(GLAuditLog.timestamp)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching logs by batch {batch_id}: {str(e)}")
            return []
    
    # ==================== Analysis Operations ====================
    
    async def get_audit_summary(
        self,
        school_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Get summary of audit activity within a date range
        
        Useful for audit reports and compliance documentation.
        
        Args:
            school_id: School identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with audit activity summary
        """
        try:
            logs = await self.get_logs_by_date_range(
                school_id, start_date, end_date, limit=10000
            )
            
            summary = {
                "period_start": start_date,
                "period_end": end_date,
                "total_actions": len(logs),
                "by_action": {},
                "by_entity_type": {},
                "by_user": {},
                "suspicious_ips": {},
            }
            
            # Count by action type
            for log in logs:
                action_name = log.action.value
                if action_name not in summary["by_action"]:
                    summary["by_action"][action_name] = 0
                summary["by_action"][action_name] += 1
                
                # Count by entity type
                entity_name = log.entity_type.value
                if entity_name not in summary["by_entity_type"]:
                    summary["by_entity_type"][entity_name] = 0
                summary["by_entity_type"][entity_name] += 1
                
                # Count by user
                if log.user_id not in summary["by_user"]:
                    summary["by_user"][log.user_id] = {
                        "name": log.user_name,
                        "role": log.user_role,
                        "count": 0,
                    }
                summary["by_user"][log.user_id]["count"] += 1
                
                # Track suspicious IP changes
                if log.ip_address:
                    if log.ip_address not in summary["suspicious_ips"]:
                        summary["suspicious_ips"][log.ip_address] = {
                            "users": set(),
                            "count": 0,
                        }
                    summary["suspicious_ips"][log.ip_address]["users"].add(log.user_id)
                    summary["suspicious_ips"][log.ip_address]["count"] += 1
            
            # Identify suspicious activity (single IP from multiple users)
            for ip, data in summary["suspicious_ips"].items():
                if len(data["users"]) > 1:
                    data["users"] = list(data["users"])
            
            return summary
        except Exception as e:
            logger.error(f"Error generating audit summary: {str(e)}")
            return {"error": str(e)}
    
    async def get_recent_activity(
        self,
        school_id: str,
        hours: int = 24,
        limit: int = 50,
    ) -> List[GLAuditLog]:
        """Get recent GL audit activity
        
        Useful for dashboards and monitoring.
        
        Args:
            school_id: School identifier
            hours: Number of hours to look back
            limit: Maximum number of logs
            
        Returns:
            List of recent GLAuditLog records
        """
        start_date = datetime.utcnow() - timedelta(hours=hours)
        return await self.get_logs_by_date_range(
            school_id, start_date, datetime.utcnow(), limit=limit
        )
    
    # ==================== Utility Methods ====================
    
    def _generate_change_summary(
        self,
        action: AuditActionType,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate human-readable change summary
        
        Args:
            action: Action that occurred
            old_values: Previous values
            new_values: New values
            
        Returns:
            Human-readable change summary string
        """
        if action == AuditActionType.ACCOUNT_CREATED:
            return f"Created GL account"
        elif action == AuditActionType.ACCOUNT_UPDATED:
            changes = []
            if old_values and new_values:
                for key, new_val in new_values.items():
                    old_val = old_values.get(key)
                    if old_val != new_val:
                        changes.append(f"{key}: {old_val} → {new_val}")
            return f"Updated GL account: {', '.join(changes) if changes else 'No details'}"
        elif action == AuditActionType.ENTRY_POSTED:
            amount = new_values.get("total_debit", 0) if new_values else 0
            return f"Posted journal entry (DR {amount})"
        elif action == AuditActionType.ENTRY_REVERSED:
            return "Reversed journal entry"
        elif action == AuditActionType.EXPENSE_APPROVED:
            return "Approved expense for GL posting"
        elif action == AuditActionType.PERIOD_LOCKED:
            return "Locked fiscal period"
        elif action == AuditActionType.PERIOD_CLOSED:
            return "Closed fiscal period"
        else:
            return f"{action.value} action"
    
    async def export_audit_trail(
        self,
        school_id: str,
        entity_type: AuditEntityType,
        entity_id: str,
        format: str = "list",
    ) -> Dict[str, Any]:
        """Export complete audit trail for an entity
        
        Useful for compliance reports and documentation.
        
        Args:
            school_id: School identifier
            entity_type: Type of entity
            entity_id: Entity ID
            format: Export format ("list" or "detailed")
            
        Returns:
            Audit trail in requested format
        """
        try:
            logs = await self.get_logs_for_entity(
                school_id, entity_type, entity_id, limit=1000
            )
            
            if format == "list":
                return {
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                    "total_records": len(logs),
                    "logs": [
                        {
                            "timestamp": log.timestamp,
                            "action": log.action.value,
                            "user": log.user_name,
                            "summary": log.change_summary,
                        }
                        for log in logs
                    ]
                }
            else:  # detailed
                return {
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                    "total_records": len(logs),
                    "logs": [
                        {
                            "id": log.id,
                            "timestamp": log.timestamp,
                            "action": log.action.value,
                            "user": {
                                "id": log.user_id,
                                "name": log.user_name,
                                "role": log.user_role,
                            },
                            "ip_address": log.ip_address,
                            "old_values": log.old_values,
                            "new_values": log.new_values,
                            "summary": log.change_summary,
                        }
                        for log in logs
                    ]
                }
        except Exception as e:
            logger.error(f"Error exporting audit trail: {str(e)}")
            return {"error": str(e)}
