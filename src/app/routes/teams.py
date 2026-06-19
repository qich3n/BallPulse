import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..config import cfg
from ..providers import basketball_provider
from ..services.cache_service import CacheService
from ..services.rate_limiter import limiter, RATE_LIMITS
from nba_api.stats.static import teams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])

_cache_cfg = cfg.get("cache", {})
_teams_stats_ttl = _cache_cfg.get("team_score_ttl", 1800)
_teams_stats_cache_key = "teams:nba:include_stats"
_teams_stats_concurrency = 6

cache_service = CacheService(default_ttl=_teams_stats_ttl)


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


def _build_team_info(team: Dict[str, Any], stats: Optional[Dict[str, Any]] = None) -> TeamInfo:
    return TeamInfo(
        id=team['id'],
        full_name=team['full_name'],
        abbreviation=team['abbreviation'],
        nickname=team['nickname'],
        city=team['city'],
        conference=team.get('conference'),
        division=team.get('division'),
        stats=stats,
    )


async def _fetch_team_stats(team: Dict[str, Any], semaphore: asyncio.Semaphore) -> TeamInfo:
    """Fetch stats for one team without blocking the event loop."""
    async with semaphore:
        try:
            stats = await asyncio.to_thread(
                basketball_provider.get_team_stats_summary,
                team['full_name'],
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to fetch stats for %s: %s", team['full_name'], e)
            stats = None
    return _build_team_info(team, stats)


async def _build_teams_with_stats(nba_teams: List[Dict[str, Any]]) -> TeamListResponse:
    semaphore = asyncio.Semaphore(_teams_stats_concurrency)
    team_list = await asyncio.gather(
        *(_fetch_team_stats(team, semaphore) for team in nba_teams)
    )
    return TeamListResponse(teams=list(team_list), total=len(team_list))


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
        if include_stats:
            cached = cache_service.get_by_key(_teams_stats_cache_key)
            if cached is not None:
                logger.info("Returning cached teams list with stats")
                return TeamListResponse(**cached)

        nba_teams = teams.get_teams()

        if include_stats:
            response = await _build_teams_with_stats(nba_teams)
            try:
                cache_service.set_by_key(
                    _teams_stats_cache_key,
                    response.model_dump(),
                    ttl=_teams_stats_ttl,
                )
            except Exception as e:
                logger.warning("Failed to cache teams list: %s", e)
            return response

        team_list = [_build_team_info(team) for team in nba_teams]
        return TeamListResponse(teams=team_list, total=len(team_list))
        
    except Exception as e:
        logger.error("Error fetching teams: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch teams: {str(e)}"
        ) from e


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
        
        stats = None
        if include_stats:
            try:
                stats = basketball_provider.get_team_stats_summary(team['full_name'])
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Failed to fetch stats for %s: %s", team['full_name'], e)
        
        return _build_team_info(team, stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching team %s: %s", team_name, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch team: {str(e)}"
        ) from e
