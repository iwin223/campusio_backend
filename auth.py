"""Authentication utilities"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from models.user import User, UserRole
from database import get_session
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# 🚀 OPTIMIZATION: Redis cache for user authentication
# Reduces database hits from every request to only cache misses
_redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get or create Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            # Use REDIS_URL from config (Render provides this)
            redis_url = settings.redis_url
            
            # Try to connect to Redis
            _redis_client = await redis.from_url(
                redis_url,
                encoding="utf8",
                decode_responses=True,
                socket_connect_timeout=5
            )
            await _redis_client.ping()
            logger.info("✓ Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"⚠ Redis cache unavailable ({e}), falling back to database queries")
            _redis_client = None
    return _redis_client

async def close_redis():
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)



async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Get the current authenticated user from JWT token with caching"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # 🚀 OPTIMIZATION: Try cache first (0.1ms vs 5-10ms DB hit)
    redis_client = await get_redis()
    cache_key = f"user:{user_id}"
    user = None
    
    if redis_client:
        try:
            cached_user = await redis_client.get(cache_key)
            if cached_user:
                try:
                    user_dict = json.loads(cached_user)
                    # Reconstruct User object from cached dict
                    user = User(**user_dict)
                    logger.debug(f"User {user_id} loaded from cache")
                except Exception as e:
                    logger.warning(f"Error deserializing cached user: {e}")
                    user = None
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")
    
    # Cache miss or Redis unavailable - query database
    if user is None:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
        
        # Cache the user for 15 minutes
        if redis_client:
            try:
                user_dict = {
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role.value if user.role else None,
                    "is_active": user.is_active,
                    "school_id": str(user.school_id) if user.school_id else None,
                }
                await redis_client.setex(
                    cache_key,
                    900,  # 15 minutes TTL
                    json.dumps(user_dict)
                )
                logger.debug(f"User {user_id} cached for 15 minutes")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    
    return user


def require_roles(*roles: UserRole):
    """Dependency to require specific roles"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}"
            )
        return current_user
    return role_checker


def require_school_access(current_user: User = Depends(get_current_user)) -> User:
    """Require user to have school_id (non-super admin)"""
    if current_user.role == UserRole.SUPER_ADMIN:
        return current_user
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any school"
        )
    return current_user
