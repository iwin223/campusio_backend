#!/usr/bin/env python3
"""
Management Script: Initialize Chart of Accounts for Schools

Usage:
    python scripts/init_finance.py                    # Initialize all schools
    python scripts/init_finance.py --school-id=ID     # Initialize specific school
    python scripts/init_finance.py --school-id=ID --dry-run  # Test without applying

This script:
1. Connects to the database
2. Finds schools that don't have GL accounts
3. Seeds default Chart of Accounts for each
4. Validates the setup
"""
import asyncio
import argparse
import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.school import School
from models.finance import GLAccount
from services.coa_initialization import seed_default_chart_of_accounts
from config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


async def get_database_session():
    """Create async database session"""
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    return async_session, engine


async def get_schools_without_coa(session: AsyncSession) -> list:
    """Get all schools that don't have GL accounts"""
    try:
        # Get all schools
        result = await session.execute(select(School))
        schools = result.scalars().all()
        
        schools_without_coa = []
        
        for school in schools:
            # Check if school has any GL accounts
            result = await session.execute(
                select(GLAccount).where(GLAccount.school_id == school.id)
            )
            if not result.scalar_one_or_none():
                schools_without_coa.append(school)
        
        return schools_without_coa
    except Exception as e:
        logger.error(f"Error fetching schools: {str(e)}")
        return []


async def initialize_school_finance(session: AsyncSession, school_id: str, dry_run: bool = False):
    """Initialize Chart of Accounts for a school"""
    try:
        # Verify school exists
        result = await session.execute(select(School).where(School.id == school_id))
        school = result.scalar_one_or_none()
        
        if not school:
            logger.error(f"School {school_id} not found")
            return {"success": False, "error": "School not found"}
        
        # Check if already has CoA
        result = await session.execute(
            select(GLAccount).where(GLAccount.school_id == school_id).limit(1)
        )
        if result.scalar_one_or_none():
            logger.warning(f"School {school_id} already has Chart of Accounts")
            return {"success": False, "error": "CoA already initialized"}
        
        if dry_run:
            logger.info(f"[DRY RUN] Would initialize {school.name} ({school_id})")
            return {"success": True, "dry_run": True}
        
        logger.info(f"Initializing Chart of Accounts for {school.name} ({school_id})...")
        
        result = await seed_default_chart_of_accounts(
            session=session,
            school_id=school_id,
            created_by="system"
        )
        
        if result["success"]:
            logger.info(
                f"✓ Successfully initialized {result['accounts_created']} GL accounts "
                f"for school {school.name}"
            )
        else:
            logger.error(
                f"✗ Failed to initialize CoA for {school.name}. "
                f"Errors: {result.get('errors', [])}"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error initializing school {school_id}: {str(e)}")
        return {"success": False, "error": str(e)}


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Initialize Chart of Accounts for schools"
    )
    parser.add_argument(
        "--school-id",
        type=str,
        help="Initialize specific school by ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - show what would happen without applying"
    )
    
    args = parser.parse_args()
    
    # Create database session
    async_session, engine = await get_database_session()
    
    try:
        async with async_session() as session:
            if args.school_id:
                # Initialize specific school
                logger.info(f"Initializing Chart of Accounts for school {args.school_id}")
                result = await initialize_school_finance(
                    session=session,
                    school_id=args.school_id,
                    dry_run=args.dry_run
                )
                
                if result["success"]:
                    print(f"\n✓ Success: {result['accounts_created']} accounts created")
                else:
                    print(f"\n✗ Failed: {result.get('error', 'Unknown error')}")
                    sys.exit(1)
            else:
                # Initialize all schools without CoA
                logger.info("Finding schools without Chart of Accounts...")
                schools = await get_schools_without_coa(session)
                
                if not schools:
                    logger.info("All schools already have Chart of Accounts initialized")
                    return
                
                logger.info(f"Found {len(schools)} schools needing CoA initialization:")
                for school in schools:
                    logger.info(f"  - {school.name} ({school.id})")
                
                total_success = 0
                total_failed = 0
                
                for school in schools:
                    result = await initialize_school_finance(
                        session=session,
                        school_id=school.id,
                        dry_run=args.dry_run
                    )
                    
                    if result["success"]:
                        total_success += 1
                    else:
                        total_failed += 1
                
                print(f"\n{'=' * 50}")
                print(f"Summary: {total_success} schools initialized, {total_failed} failed")
                
                if total_failed > 0:
                    sys.exit(1)
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
