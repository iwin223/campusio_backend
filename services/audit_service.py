"""One-line audit logging for any router. Call log_event() right after a
mutation commits — never let a logging failure break the actual request, so
failures here are swallowed (and printed) rather than raised.
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import SystemAuditLog
from models.user import User

logger = logging.getLogger(__name__)


def _serialize(values: Optional[dict[str, Any]]) -> Optional[str]:
    if values is None:
        return None
    try:
        return json.dumps(values, default=str)
    except (TypeError, ValueError):
        return None


async def log_event(
    session: AsyncSession,
    actor: User,
    action: str,
    entity_type: str,
    summary: str,
    entity_id: Optional[str] = None,
    school_id: Optional[str] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Record a system audit log entry. Commits independently of the caller's
    transaction state — safe to call after the caller's own session.commit()."""
    try:
        entry = SystemAuditLog(
            actor_id=actor.id,
            actor_name=f"{actor.first_name} {actor.last_name}".strip(),
            actor_role=actor.role.value if hasattr(actor.role, "value") else str(actor.role),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            school_id=school_id,
            old_values=_serialize(old_values),
            new_values=_serialize(new_values),
            ip_address=ip_address,
        )
        session.add(entry)
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log ({action} on {entity_type}): {e}")
