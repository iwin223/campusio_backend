"""Update fiscal periods to have correct current flag"""
import asyncio
from datetime import datetime
from sqlalchemy import update
from models.finance.fiscal_period import FiscalPeriod
from database import async_session

async def fix_current_periods():
    """Set only May 2026 as current"""
    async with async_session() as session:
        # First, set all to not current
        stmt = update(FiscalPeriod).values(is_current_period=False)
        await session.execute(stmt)
        
        # Then set May 2026 as current
        school_id = "2df8559b-ebba-4894-a0a5-c522a549b3ab"
        stmt = update(FiscalPeriod).where(
            (FiscalPeriod.school_id == school_id) &
            (FiscalPeriod.period_name == "May 2026")
        ).values(is_current_period=True)
        result = await session.execute(stmt)
        
        await session.commit()
        
        print(f"✅ Updated fiscal periods - May 2026 is now the current period")

if __name__ == "__main__":
    asyncio.run(fix_current_periods())
