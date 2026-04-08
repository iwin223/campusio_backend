"""Database Migration Guide and Helper Functions for Finance Module

This module provides utilities for running migrations and initializing
the Chart of Accounts for new schools.
"""
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from services.coa_initialization import seed_default_chart_of_accounts

logger = logging.getLogger(__name__)


async def initialize_school_chart_of_accounts(
    session: AsyncSession,
    school_id: str,
    created_by: str = "system"
) -> dict:
    """Initialize a new school's Chart of Accounts with defaults
    
    This function should be called:
    1. After a new school is created
    2. After database migrations have run
    3. To set up the default GL accounts
    
    Args:
        session: Async database session
        school_id: ID of the school to initialize
        created_by: User ID creating the accounts (default: "system")
        
    Returns:
        Dictionary with seeding results
        
    Example:
        result = await initialize_school_chart_of_accounts(
            session=db_session,
            school_id="school_123",
            created_by="admin_user_id"
        )
        print(f"Created {result['accounts_created']} accounts")
    """
    logger.info(f"Initializing Chart of Accounts for school {school_id}")
    
    result = await seed_default_chart_of_accounts(session, school_id, created_by)
    
    if result["success"]:
        logger.info(
            f"✓ Successfully initialized {result['accounts_created']} accounts "
            f"for school {school_id}"
        )
    else:
        logger.error(
            f"✗ Failed to initialize CoA for school {school_id}. "
            f"Errors: {result['errors']}"
        )
    
    return result
