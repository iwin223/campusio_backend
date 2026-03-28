"""Authentication router"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from models.user import User, UserCreate, UserLogin, UserRole
from database import get_session
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, require_roles
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict)
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    """Register a new user"""
    # Check if email exists
    result = await session.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    if user_data.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot register super admin accounts"
        )
    
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=user_data.role,
        school_id=user_data.school_id
    )
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "school_id": user.school_id,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "last_login": None
        }
    }


@router.post("/login", response_model=dict)
async def login(credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    """Login and get access token"""
    result = await session.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    user.last_login = datetime.utcnow()
    session.add(user)
    await session.commit()
    
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "school_id": user.school_id,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        }
    }


@router.get("/me", response_model=dict)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone": current_user.phone,
        "role": current_user.role,
        "school_id": current_user.school_id,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


@router.get("/users", response_model=list[dict])
async def list_users(
    school_id: str = None,
    role: UserRole = None,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """List users (admin only)"""
    query = select(User)
    
    if current_user.role == UserRole.SCHOOL_ADMIN:
        query = query.where(User.school_id == current_user.school_id)
    elif school_id:
        query = query.where(User.school_id == school_id)
    
    if role:
        query = query.where(User.role == role)
    
    result = await session.execute(query)
    users = result.scalars().all()
    
    return [
        {
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "phone": u.phone,
            "role": u.role,
            "school_id": u.school_id,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None
        }
        for u in users
    ]


@router.put("/users/{user_id}/status", response_model=dict)
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """Enable/disable user account"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.role == UserRole.SCHOOL_ADMIN and user.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user.is_active = is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    
    return {"message": f"User {'enabled' if is_active else 'disabled'} successfully"}
