"""Authentication router with OTP support"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from models.user import User, UserCreate, UserLogin, UserRole
from models.otp import (
    OTPVerificationRequest, OTPVerificationResponse, OTPSettings,
    OTPAdminSettings, OTPAdminSettingsRequest, OTPAdminSettingsResponse
)
from database import get_session
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, require_roles
)
from utils.otp import (
    create_otp, verify_otp, send_otp_email, send_otp_sms,
    get_otp_settings, create_or_update_otp_settings,
    get_admin_otp_settings, create_or_update_admin_otp_settings
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Roles that require mandatory OTP
MANDATORY_OTP_ROLES = {UserRole.SCHOOL_ADMIN, UserRole.HR}


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
    
    # Create OTP settings (mandatory for sensitive roles, optional for others)
    is_mandatory = user.role in MANDATORY_OTP_ROLES
    await create_or_update_otp_settings(
        session=session,
        user_id=user.id,
        is_enabled=is_mandatory,
        method="email"  # Default to email
    )
    
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
    """
    Step 1: Login with email and password.
    Returns temporary token and whether OTP is required.
    """
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
    
    # Get OTP settings for user
    otp_settings = await get_otp_settings(session, user.id)
    otp_required = otp_settings and otp_settings.is_enabled
    
    if otp_required:
        # Generate OTP and send it
        otp_code, otp_id = await create_otp(session, user.id)
        
        # Send OTP via email or SMS based on settings
        if otp_settings.method == "sms" and user.phone:
            send_otp_sms(user.phone, otp_code)
        else:
            send_otp_email(user.email, otp_code, f"{user.first_name} {user.last_name}")
        
        # Create temporary token valid for 10 minutes
        temp_token = create_access_token(
            data={
                "sub": user.id,
                "type": "otp_pending",
                "otp_id": otp_id
            },
            expires_delta=None  # Use default 10 minutes
        )
        
        return {
            "status": "otp_required",
            "temporary_token": temp_token,
            "otp_method": otp_settings.method,
            "message": f"OTP sent to {otp_settings.method}"
        }
    
    else:
        # No OTP required, proceed directly to login
        user.last_login = datetime.utcnow()
        session.add(user)
        await session.commit()
        
        access_token = create_access_token(data={"sub": user.id})
        
        return {
            "status": "authenticated",
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


@router.post("/verify-otp", response_model=dict)
async def verify_otp_code(
    verification: OTPVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Step 2: Verify OTP code and get access token.
    """
    # Get user
    result = await session.execute(select(User).where(User.email == verification.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email"
        )
    
    # Verify OTP
    try:
        await verify_otp(session, user.id, verification.otp_code)
    except HTTPException as e:
        raise e
    
    # Update last login and create final access token
    user.last_login = datetime.utcnow()
    session.add(user)
    await session.commit()
    
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "status": "authenticated",
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


@router.post("/resend-otp", response_model=dict)
async def resend_otp(
    email: str,
    session: AsyncSession = Depends(get_session)
):
    """Resend OTP to user"""
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    otp_settings = await get_otp_settings(session, user.id)
    
    if not otp_settings or not otp_settings.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not enabled for this user"
        )
    
    # Generate and send OTP
    otp_code, otp_id = await create_otp(session, user.id)
    
    if otp_settings.method == "sms" and user.phone:
        success = send_otp_sms(user.phone, otp_code)
    else:
        success = send_otp_email(user.email, otp_code, f"{user.first_name} {user.last_name}")
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP via {otp_settings.method}"
        )
    
    return {
        "message": f"OTP resent to {otp_settings.method}",
        "otp_method": otp_settings.method
    }


@router.get("/otp-settings", response_model=dict)
async def get_otp_settings_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get user's OTP settings"""
    otp_settings = await get_otp_settings(session, current_user.id)
    
    return {
        "is_enabled": otp_settings.is_enabled if otp_settings else False,
        "is_mandatory": otp_settings.is_mandatory if otp_settings else False,
        "method": otp_settings.method if otp_settings else "email",
        "user_id": current_user.id
    }


@router.post("/otp-settings/update", response_model=dict)
async def update_otp_settings(
    is_enabled: bool,
    method: str = "email",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update user's OTP settings"""
    if current_user.role in MANDATORY_OTP_ROLES and not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"OTP is mandatory for {current_user.role} role"
        )
    
    if method not in ["email", "sms"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Method must be 'email' or 'sms'"
        )
    
    otp_settings = await create_or_update_otp_settings(
        session=session,
        user_id=current_user.id,
        is_enabled=is_enabled,
        method=method
    )
    
    return {
        "message": "OTP settings updated",
        "is_enabled": otp_settings.is_enabled,
        "method": otp_settings.method
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


# ==================== ADMIN OTP SETTINGS ENDPOINTS ====================

@router.get("/admin/otp-settings", response_model=dict)
async def get_admin_otp_settings_endpoint(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """
    Get OTP settings for the school (admin only)
    
    Only Super Admin and School Admin can access
    """
    # Get the school_id from current user
    # Super admin manages all schools, so school_id is None
    # School admin manages their specific school
    school_id = current_user.school_id if current_user.role == UserRole.SCHOOL_ADMIN else None
    
    settings = await get_admin_otp_settings(session, school_id)
    
    if not settings:
        # Return default settings if none exist
        return {
            "is_enabled": True,
            "expiry_minutes": 10,
            "max_attempts": 3,
            "default_method": "sms",
            "require_for_roles": ["school_admin", "hr"]
        }
    
    return {
        "is_enabled": settings.is_enabled,
        "expiry_minutes": settings.expiry_minutes,
        "max_attempts": settings.max_attempts,
        "default_method": settings.default_method,
        "require_for_roles": settings.require_for_roles.split(",")
    }


@router.put("/admin/otp-settings", response_model=dict)
async def update_admin_otp_settings(
    settings_request: OTPAdminSettingsRequest,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
    session: AsyncSession = Depends(get_session)
):
    """
    Update OTP settings for the school (admin only)
    
    Only Super Admin and School Admin can update
    """
    # Get the school_id from current user
    # Super admin manages all schools, so school_id is None
    # School admin manages their specific school
    school_id = current_user.school_id if current_user.role == UserRole.SCHOOL_ADMIN else None
    
    try:
        settings = await create_or_update_admin_otp_settings(
            session=session,
            school_id=school_id,
            is_enabled=settings_request.is_enabled,
            expiry_minutes=settings_request.expiry_minutes,
            max_attempts=settings_request.max_attempts,
            default_method=settings_request.default_method,
            require_for_roles=settings_request.require_for_roles
        )
        
        return {
            "message": "OTP admin settings updated successfully",
            "is_enabled": settings.is_enabled,
            "expiry_minutes": settings.expiry_minutes,
            "max_attempts": settings.max_attempts,
            "default_method": settings.default_method,
            "require_for_roles": settings.require_for_roles.split(",")
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update OTP settings: {str(e)}"
        )
