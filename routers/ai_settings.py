"""Per-school BYOK AI settings for report card comment generation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database import get_session
from auth import get_current_user
from models.user import User, UserRole
from models.ai_settings import SchoolAISettings, AIProvider, AISettingsResponse, UpdateAISettingsRequest
from services.ai_key_crypto import encrypt_api_key

router = APIRouter(prefix="/ai-settings", tags=["AI Settings"])

VALID_PROVIDERS = {p.value for p in AIProvider}


def _require_school_admin(current_user: User) -> None:
    if current_user.role != UserRole.SCHOOL_ADMIN:
        raise HTTPException(status_code=403, detail="Only a school admin can manage AI settings")
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="No school associated with this account")


@router.get("", response_model=AISettingsResponse)
async def get_ai_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Whether this school has a BYOK AI provider configured. Never returns the key."""
    _require_school_admin(current_user)
    result = await session.execute(
        select(SchoolAISettings).where(SchoolAISettings.school_id == current_user.school_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        return AISettingsResponse(configured=False, enabled=False)
    return AISettingsResponse(
        configured=True, enabled=settings.enabled,
        provider=settings.provider, model=settings.model,
    )


@router.put("", response_model=AISettingsResponse)
async def update_ai_settings(
    body: UpdateAISettingsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save (or replace) this school's BYOK provider + API key. Key is encrypted at rest."""
    _require_school_admin(current_user)
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"provider must be one of: {', '.join(sorted(VALID_PROVIDERS))}")
    if not body.api_key or not body.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key is required")

    result = await session.execute(
        select(SchoolAISettings).where(SchoolAISettings.school_id == current_user.school_id)
    )
    settings = result.scalar_one_or_none()
    encrypted = encrypt_api_key(body.api_key.strip())

    if settings:
        settings.provider = body.provider
        settings.api_key_encrypted = encrypted
        settings.model = body.model
        settings.enabled = body.enabled
        settings.updated_at = datetime.utcnow()
        settings.updated_by = current_user.id
    else:
        settings = SchoolAISettings(
            school_id=current_user.school_id,
            provider=body.provider,
            api_key_encrypted=encrypted,
            model=body.model,
            enabled=body.enabled,
            updated_by=current_user.id,
        )
        session.add(settings)

    await session.commit()
    return AISettingsResponse(
        configured=True, enabled=settings.enabled,
        provider=settings.provider, model=settings.model,
    )


@router.delete("", response_model=AISettingsResponse)
async def delete_ai_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove this school's stored key entirely (reverts to the free template engine)."""
    _require_school_admin(current_user)
    result = await session.execute(
        select(SchoolAISettings).where(SchoolAISettings.school_id == current_user.school_id)
    )
    settings = result.scalar_one_or_none()
    if settings:
        await session.delete(settings)
        await session.commit()
    return AISettingsResponse(configured=False, enabled=False)
