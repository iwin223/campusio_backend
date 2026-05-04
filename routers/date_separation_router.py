"""API Router for Date Separation & Cutoff Procedures

Endpoints for:
- Entry date vs posting date queries
- Cutoff entry analysis
- Accrual entry management
- Adjusting entries
- Date variance reporting
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from services.date_separation_service import DateSeparationService, DateSeparationError
from models.finance import PostingStatus
from dependencies import get_current_school_id
from auth import get_current_user 
from database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/date-separation", tags=["Date Separation"])


# ==================== Period Posting Eligibility ====================

@router.get("/can-post/{posted_date}", response_model=dict)
async def check_posting_eligibility(
    posted_date: str,
    is_adjusting_entry: bool = Query(False),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Check if an entry can be posted to a specific date
    
    Determines which fiscal period the posting_date falls into and
    checks if postings are allowed for that period.
    
    Rules:
    - Normal entries: Period must be OPEN
    - Adjusting entries: Period can be LOCKED (if allow_adjustment_entries=True)
    - Never post to CLOSED or ARCHIVED periods
    
    Args:
        posted_date: Date for posting (YYYY-MM-DD format)
        is_adjusting_entry: Whether this is an adjusting entry
        school_id: School identifier
        session: Database session
        
    Returns:
        Dictionary with can_post (bool), reason, and period info
        
    Raises:
        HTTPException 400: If date is invalid
    """
    try:
        posted_datetime = datetime.fromisoformat(posted_date)
        
        service = DateSeparationService(session)
        result = await service.can_post_entry_to_period(
            school_id=school_id,
            posted_date=posted_datetime,
            is_adjusting_entry=is_adjusting_entry,
        )
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except DateSeparationError as e:
        logger.warning(f"Error checking posting eligibility: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in posting eligibility check: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check posting eligibility")


# ==================== Cutoff Procedures ====================

@router.get("/cutoff-entries/{period_id}", response_model=dict)
async def get_cutoff_entries(
    period_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get entries with mismatched entry_date and posted_date
    
    Returns entries where the transaction occurred in one period but
    was posted in another (early postings and late postings).
    
    **Use Cases**:
    - Accrued expenses: Entry on 1/31, posted to January
    - Prior period adjustments: Entry on 2/3, posted to January (correcting January error)
    - Late fee postings: Entry on 2/5, posted to January (deferred posting)
    
    Args:
        period_id: Period to analyze
        school_id: School identifier
        session: Database session
        
    Returns:
        Cutoff entries summary with early and late postings
    """
    try:
        service = DateSeparationService(session)
        return await service.get_cutoff_entries(school_id, period_id)
    except DateSeparationError as e:
        logger.warning(f"Error getting cutoff entries: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in cutoff analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze cutoff entries")


@router.get("/accrual-entries/{period_id}", response_model=dict)
async def get_accrual_entries(
    period_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get accrual entries (posted before entry_date)
    
    These are entries posted before the transaction actually occurred,
    commonly used for accruing expenses or revenues.
    
    **Example**: Accrued interest posted on 1/31 for interest earned 2/1-2/15
    
    Args:
        period_id: Period to analyze
        school_id: School identifier
        session: Database session
        
    Returns:
        List of accrual entries with posting vs entry date details
    """
    try:
        service = DateSeparationService(session)
        entries = await service.get_accrual_entries(school_id, period_id)
        
        return {
            "period_id": period_id,
            "count": len(entries),
            "entries": entries,
        }
    except Exception as e:
        logger.error(f"Error getting accrual entries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get accrual entries")


# ==================== Adjusting Entries ====================

@router.get("/adjusting-entries/{period_id}", response_model=dict)
async def get_adjusting_entries(
    period_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get adjusting entries for a period
    
    Adjusting entries are posted after a period is locked/closed to
    record corrections or accruals specific to that period.
    
    Args:
        period_id: Period to query
        school_id: School identifier
        session: Database session
        
    Returns:
        Summary of adjusting entries
    """
    try:
        service = DateSeparationService(session)
        return await service.get_adjusting_entries_for_period(school_id, period_id)
    except DateSeparationError as e:
        logger.warning(f"Error getting adjusting entries: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving adjusting entries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get adjusting entries")


# ==================== Date Range Queries ====================

@router.get("/by-entry-date", response_model=dict)
async def get_entries_by_entry_date(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    posting_status: Optional[str] = Query(None, description="Filter by status"),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get entries by entry_date range (when transaction occurred)
    
    Query all entries where the business transaction occurred within
    the specified date range, regardless of when they were posted to GL.
    
    Args:
        start_date: Start of range (YYYY-MM-DD)
        end_date: End of range (YYYY-MM-DD)
        posting_status: Optional filter (DRAFT, POSTED, REVERSED, REJECTED)
        school_id: School identifier
        session: Database session
        
    Returns:
        List of entries with entry dates in range
    """
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Add end of day to end_date
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        
        status_filter = None
        if posting_status:
            try:
                status_filter = PostingStatus(posting_status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be: DRAFT, POSTED, REVERSED, REJECTED"
                )
        
        service = DateSeparationService(session)
        entries = await service.get_entries_by_entry_date_range(
            school_id=school_id,
            start_date=start_dt,
            end_date=end_dt,
            posting_status=status_filter,
        )
        
        return {
            "query": "by_entry_date",
            "start_date": start_date,
            "end_date": end_date,
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "entry_date": e.entry_date.isoformat(),
                    "posted_date": e.posted_date.isoformat() if e.posted_date else None,
                    "description": e.description,
                    "total_debit": e.total_debit,
                    "total_credit": e.total_credit,
                    "status": e.posting_status.value,
                }
                for e in entries
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error querying by entry date: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to query entries")


@router.get("/by-posting-date", response_model=dict)
async def get_entries_by_posting_date(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get entries by posted_date range (when posted to GL)
    
    Query all entries that were posted to the GL within the specified
    date range (determines which fiscal period they affect).
    
    Args:
        start_date: Start of range (YYYY-MM-DD)
        end_date: End of range (YYYY-MM-DD)
        school_id: School identifier
        session: Database session
        
    Returns:
        List of entries posted within date range
    """
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Add end of day to end_date
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        
        service = DateSeparationService(session)
        entries = await service.get_entries_by_posting_date_range(
            school_id=school_id,
            start_date=start_dt,
            end_date=end_dt,
            posting_status=PostingStatus.POSTED,
        )
        
        return {
            "query": "by_posting_date",
            "start_date": start_date,
            "end_date": end_date,
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "entry_date": e.entry_date.isoformat(),
                    "posted_date": e.posted_date.isoformat() if e.posted_date else None,
                    "description": e.description,
                    "total_debit": e.total_debit,
                    "total_credit": e.total_credit,
                    "fiscal_period_id": e.fiscal_period_id,
                }
                for e in entries
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error querying by posting date: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to query entries")


# ==================== Analysis & Reporting ====================

@router.get("/date-variance-report/{period_id}", response_model=dict)
async def get_date_variance_report(
    period_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Analyze entry_date vs posted_date variance for a period
    
    Shows how entries are distributed by posting timing:
    - Same day: Posted on the entry date
    - Early posted: Posted before the entry date (pre-accruals)
    - Late posted: Posted after the entry date (deferred postings)
    
    Helps identify cutoff practices and accrual policies.
    
    Args:
        period_id: Period to analyze
        school_id: School identifier
        session: Database session
        
    Returns:
        Date variance statistics and distribution
    """
    try:
        service = DateSeparationService(session)
        return await service.get_date_variance_report(school_id, period_id)
    except DateSeparationError as e:
        logger.warning(f"Error generating variance report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in variance analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate variance report")
