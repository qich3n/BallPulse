"""
ESPN API Routes

Provides endpoints for accessing ESPN data including:
- Live scores/scoreboard
- Team information
- News
- Injuries
- Standings
- Game details
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from ..providers.espn_provider import ESPNProvider, Sport, League

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/espn", tags=["ESPN"])

# Initialize provider (default: NBA)
_providers = {}


def get_provider(sport: str = "basketball", league: str = "nba") -> ESPNProvider:
    """Get or create an ESPN provider for the given sport/league"""
    key = f"{sport}:{league}"
    if key not in _providers:
        try:
            sport_enum = Sport(sport)
            league_enum = League(league)
            _providers[key] = ESPNProvider(sport=sport_enum, league=league_enum)
        except ValueError:
            # Default to NBA if invalid
            _providers[key] = ESPNProvider()
    return _providers[key]


# ==================== SCOREBOARD ====================

@router.get("/scores")
async def get_scores(
    sport: str = Query("basketball", description="Sport (basketball, football, baseball, hockey, soccer)"),
    league: str = Query("nba", description="League (nba, nfl, mlb, nhl, mens-college-basketball, etc.)"),
    date: Optional[str] = Query(None, description="Date in YYYYMMDD format")
):
    """
    Get today's scores or scores for a specific date
    
    Returns live, scheduled, and completed games with scores, teams, and status.
    """
    try:
        provider = get_provider(sport, league)
        
        if date:
            scoreboard = provider.get_scoreboard(date=date)
            return scoreboard
        else:
            scores = provider.get_today_scores()
            return {
                "sport": sport,
                "league": league,
                "games": scores,
                "count": len(scores)
            }
    except Exception as e:
        logger.error("Error fetching scores: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/scores/live")
async def get_live_scores(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get only currently live/in-progress games
    """
    try:
        provider = get_provider(sport, league)
        all_scores = provider.get_today_scores()
        
        live_games = [
            game for game in all_scores
            if game.get("status") in ["In Progress", "Halftime", "End of Period"]
        ]
        
        return {
            "sport": sport,
            "league": league,
            "live_games": live_games,
            "count": len(live_games)
        }
    except Exception as e:
        logger.error("Error fetching live scores: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== TEAMS ====================

@router.get("/teams")
async def get_all_teams(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get list of all teams in the league
    """
    try:
        provider = get_provider(sport, league)
        teams = provider.get_all_teams()
        return {
            "sport": sport,
            "league": league,
            "teams": teams,
            "count": len(teams)
        }
    except Exception as e:
        logger.error("Error fetching teams: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/teams/{team_identifier}")
async def get_team(
    team_identifier: str,
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get detailed information about a specific team
    
    Args:
        team_identifier: Team name, abbreviation (e.g., 'LAL'), or ESPN ID
    """
    try:
        provider = get_provider(sport, league)
        team = provider.get_team(team_identifier)
        
        if not team:
            raise HTTPException(status_code=404, detail=f"Team '{team_identifier}' not found")
        
        return team
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching team %s: %s", team_identifier, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/teams/{team_identifier}/schedule")
async def get_team_schedule(
    team_identifier: str,
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League"),
    season: Optional[int] = Query(None, description="Season year")
):
    """
    Get schedule for a specific team
    """
    try:
        provider = get_provider(sport, league)
        schedule = provider.get_team_schedule(team_identifier, season=season)
        
        return {
            "team": team_identifier,
            "schedule": schedule,
            "count": len(schedule)
        }
    except Exception as e:
        logger.error("Error fetching schedule for %s: %s", team_identifier, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/teams/{team_identifier}/news")
async def get_team_news(
    team_identifier: str,
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get news articles for a specific team
    """
    try:
        provider = get_provider(sport, league)
        news = provider.get_team_news(team_identifier)
        
        return {
            "team": team_identifier,
            "articles": news,
            "count": len(news)
        }
    except Exception as e:
        logger.error("Error fetching news for %s: %s", team_identifier, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== NEWS ====================

@router.get("/news")
async def get_news(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League"),
    limit: int = Query(25, description="Maximum number of articles", le=100)
):
    """
    Get latest news articles for the league
    """
    try:
        provider = get_provider(sport, league)
        articles = provider.get_news(limit=limit)
        
        return {
            "sport": sport,
            "league": league,
            "articles": articles,
            "count": len(articles)
        }
    except Exception as e:
        logger.error("Error fetching news: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== INJURIES ====================

@router.get("/injuries")
async def get_injuries(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League"),
    team: Optional[str] = Query(None, description="Filter by team name/abbreviation")
):
    """
    Get injury reports for the league
    
    Optionally filter by team.
    """
    try:
        provider = get_provider(sport, league)
        injuries = provider.get_injuries(team_name=team)
        
        return {
            "sport": sport,
            "league": league,
            "team_filter": team,
            "injuries": injuries,
            "count": len(injuries)
        }
    except Exception as e:
        logger.error("Error fetching injuries: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/injuries/{team_identifier}")
async def get_team_injuries(
    team_identifier: str,
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get injuries for a specific team
    """
    try:
        provider = get_provider(sport, league)
        injuries = provider.get_team_injuries(team_identifier)
        
        return {
            "team": team_identifier,
            "injuries": injuries,
            "count": len(injuries)
        }
    except Exception as e:
        logger.error("Error fetching injuries for %s: %s", team_identifier, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== STANDINGS ====================

@router.get("/standings")
async def get_standings(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get current league standings organized by conference/division
    """
    try:
        provider = get_provider(sport, league)
        standings = provider.get_standings()
        
        return {
            "sport": sport,
            "league": league,
            "standings": standings
        }
    except Exception as e:
        logger.error("Error fetching standings: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== GAME DETAILS ====================

@router.get("/games/{game_id}")
async def get_game_details(
    game_id: str,
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("nba", description="League")
):
    """
    Get detailed information about a specific game including box score
    
    Args:
        game_id: ESPN game/event ID (found in scoreboard response)
    """
    try:
        provider = get_provider(sport, league)
        game = provider.get_game_details(game_id)
        
        if not game:
            raise HTTPException(status_code=404, detail=f"Game '{game_id}' not found")
        
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching game %s: %s", game_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== RANKINGS (College Sports) ====================

@router.get("/rankings")
async def get_rankings(
    sport: str = Query("basketball", description="Sport"),
    league: str = Query("mens-college-basketball", description="College league")
):
    """
    Get rankings/polls (primarily for college sports)
    
    Use leagues like:
    - mens-college-basketball
    - womens-college-basketball  
    - college-football
    """
    try:
        provider = get_provider(sport, league)
        rankings = provider.get_rankings()
        
        return {
            "sport": sport,
            "league": league,
            "rankings": rankings
        }
    except Exception as e:
        logger.error("Error fetching rankings: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== SUPPORTED LEAGUES ====================

@router.get("/leagues")
async def get_supported_leagues():
    """
    Get list of all supported sports and leagues
    """
    return {
        "sports": [
            {
                "sport": "basketball",
                "leagues": [
                    {"id": "nba", "name": "NBA"},
                    {"id": "wnba", "name": "WNBA"},
                    {"id": "mens-college-basketball", "name": "Men's College Basketball"},
                    {"id": "womens-college-basketball", "name": "Women's College Basketball"}
                ]
            },
            {
                "sport": "football",
                "leagues": [
                    {"id": "nfl", "name": "NFL"},
                    {"id": "college-football", "name": "College Football"}
                ]
            },
            {
                "sport": "baseball",
                "leagues": [
                    {"id": "mlb", "name": "MLB"}
                ]
            },
            {
                "sport": "hockey",
                "leagues": [
                    {"id": "nhl", "name": "NHL"}
                ]
            },
            {
                "sport": "soccer",
                "leagues": [
                    {"id": "eng.1", "name": "English Premier League"},
                    {"id": "usa.1", "name": "MLS"},
                    {"id": "esp.1", "name": "La Liga"},
                    {"id": "ger.1", "name": "Bundesliga"},
                    {"id": "ita.1", "name": "Serie A"},
                    {"id": "fra.1", "name": "Ligue 1"}
                ]
            }
        ]
    }
