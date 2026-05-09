"""Seed sample fiscal periods for testing"""
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from models.finance.fiscal_period import FiscalPeriod, FiscalPeriodStatus, FiscalPeriodType
from database import async_engine, async_session

async def seed_fiscal_periods():
    """Create sample fiscal periods"""
    async with async_session() as session:
        # Get a school_id from the database or use a test one
        # For now, using a sample school ID
        school_id = "2df8559b-ebba-4894-a0a5-c522a549b3ab"
        user_id = "system-admin"
        
        # Create fiscal periods for 2026
        periods = []
        
        # Monthly periods for Q1 2026
        period_config = [
            ("January 2026", "2026-01-01", "2026-01-31", 0),
            ("February 2026", "2026-02-01", "2026-02-28", 0),
            ("March 2026", "2026-03-01", "2026-03-31", 0),
            ("April 2026", "2026-04-01", "2026-04-30", 0),
            ("May 2026", "2026-05-01", "2026-05-31", 1),  # Only May is current
            ("June 2026", "2026-06-01", "2026-06-30", 0),
        ]
        
        for name, start_str, end_str, is_current in period_config:
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
            
            period = FiscalPeriod(
                id=str(uuid4()),
                school_id=school_id,
                period_name=name,
                period_type=FiscalPeriodType.MONTHLY,
                start_date=start_date,
                end_date=end_date,
                fiscal_year=2026,
                status=FiscalPeriodStatus.OPEN,
                allow_posting=True,
                allow_adjustment_entries=True,
                is_current_period=(is_current == 1),
                created_by=user_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            periods.append(period)
        
        # Add all periods to session
        for period in periods:
            session.add(period)
        
        # Commit
        await session.commit()
        
        print(f"✅ Created {len(periods)} fiscal periods")
        print(f"   Current period: May 2026")
        for p in periods:
            status = "✓ CURRENT" if p.is_current_period else ""
            print(f"   - {p.period_name} ({p.start_date.date()} to {p.end_date.date()}) {status}")

if __name__ == "__main__":
    asyncio.run(seed_fiscal_periods())
