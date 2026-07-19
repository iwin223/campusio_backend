"""System-wide audit log — every mutating action a super admin cares about,
across every module, not just finance (see models/finance/gl_audit_log.py for
the older GL-specific trail).

action/entity_type are plain strings, not native Postgres enums, deliberately
— this codebase has been bitten repeatedly by enum name/value mismatches, and
a system-wide log needs to accept new action names from any module without a
migration every time. Logs are append-only; nothing here ever updates or
deletes a row.
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class SystemAuditLog(SQLModel, table=True):
    __tablename__ = "system_audit_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    # WHO
    actor_id: str = Field(index=True)
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None

    # WHAT
    action: str = Field(index=True)          # e.g. "user.created", "school.deleted"
    entity_type: str = Field(index=True)      # e.g. "user", "school", "ticket"
    entity_id: Optional[str] = Field(default=None, index=True)
    summary: str                              # human-readable one-liner

    # SCOPE — which school this action affects, if any (None = platform-level)
    school_id: Optional[str] = Field(default=None, index=True)

    # DETAIL
    old_values: Optional[str] = None          # JSON string
    new_values: Optional[str] = None          # JSON string
    ip_address: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class SystemAuditLogResponse(SQLModel):
    id: str
    actor_id: str
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    summary: str
    school_id: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
