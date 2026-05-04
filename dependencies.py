"""
Shared dependencies for all routers
Centralizes authentication, database, and user context injection
"""
import logging
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from auth import get_current_user
from database import get_session
from models.user import User

logger = logging.getLogger(__name__)

# Alias get_session as get_db for consistency with codebase
get_db = get_session


async def get_current_school_id(current_user: User = Depends(get_current_user)) -> str:
    """Extract school_id from current user
    
    Used to automatically scope all queries to the user's school.
    SUPER_ADMIN can access any school (school_id will be from user selection).
    Regular users can only access their assigned school.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        School ID string
        
    Raises:
        HTTPException 403: If user has no school access
    """
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any school"
        )
    return str(current_user.school_id)


# Re-export commonly used dependencies for convenience
__all__ = [
    "get_db",
    "get_session", 
    "get_current_user",
    "get_current_school_id",
]
