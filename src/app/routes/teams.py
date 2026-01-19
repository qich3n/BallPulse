import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..providers.basketball_provider import BasketballProvider
from ..services.rate_limiter import limiter, RATE_LIMITS
from nba_api.stats.static import teams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])

basketball_provider = BasketballProvider()


class TeamInfo(BaseModel):
    """Team information model"""
    id: int
    full_name: str
    abbreviation: str
    nickname: str
    city: str
    conference: Optional[str] = None
    division: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class TeamListResponse(BaseModel):
    """Response model for team list"""
    teams: List[TeamInfo]
    total: int


@router.get("", response_model=TeamListResponse)
@limiter.limit(RATE_LIMITS["teams"])
async def get_teams(request: Request, include_stats: bool = False) -> TeamListResponse:
    """
    Get list of all NBA teams
    
    Args:
        request: FastAPI request object (for rate limiting)
        include_stats: Whether to include current season stats for each team
        
    Returns:
        TeamListResponse with list of teams
    """
    try:
        nba_teams = teams.get_teams()
        team_list = []
        
        for team in nba_teams:
            team_info = TeamInfo(
                id=team['id'],
                full_name=team['full_name'],
                abbreviation=team['abbreviation'],
                nickname=team['nickname'],
                city=team['city'],
                conference=team.get('conference'),
                division=team.get('division')
            )
            
            # Optionally fetch stats
            if include_stats:
                try:
                    stats = basketball_provider.get_team_stats_summary(team['full_name'])
                    team_info.stats = stats
                except Exception as e:
                    logger.warning(f"Failed to fetch stats for {team['full_name']}: {e}")
            
            team_list.append(team_info)
        
        return TeamListResponse(teams=team_list, total=len(team_list))
        
    except Exception as e:
        logger.error(f"Error fetching teams: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch teams: {str(e)}"
        )


@router.get("/{team_name}", response_model=TeamInfo)
async def get_team(team_name: str, include_stats: bool = True) -> TeamInfo:
    """
    Get detailed information about a specific team
    
    Args:
        team_name: Name of the team (can be full name, city, or abbreviation)
        include_stats: Whether to include current season stats
        
    Returns:
        TeamInfo with team details
    """
    try:
        nba_teams = teams.get_teams()
        team_name_lower = team_name.lower()
        
        # Try to find team by various name formats
        team = None
        for t in nba_teams:
            if (team_name_lower == t['full_name'].lower() or
                team_name_lower == t['city'].lower() or
                team_name_lower == t['abbreviation'].lower() or
                team_name_lower in t['full_name'].lower() or
                team_name_lower in t['nickname'].lower()):
                team = t
                break
        
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team '{team_name}' not found"
            )
        
        team_info = TeamInfo(
            id=team['id'],
            full_name=team['full_name'],
            abbreviation=team['abbreviation'],
            nickname=team['nickname'],
            city=team['city'],
            conference=team.get('conference'),
            division=team.get('division')
        )
        
        # Fetch stats if requested
        if include_stats:
            try:
                stats = basketball_provider.get_team_stats_summary(team['full_name'])
                team_info.stats = stats
            except Exception as e:
                logger.warning(f"Failed to fetch stats for {team['full_name']}: {e}")
        
        return team_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching team {team_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch team: {str(e)}"
        )
