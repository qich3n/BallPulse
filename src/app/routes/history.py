import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from ..services.history_service import HistoryService
from ..services.rate_limiter import limiter, RATE_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["history"])

history_service = HistoryService()


class HistoryEntry(BaseModel):
    """History entry model"""
    id: str
    timestamp: str
    team1: str
    team2: str
    sport: str
    predicted_winner: Optional[str] = None
    win_probability: Optional[float] = None


class HistoryResponse(BaseModel):
    """Response model for history"""
    entries: List[HistoryEntry]
    total: int


@router.get("", response_model=HistoryResponse)
@limiter.limit(RATE_LIMITS["history"])
async def get_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of entries to return"),
    team1: Optional[str] = Query(None, description="Filter by team1 name"),
    team2: Optional[str] = Query(None, description="Filter by team2 name")
) -> HistoryResponse:
    """
    Get comparison history
    
    Args:
        request: FastAPI request object (for rate limiting)
        limit: Maximum number of entries to return (1-200)
        team1: Optional filter by team1 name
        team2: Optional filter by team2 name
        
    Returns:
        HistoryResponse with list of history entries
    """
    try:
        entries = history_service.get_history(limit=limit, team1=team1, team2=team2)
        
        # Convert to response model (excluding full result data for list view)
        history_entries = [
            HistoryEntry(
                id=entry["id"],
                timestamp=entry["timestamp"],
                team1=entry["team1"],
                team2=entry["team2"],
                sport=entry["sport"],
                predicted_winner=entry.get("predicted_winner"),
                win_probability=entry.get("win_probability")
            )
            for entry in entries
        ]
        
        return HistoryResponse(entries=history_entries, total=len(history_entries))
        
    except Exception as e:
        logger.error("Error fetching history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch history: {str(e)}"
        ) from e


@router.get("/{entry_id}")
async def get_comparison_detail(entry_id: str):
    """
    Get detailed comparison result by history entry ID
    
    Args:
        entry_id: History entry ID
        
    Returns:
        Full comparison result
    """
    try:
        entry = history_service.get_comparison(entry_id)
        if not entry:
            raise HTTPException(
                status_code=404,
                detail=f"History entry '{entry_id}' not found"
            )
        return entry.get("result")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching comparison detail: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch comparison detail: {str(e)}"
        ) from e


@router.delete("")
async def clear_history():
    """
    Clear all comparison history
    
    Returns:
        Number of entries cleared
    """
    try:
        count = history_service.clear_history()
        return {"message": f"Cleared {count} history entries", "count": count}
    except Exception as e:
        logger.error("Error clearing history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear history: {str(e)}"
        ) from e
