"""Fiscal Period Service - Business logic for fiscal period management

Handles the complete lifecycle of fiscal periods:
- Creation and configuration
- Period status transitions (OPEN → LOCKED → CLOSED → ARCHIVED)
- Period validation for posting
- Period-end procedures
- Closing entry management
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func
from datetime import datetime, timedelta

from models.finance.fiscal_period import (
    FiscalPeriod,
    FiscalPeriodStatus,
    FiscalPeriodType,
    FiscalPeriodCreate,
    FiscalPeriodUpdate,
    FiscalPeriodStatusChange,
)

logger = logging.getLogger(__name__)


class FiscalPeriodError(Exception):
    """Base exception for fiscal period service errors"""
    pass


class FiscalPeriodValidationError(FiscalPeriodError):
    """Raised when fiscal period validation fails"""
    pass


class FiscalPeriodService:
    """Service for managing fiscal periods
    
    Fiscal periods control the posting window. No transactions can be posted
    to LOCKED or CLOSED periods. This prevents accidental modifications to
    finalized accounting periods.
    
    Typical workflow:
    1. OPEN - Transactions are posted normally
    2. LOCKED - Period audit is complete, no new postings but data visible
    3. CLOSED - Closing entries are posted, period finalized
    4. ARCHIVED - Moved to archive for historical access
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with async database session
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
    
    # ==================== Create Operations ====================
    
    async def create_period(
        self,
        school_id: str,
        period_data: FiscalPeriodCreate,
        created_by: str,
    ) -> FiscalPeriod:
        """Create a new fiscal period
        
        Args:
            school_id: School identifier
            period_data: Period creation data
            created_by: User ID creating the period
            
        Returns:
            Created FiscalPeriod instance
            
        Raises:
            FiscalPeriodValidationError: If validation fails
        """
        # Validate date range
        if period_data.start_date >= period_data.end_date:
            raise FiscalPeriodValidationError("Period start date must be before end date")
        
        # Check for overlapping periods
        existing = await self.session.execute(
            select(FiscalPeriod).where(
                and_(
                    FiscalPeriod.school_id == school_id,
                    FiscalPeriod.fiscal_year == period_data.fiscal_year,
                    FiscalPeriod.period_type == period_data.period_type,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise FiscalPeriodValidationError(
                f"Period {period_data.period_type} already exists for fiscal year {period_data.fiscal_year}"
            )
        
        # Create period
        period = FiscalPeriod(
            school_id=school_id,
            period_name=period_data.period_name,
            period_type=period_data.period_type,
            start_date=period_data.start_date,
            end_date=period_data.end_date,
            fiscal_year=period_data.fiscal_year,
            status=FiscalPeriodStatus.OPEN,
            allow_posting=True,
            allow_adjustment_entries=True,
            is_current_period=False,
            created_by=created_by,
            notes=period_data.notes,
        )
        
        self.session.add(period)
        await self.session.commit()
        await self.session.refresh(period)
        
        logger.info(
            f"Created fiscal period {period.period_name} for school {school_id} "
            f"({period.start_date.date()} to {period.end_date.date()})"
        )
        
        return period
    
    # ==================== Read Operations ====================
    
    async def get_period_by_id(self, school_id: str, period_id: str) -> Optional[FiscalPeriod]:
        """Get fiscal period by ID
        
        Args:
            school_id: School identifier
            period_id: Period ID
            
        Returns:
            FiscalPeriod if found, None otherwise
        """
        try:
            result = await self.session.execute(
                select(FiscalPeriod).where(
                    and_(
                        FiscalPeriod.school_id == school_id,
                        FiscalPeriod.id == period_id
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching period {period_id}: {str(e)}")
            return None
    
    async def get_all_periods(
        self,
        school_id: str,
        status: Optional[FiscalPeriodStatus] = None,
        fiscal_year: Optional[int] = None,
    ) -> List[FiscalPeriod]:
        """Get all fiscal periods with optional filtering
        
        Args:
            school_id: School identifier
            status: Filter by period status (optional)
            fiscal_year: Filter by fiscal year (optional)
            
        Returns:
            List of FiscalPeriod instances
        """
        try:
            query = select(FiscalPeriod).where(FiscalPeriod.school_id == school_id)
            
            if status:
                query = query.where(FiscalPeriod.status == status)
            
            if fiscal_year:
                query = query.where(FiscalPeriod.fiscal_year == fiscal_year)
            
            # Order by start date, most recent first
            query = query.order_by(FiscalPeriod.start_date.desc())
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching periods for school {school_id}: {str(e)}")
            return []
    
    async def get_current_period(self, school_id: str) -> Optional[FiscalPeriod]:
        """Get the current open fiscal period
        
        Returns the period marked as current_period, or the most recent OPEN period.
        
        Args:
            school_id: School identifier
            
        Returns:
            Current FiscalPeriod, or None if no open period exists
        """
        try:
            # First check for explicitly marked current period
            result = await self.session.execute(
                select(FiscalPeriod).where(
                    and_(
                        FiscalPeriod.school_id == school_id,
                        FiscalPeriod.is_current_period == True,
                    )
                )
            )
            period = result.scalar_one_or_none()
            if period:
                return period
            
            # Fallback: Get most recent OPEN period
            result = await self.session.execute(
                select(FiscalPeriod).where(
                    and_(
                        FiscalPeriod.school_id == school_id,
                        FiscalPeriod.status == FiscalPeriodStatus.OPEN,
                    )
                ).order_by(FiscalPeriod.start_date.desc())
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching current period for school {school_id}: {str(e)}")
            return None
    
    async def get_period_by_date(
        self,
        school_id: str,
        date: datetime,
        status: Optional[FiscalPeriodStatus] = None,
    ) -> Optional[FiscalPeriod]:
        """Get fiscal period containing a specific date
        
        Args:
            school_id: School identifier
            date: Date to find period for
            status: Filter by period status (optional)
            
        Returns:
            FiscalPeriod containing the date, or None if not found
        """
        try:
            query = select(FiscalPeriod).where(
                and_(
                    FiscalPeriod.school_id == school_id,
                    FiscalPeriod.start_date <= date,
                    FiscalPeriod.end_date >= date,
                )
            )
            
            if status:
                query = query.where(FiscalPeriod.status == status)
            
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching period for date {date}: {str(e)}")
            return None
    
    # ==================== Period Status Management ====================
    
    async def can_post_to_period(
        self,
        school_id: str,
        period_id: str,
        is_adjustment_entry: bool = False,
    ) -> tuple[bool, str]:
        """Check if transactions can be posted to a period
        
        Returns (can_post, reason) tuple.
        
        Args:
            school_id: School identifier
            period_id: Period ID to check
            is_adjustment_entry: Is this an adjusting entry? (may have different rules)
            
        Returns:
            Tuple of (can_post: bool, reason: str)
        """
        try:
            period = await self.get_period_by_id(school_id, period_id)
            if not period:
                return False, f"Period {period_id} not found"
            
            # Check period status
            if period.status == FiscalPeriodStatus.OPEN and period.allow_posting:
                return True, "Period is OPEN and allows posting"
            
            # Allow adjusting entries if enabled
            if (is_adjustment_entry and
                period.status == FiscalPeriodStatus.LOCKED and
                period.allow_adjustment_entries):
                return True, "Period allows adjustment entries"
            
            # Otherwise, cannot post
            status_reason = {
                FiscalPeriodStatus.OPEN: "Period does not allow posting",
                FiscalPeriodStatus.LOCKED: f"Period is LOCKED (adjustment entries allowed: {period.allow_adjustment_entries})",
                FiscalPeriodStatus.CLOSED: "Period is CLOSED and immutable",
                FiscalPeriodStatus.ARCHIVED: "Period is ARCHIVED",
            }
            
            return False, status_reason.get(period.status, "Cannot post to this period")
        except Exception as e:
            logger.error(f"Error checking if can post to period {period_id}: {str(e)}")
            return False, f"Error checking posting permission: {str(e)}"
    
    async def lock_period(
        self,
        school_id: str,
        period_id: str,
        locked_by: str,
        notes: Optional[str] = None,
    ) -> Optional[FiscalPeriod]:
        """Lock a fiscal period (end of audit, before closing)
        
        LOCKED periods allow no new postings but data is visible.
        Allows adjustment entries if enabled.
        
        Args:
            school_id: School identifier
            period_id: Period ID to lock
            locked_by: User ID locking the period
            notes: Optional notes about the lock
            
        Returns:
            Locked FiscalPeriod, or None if failed
        """
        try:
            period = await self.get_period_by_id(school_id, period_id)
            if not period:
                logger.warning(f"Cannot lock non-existent period {period_id}")
                return None
            
            if period.status != FiscalPeriodStatus.OPEN:
                raise FiscalPeriodError(
                    f"Cannot lock period in {period.status} status. Only OPEN periods can be locked."
                )
            
            period.status = FiscalPeriodStatus.LOCKED
            period.allow_posting = False
            period.locked_date = datetime.utcnow()
            period.locked_by = locked_by
            if notes:
                period.notes = notes
            period.status_changed_date = datetime.utcnow()
            period.status_changed_by = locked_by
            
            self.session.add(period)
            await self.session.commit()
            await self.session.refresh(period)
            
            logger.info(f"Locked fiscal period {period.period_name} (locked by {locked_by})")
            
            return period
        except Exception as e:
            logger.error(f"Error locking period {period_id}: {str(e)}")
            return None
    
    async def close_period(
        self,
        school_id: str,
        period_id: str,
        closed_by: str,
        notes: Optional[str] = None,
    ) -> Optional[FiscalPeriod]:
        """Close a fiscal period (after closing entries are posted)
        
        CLOSED periods are immutable. No further postings allowed.
        
        Args:
            school_id: School identifier
            period_id: Period ID to close
            closed_by: User ID closing the period
            notes: Optional notes about the close
            
        Returns:
            Closed FiscalPeriod, or None if failed
        """
        try:
            period = await self.get_period_by_id(school_id, period_id)
            if not period:
                logger.warning(f"Cannot close non-existent period {period_id}")
                return None
            
            if period.status not in [FiscalPeriodStatus.OPEN, FiscalPeriodStatus.LOCKED]:
                raise FiscalPeriodError(
                    f"Cannot close period in {period.status} status. "
                    f"Only OPEN or LOCKED periods can be closed."
                )
            
            period.status = FiscalPeriodStatus.CLOSED
            period.allow_posting = False
            period.allow_adjustment_entries = False
            period.closed_date = datetime.utcnow()
            period.closed_by = closed_by
            if notes:
                period.notes = notes
            period.status_changed_date = datetime.utcnow()
            period.status_changed_by = closed_by
            
            self.session.add(period)
            await self.session.commit()
            await self.session.refresh(period)
            
            logger.info(f"Closed fiscal period {period.period_name} (closed by {closed_by})")
            
            return period
        except Exception as e:
            logger.error(f"Error closing period {period_id}: {str(e)}")
            return None
    
    async def set_current_period(
        self,
        school_id: str,
        period_id: str,
    ) -> Optional[FiscalPeriod]:
        """Set a period as the current posting period
        
        Only one period can be current. This updates the is_current_period flag.
        
        Args:
            school_id: School identifier
            period_id: Period ID to set as current
            
        Returns:
            Updated FiscalPeriod, or None if failed
        """
        try:
            # Clear current flag from all periods
            await self.session.execute(
                FiscalPeriod.update().where(
                    and_(
                        FiscalPeriod.school_id == school_id,
                        FiscalPeriod.is_current_period == True,
                    )
                ).values(is_current_period=False)
            )
            
            # Set new current period
            period = await self.get_period_by_id(school_id, period_id)
            if period:
                period.is_current_period = True
                self.session.add(period)
                await self.session.commit()
                await self.session.refresh(period)
                
                logger.info(f"Set {period.period_name} as current period")
                return period
            
            return None
        except Exception as e:
            logger.error(f"Error setting current period: {str(e)}")
            return None
    
    # ==================== Update Operations ====================
    
    async def update_period(
        self,
        school_id: str,
        period_id: str,
        update_data: FiscalPeriodUpdate,
    ) -> Optional[FiscalPeriod]:
        """Update fiscal period details
        
        Args:
            school_id: School identifier
            period_id: Period ID to update
            update_data: Fields to update
            
        Returns:
            Updated FiscalPeriod, or None if failed
        """
        try:
            period = await self.get_period_by_id(school_id, period_id)
            if not period:
                return None
            
            update_dict = update_data.model_dump(exclude_unset=True)
            
            for key, value in update_dict.items():
                setattr(period, key, value)
            
            period.updated_at = datetime.utcnow()
            
            self.session.add(period)
            await self.session.commit()
            await self.session.refresh(period)
            
            logger.info(f"Updated fiscal period {period.period_name}")
            
            return period
        except Exception as e:
            logger.error(f"Error updating period {period_id}: {str(e)}")
            return None
    
    # ==================== Analysis Operations ====================
    
    async def get_period_summary(self, school_id: str) -> Dict[str, Any]:
        """Get summary of all fiscal periods
        
        Useful for dashboard and overview displays.
        
        Args:
            school_id: School identifier
            
        Returns:
            Dictionary with period counts by status and fiscal year
        """
        try:
            periods = await self.get_all_periods(school_id)
            
            summary = {
                "total_periods": len(periods),
                "by_status": {},
                "by_fiscal_year": {},
                "current_period": None,
            }
            
            for status in FiscalPeriodStatus:
                count = sum(1 for p in periods if p.status == status)
                if count > 0:
                    summary["by_status"][status.value] = count
            
            for period in periods:
                fy = period.fiscal_year
                if fy not in summary["by_fiscal_year"]:
                    summary["by_fiscal_year"][fy] = []
                summary["by_fiscal_year"][fy].append({
                    "id": period.id,
                    "name": period.period_name,
                    "status": period.status.value,
                    "type": period.period_type.value,
                })
            
            # Get current period
            current = await self.get_current_period(school_id)
            if current:
                summary["current_period"] = {
                    "id": current.id,
                    "name": current.period_name,
                    "start_date": current.start_date,
                    "end_date": current.end_date,
                    "status": current.status.value,
                }
            
            return summary
        except Exception as e:
            logger.error(f"Error generating period summary for school {school_id}: {str(e)}")
            return {"error": str(e)}
