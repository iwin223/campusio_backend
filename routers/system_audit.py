"""System-wide audit trail viewer. Super admin only."""
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_session
from auth import require_roles
from models.user import User, UserRole
from models.audit import SystemAuditLog

router = APIRouter(prefix="/system-audit", tags=["System Audit"])


@router.get("", response_model=dict)
async def list_audit_logs(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    school_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    """Paginated, filterable system-wide audit trail."""
    query = select(SystemAuditLog)
    count_query = select(func.count(SystemAuditLog.id))

    if action:
        query = query.where(SystemAuditLog.action == action)
        count_query = count_query.where(SystemAuditLog.action == action)
    if entity_type:
        query = query.where(SystemAuditLog.entity_type == entity_type)
        count_query = count_query.where(SystemAuditLog.entity_type == entity_type)
    if actor_id:
        query = query.where(SystemAuditLog.actor_id == actor_id)
        count_query = count_query.where(SystemAuditLog.actor_id == actor_id)
    if school_id:
        query = query.where(SystemAuditLog.school_id == school_id)
        count_query = count_query.where(SystemAuditLog.school_id == school_id)

    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(SystemAuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await session.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "actor_name": log.actor_name,
                "actor_role": log.actor_role,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "summary": log.summary,
                "school_id": log.school_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 1,
    }


@router.get("/actions", response_model=list)
async def list_distinct_actions(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    """Distinct action names seen so far, for a filter dropdown."""
    result = await session.execute(select(SystemAuditLog.action).distinct())
    return sorted(row[0] for row in result.all())
