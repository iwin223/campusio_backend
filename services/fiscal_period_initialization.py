"""Fiscal Period Initialization and Seeding
Provides a function to set up default monthly fiscal periods for new schools
"""
import calendar
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from models.finance.fiscal_period import FiscalPeriod, FiscalPeriodStatus, FiscalPeriodType

logger = logging.getLogger(__name__)


async def seed_default_fiscal_periods(
    session: AsyncSession,
    school_id: str,
    created_by: str = "system",
    fiscal_year: int = None,
) -> Dict[str, Any]:
    """Create the 12 calendar-month fiscal periods for a school's current fiscal year

    This function is called when a new school is created in the system. It populates
    the school with monthly periods so postings have somewhere to land immediately,
    instead of requiring a school_admin to create the first period by hand.

    Args:
        session: Async database session
        school_id: ID of the school to initialize
        created_by: User ID creating the periods (default: "system")
        fiscal_year: Calendar year to seed (defaults to the current year)

    Returns:
        Dictionary with seeding results:
        {
            "success": bool,
            "periods_created": int,
            "errors": List[str]
        }
    """
    now = datetime.utcnow()
    fiscal_year = fiscal_year or now.year
    results = {"success": True, "periods_created": 0, "errors": []}

    try:
        logger.info(f"Seeding default fiscal periods ({fiscal_year}) for school {school_id}")

        periods = []
        for month in range(1, 13):
            last_day = calendar.monthrange(fiscal_year, month)[1]
            start_date = datetime(fiscal_year, month, 1)
            end_date = datetime(fiscal_year, month, last_day, 23, 59, 59)
            is_current = fiscal_year == now.year and month == now.month

            periods.append(FiscalPeriod(
                school_id=school_id,
                period_name=f"{calendar.month_name[month]} {fiscal_year}",
                period_type=FiscalPeriodType.MONTHLY,
                start_date=start_date,
                end_date=end_date,
                fiscal_year=fiscal_year,
                status=FiscalPeriodStatus.OPEN,
                allow_posting=True,
                allow_adjustment_entries=True,
                is_current_period=is_current,
                created_by=created_by,
            ))

        for period in periods:
            session.add(period)
        await session.commit()

        results["periods_created"] = len(periods)
        logger.info(f"Successfully seeded {len(periods)} fiscal periods for school {school_id}")
        return results

    except Exception as e:
        error_msg = f"Critical error seeding fiscal periods for school {school_id}: {str(e)}"
        logger.error(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
        return results
