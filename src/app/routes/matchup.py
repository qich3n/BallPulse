import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..services.history_service import HistoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matchup", tags=["matchup"])

history_service = HistoryService()


class MatchupSummary(BaseModel):
    """Matchup summary model"""
    id: str
    timestamp: str
    team1: str
    team2: str
    predicted_winner: str
    win_probability: float
    confidence: str


class MatchupResponse(BaseModel):
    """Response model for matchups"""
    matchups: List[MatchupSummary]
    total: int


@router.get("", response_model=MatchupResponse)
async def get_matchups(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of matchups to return"),
    team: Optional[str] = Query(None, description="Filter by team name (either team1 or team2)")
) -> MatchupResponse:
    """
    Get recent matchups from history
    
    Args:
        limit: Maximum number of matchups to return (1-100)
        team: Optional filter by team name
        
    Returns:
        MatchupResponse with list of matchup summaries
    """
    try:
        # Get history entries
        entries = history_service.get_history(limit=limit, team1=team, team2=team)
        
        # Convert to matchup summaries
        matchups = []
        for entry in entries:
            matchup = entry.get("result", {}).get("matchup", {})
            matchups.append(MatchupSummary(
                id=entry["id"],
                timestamp=entry["timestamp"],
                team1=entry["team1"],
                team2=entry["team2"],
                predicted_winner=matchup.get("predicted_winner", "Unknown"),
                win_probability=matchup.get("win_probability", 0.5),
                confidence=matchup.get("confidence_label", "Medium")
            ))
        
        return MatchupResponse(matchups=matchups, total=len(matchups))
        
    except Exception as e:
        logger.error(f"Error fetching matchups: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch matchups: {str(e)}"
        )


@router.get("/{entry_id}")
async def get_matchup_detail(entry_id: str):
    """
    Get detailed matchup by history entry ID
    
    Args:
        entry_id: History entry ID
        
    Returns:
        Full matchup result
    """
    try:
        entry = history_service.get_comparison(entry_id)
        if not entry:
            raise HTTPException(
                status_code=404,
                detail=f"Matchup '{entry_id}' not found"
            )
        return entry.get("result")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching matchup detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch matchup detail: {str(e)}"
        )
