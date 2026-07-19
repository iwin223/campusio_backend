"""Per-school BYOK settings for AI-assisted report card comments.

Never required — services/comment_generator_service.py is the free default.
This table only exists for schools that opt in to using their own
OpenAI/Anthropic/Gemini API key for higher-quality generated remarks.
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class AIProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class SchoolAISettings(SQLModel, table=True):
    """Stored as a plain String column for provider (not a native Postgres
    enum) deliberately — this codebase has been bitten repeatedly by
    native-enum name/value mismatches."""
    __tablename__ = "school_ai_settings"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True, unique=True)
    provider: str
    api_key_encrypted: str
    model: Optional[str] = None
    enabled: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str


class AISettingsResponse(SQLModel):
    configured: bool
    enabled: bool
    provider: Optional[str] = None
    model: Optional[str] = None


class UpdateAISettingsRequest(SQLModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    enabled: bool = True
