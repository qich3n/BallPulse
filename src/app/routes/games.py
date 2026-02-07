"""
Games Routes

Provides endpoints for:
- Today's games with predictions
- Head-to-head history between teams
- Betting odds comparison
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from datetime import datetime
from ..providers.espn_provider import ESPNProvider, Sport, League
from ..providers.basketball_provider import BasketballProvider
from ..services.scoring_service import ScoringService
from ..services.rate_limiter import limiter, RATE_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/games", tags=["games"])

# Initialize providers and services
espn_provider = ESPNProvider(sport=Sport.BASKETBALL, league=League.NBA)
basketball_provider = BasketballProvider()
scoring_service = ScoringService()

# Simple in-memory cache for team scores (refreshed every 30 minutes)
_team_score_cache: Dict[str, tuple] = {}  # {team_name: (score, timestamp)}
_CACHE_TTL = 1800  # 30 minutes


# ==================== Models ====================

class TeamPrediction(BaseModel):
    """Team info with prediction data"""
    name: str
    abbreviation: str
    score: Optional[str] = None
    logo: Optional[str] = None
    predicted_score: float = Field(description="Our prediction score 0-1")
    stats_available: bool = True


class OddsComparison(BaseModel):
    """Betting odds vs prediction comparison"""
    spread: Optional[float] = None
    spread_favorite: Optional[str] = None
    over_under: Optional[float] = None
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None
    vegas_favorite: Optional[str] = None
    our_favorite: str
    agreement: bool = Field(description="Whether our prediction agrees with Vegas")
    edge: Optional[str] = Field(None, description="Potential betting edge if disagreement")


class GamePrediction(BaseModel):
    """Game with prediction and odds"""
    game_id: str
    date: str
    status: str
    status_detail: str
    venue: Optional[str] = None
    broadcast: Optional[str] = None
    home_team: TeamPrediction
    away_team: TeamPrediction
    predicted_winner: str
    win_probability: float
    confidence: str
    odds: Optional[OddsComparison] = None


class TodaysGamesResponse(BaseModel):
    """Response for today's games"""
    date: str
    games: List[GamePrediction]
    total_games: int
    predictions_generated: int


class HeadToHeadGame(BaseModel):
    """Historical game between two teams"""
    game_id: str
    date: str
    season: Optional[str] = None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    winner: str
    venue: Optional[str] = None


class HeadToHeadResponse(BaseModel):
    """Head-to-head history response"""
    team1: str
    team2: str
    total_games: int
    team1_wins: int
    team2_wins: int
    games: List[HeadToHeadGame]
    last_meeting: Optional[HeadToHeadGame] = None
    home_advantage: Optional[Dict[str, Any]] = None


# ==================== Helper Functions ====================

def _calculate_team_score(team_name: str) -> float:
    """Calculate prediction score for a team with caching"""
    import time
    
    # Check cache first
    cache_key = team_name.lower()
    if cache_key in _team_score_cache:
        cached_score, cached_time = _team_score_cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_score
    
    try:
        stats = basketball_provider.get_team_stats_summary(team_name)
        score = scoring_service.calculate_stats_score(stats)
        # Cache the result
        _team_score_cache[cache_key] = (score, time.time())
        return score
    except Exception as e:
        logger.warning(f"Error calculating score for {team_name}: {e}")
        return 0.5


def _get_confidence_label(probability: float) -> str:
    """Get confidence label from probability"""
    diff = abs(probability - 0.5)
    if diff >= 0.25:
        return "High"
    elif diff >= 0.15:
        return "Medium"
    elif diff >= 0.08:
        return "Low"
    else:
        return "Toss-up"


def _parse_odds_comparison(
    odds_data: Optional[Dict[str, Any]], 
    home_team: str, 
    away_team: str,
    our_predicted_winner: str
) -> Optional[OddsComparison]:
    """Parse ESPN odds data and compare with our prediction"""
    if not odds_data:
        return None
    
    spread = odds_data.get("spread")
    over_under = odds_data.get("over_under")
    
    # Determine Vegas favorite from spread
    vegas_favorite = None
    if spread is not None:
        # Negative spread means home team is favored
        if spread < 0:
            vegas_favorite = home_team
        elif spread > 0:
            vegas_favorite = away_team
        else:
            vegas_favorite = "Pick'em"
    
    # Get moneylines
    home_odds = odds_data.get("home_team_odds", {})
    away_odds = odds_data.get("away_team_odds", {})
    
    moneyline_home = home_odds.get("moneyLine") if home_odds else None
    moneyline_away = away_odds.get("moneyLine") if away_odds else None
    
    # Compare with our prediction
    agreement = (vegas_favorite == our_predicted_winner) if vegas_favorite and vegas_favorite != "Pick'em" else True
    
    # Calculate potential edge
    edge = None
    if not agreement and spread is not None:
        edge = f"Our model picks {our_predicted_winner}, Vegas favors {vegas_favorite} by {abs(spread)} pts"
    
    return OddsComparison(
        spread=spread,
        spread_favorite=vegas_favorite,
        over_under=over_under,
        moneyline_home=moneyline_home,
        moneyline_away=moneyline_away,
        vegas_favorite=vegas_favorite or "Unknown",
        our_favorite=our_predicted_winner,
        agreement=agreement,
        edge=edge
    )


# ==================== Endpoints ====================

@router.get("/today", response_model=TodaysGamesResponse)
@limiter.limit(RATE_LIMITS.get("compare", "10/minute"))
async def get_todays_games(request: Request):
    """
    Get today's NBA games with predictions and odds comparison.
    
    Returns all games scheduled for today with:
    - Our win probability prediction
    - Vegas betting odds
    - Comparison between our prediction and Vegas lines
    """
    try:
        # Get today's scores from ESPN
        today_scores = espn_provider.get_today_scores()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        games = []
        predictions_generated = 0
        
        for game_data in today_scores:
            home_info = game_data.get("home_team", {})
            away_info = game_data.get("away_team", {})
            
            home_name = home_info.get("name", "Unknown")
            away_name = away_info.get("name", "Unknown")
            
            # Calculate prediction scores
            home_score = _calculate_team_score(home_name)
            away_score = _calculate_team_score(away_name)
            
            # Apply home court advantage (~3-4% boost)
            home_score_adjusted = min(1.0, home_score + 0.03)
            
            # Calculate win probability using scoring service
            total_score = home_score_adjusted + away_score
            if total_score > 0:
                home_win_prob = home_score_adjusted / total_score
            else:
                home_win_prob = 0.5
            
            # Determine predicted winner
            if home_win_prob >= 0.5:
                predicted_winner = home_name
                win_probability = home_win_prob
            else:
                predicted_winner = away_name
                win_probability = 1 - home_win_prob
            
            # Parse odds comparison
            odds_comparison = _parse_odds_comparison(
                game_data.get("odds"),
                home_name,
                away_name,
                predicted_winner
            )
            
            game_prediction = GamePrediction(
                game_id=game_data.get("id", ""),
                date=game_data.get("date", today_str),
                status=game_data.get("status", "Scheduled"),
                status_detail=game_data.get("status_detail", ""),
                venue=game_data.get("venue"),
                broadcast=game_data.get("broadcast"),
                home_team=TeamPrediction(
                    name=home_name,
                    abbreviation=home_info.get("abbreviation", ""),
                    score=home_info.get("score"),
                    logo=home_info.get("logo"),
                    predicted_score=round(home_score_adjusted, 3),
                    stats_available=home_score != 0.5
                ),
                away_team=TeamPrediction(
                    name=away_name,
                    abbreviation=away_info.get("abbreviation", ""),
                    score=away_info.get("score"),
                    logo=away_info.get("logo"),
                    predicted_score=round(away_score, 3),
                    stats_available=away_score != 0.5
                ),
                predicted_winner=predicted_winner,
                win_probability=round(win_probability, 3),
                confidence=_get_confidence_label(win_probability),
                odds=odds_comparison
            )
            
            games.append(game_prediction)
            predictions_generated += 1
        
        return TodaysGamesResponse(
            date=today_str,
            games=games,
            total_games=len(games),
            predictions_generated=predictions_generated
        )
        
    except Exception as e:
        logger.error(f"Error fetching today's games: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch today's games: {str(e)}"
        )


@router.get("/date/{date}", response_model=TodaysGamesResponse)
async def get_games_by_date(date: str):
    """
    Get games for a specific date with predictions.
    
    Args:
        date: Date in YYYYMMDD format
    """
    try:
        # Get scoreboard for specific date
        scoreboard = espn_provider.get_scoreboard(date=date)
        
        games = []
        
        for event in scoreboard.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])
            
            if len(competitors) < 2:
                continue
            
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            
            home_name = home.get("team", {}).get("displayName", "Unknown")
            away_name = away.get("team", {}).get("displayName", "Unknown")
            
            # Calculate predictions
            home_score = _calculate_team_score(home_name)
            away_score = _calculate_team_score(away_name)
            home_score_adjusted = min(1.0, home_score + 0.03)
            
            total_score = home_score_adjusted + away_score
            home_win_prob = home_score_adjusted / total_score if total_score > 0 else 0.5
            
            if home_win_prob >= 0.5:
                predicted_winner = home_name
                win_probability = home_win_prob
            else:
                predicted_winner = away_name
                win_probability = 1 - home_win_prob
            
            # Get odds
            odds_data = None
            odds_list = competition.get("odds", [])
            if odds_list:
                raw_odds = odds_list[0]
                odds_data = {
                    "spread": raw_odds.get("spread"),
                    "over_under": raw_odds.get("overUnder"),
                    "home_team_odds": raw_odds.get("homeTeamOdds", {}),
                    "away_team_odds": raw_odds.get("awayTeamOdds", {})
                }
            
            odds_comparison = _parse_odds_comparison(odds_data, home_name, away_name, predicted_winner)
            
            game_prediction = GamePrediction(
                game_id=event.get("id", ""),
                date=event.get("date", date),
                status=event.get("status", {}).get("type", {}).get("description", "Unknown"),
                status_detail=event.get("status", {}).get("type", {}).get("detail", ""),
                venue=competition.get("venue", {}).get("fullName"),
                broadcast=espn_provider._get_broadcast(competition),
                home_team=TeamPrediction(
                    name=home_name,
                    abbreviation=home.get("team", {}).get("abbreviation", ""),
                    score=home.get("score"),
                    logo=home.get("team", {}).get("logo"),
                    predicted_score=round(home_score_adjusted, 3),
                    stats_available=True
                ),
                away_team=TeamPrediction(
                    name=away_name,
                    abbreviation=away.get("team", {}).get("abbreviation", ""),
                    score=away.get("score"),
                    logo=away.get("team", {}).get("logo"),
                    predicted_score=round(away_score, 3),
                    stats_available=True
                ),
                predicted_winner=predicted_winner,
                win_probability=round(win_probability, 3),
                confidence=_get_confidence_label(win_probability),
                odds=odds_comparison
            )
            
            games.append(game_prediction)
        
        # Format date for response
        try:
            formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
        except:
            formatted_date = date
        
        return TodaysGamesResponse(
            date=formatted_date,
            games=games,
            total_games=len(games),
            predictions_generated=len(games)
        )
        
    except Exception as e:
        logger.error(f"Error fetching games for date {date}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch games: {str(e)}"
        )


@router.get("/head-to-head", response_model=HeadToHeadResponse)
async def get_head_to_head(
    team1: str = Query(..., description="First team name"),
    team2: str = Query(..., description="Second team name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum games to return")
):
    """
    Get head-to-head history between two teams.
    
    Returns historical matchups, win counts, and last meeting details.
    """
    try:
        # Normalize team names
        team1_lower = team1.lower()
        team2_lower = team2.lower()
        
        # Get team info from ESPN to get proper names and IDs
        team1_info = espn_provider.get_team(team1)
        team2_info = espn_provider.get_team(team2)
        
        team1_name = team1_info.get("name", team1) if team1_info else team1
        team2_name = team2_info.get("name", team2) if team2_info else team2
        team1_abbrev = team1_info.get("abbreviation", "").lower() if team1_info else ""
        team2_abbrev = team2_info.get("abbreviation", "").lower() if team2_info else ""
        
        # Unfortunately ESPN doesn't have a direct head-to-head API
        # We'll check multiple recent dates for games between these teams
        # This is a workaround - in production you'd use a proper sports database
        
        games = []
        team1_wins = 0
        team2_wins = 0
        
        # Check recent dates (last 60 days) for matchups
        from datetime import timedelta
        current_date = datetime.now()
        
        for days_back in range(60):
            check_date = current_date - timedelta(days=days_back)
            date_str = check_date.strftime("%Y%m%d")
            
            try:
                scoreboard = espn_provider.get_scoreboard(date=date_str)
                
                for event in scoreboard.get("events", []):
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])
                    
                    if len(competitors) < 2:
                        continue
                    
                    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                    
                    home_name = home.get("team", {}).get("displayName", "").lower()
                    away_name = away.get("team", {}).get("displayName", "").lower()
                    home_abbrev = home.get("team", {}).get("abbreviation", "").lower()
                    away_abbrev = away.get("team", {}).get("abbreviation", "").lower()
                    
                    # Check if this game involves both teams
                    team1_in_game = (
                        team1_lower in home_name or team1_lower in away_name or
                        team1_abbrev == home_abbrev or team1_abbrev == away_abbrev
                    )
                    team2_in_game = (
                        team2_lower in home_name or team2_lower in away_name or
                        team2_abbrev == home_abbrev or team2_abbrev == away_abbrev
                    )
                    
                    if team1_in_game and team2_in_game:
                        # This is a matchup between the two teams
                        status = event.get("status", {}).get("type", {}).get("name", "")
                        
                        # Only count completed games
                        if status == "STATUS_FINAL":
                            home_score = int(home.get("score", 0))
                            away_score = int(away.get("score", 0))
                            
                            home_display = home.get("team", {}).get("displayName", "Unknown")
                            away_display = away.get("team", {}).get("displayName", "Unknown")
                            
                            winner = home_display if home_score > away_score else away_display
                            
                            # Count wins
                            if team1_lower in winner.lower() or team1_abbrev in winner.lower():
                                team1_wins += 1
                            else:
                                team2_wins += 1
                            
                            games.append(HeadToHeadGame(
                                game_id=event.get("id", ""),
                                date=event.get("date", ""),
                                season=event.get("season", {}).get("year"),
                                home_team=home_display,
                                away_team=away_display,
                                home_score=home_score,
                                away_score=away_score,
                                winner=winner,
                                venue=competition.get("venue", {}).get("fullName")
                            ))
                            
                            if len(games) >= limit:
                                break
                
                if len(games) >= limit:
                    break
                    
            except Exception as e:
                logger.debug(f"Error checking date {date_str}: {e}")
                continue
        
        # Sort games by date (most recent first)
        games.sort(key=lambda x: x.date, reverse=True)
        
        # Get last meeting
        last_meeting = games[0] if games else None
        
        # Calculate home advantage stats
        home_advantage = None
        if games:
            team1_home_wins = sum(1 for g in games if team1_lower in g.home_team.lower() and team1_lower in g.winner.lower())
            team2_home_wins = sum(1 for g in games if team2_lower in g.home_team.lower() and team2_lower in g.winner.lower())
            home_advantage = {
                "team1_home_record": f"{team1_home_wins} wins at home",
                "team2_home_record": f"{team2_home_wins} wins at home"
            }
        
        return HeadToHeadResponse(
            team1=team1_name,
            team2=team2_name,
            total_games=len(games),
            team1_wins=team1_wins,
            team2_wins=team2_wins,
            games=games[:limit],
            last_meeting=last_meeting,
            home_advantage=home_advantage
        )
        
    except Exception as e:
        logger.error(f"Error fetching head-to-head: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch head-to-head history: {str(e)}"
        )


@router.get("/{game_id}")
async def get_game_detail(game_id: str):
    """
    Get detailed information about a specific game including prediction.
    """
    try:
        # Get game summary from ESPN
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        # Parse game details
        boxscore = data.get("boxscore", {})
        teams = boxscore.get("teams", [])
        
        game_info = data.get("header", {}).get("competitions", [{}])[0]
        
        result = {
            "game_id": game_id,
            "status": game_info.get("status", {}).get("type", {}).get("description"),
            "venue": game_info.get("venue", {}).get("fullName"),
            "teams": [],
            "leaders": data.get("leaders", []),
            "predictor": data.get("predictor", {}),
            "odds": data.get("odds", [])
        }
        
        for team_data in teams:
            team_info = team_data.get("team", {})
            team_name = team_info.get("displayName", "Unknown")
            
            # Add our prediction
            prediction_score = _calculate_team_score(team_name)
            
            result["teams"].append({
                "name": team_name,
                "abbreviation": team_info.get("abbreviation"),
                "logo": team_info.get("logo"),
                "score": team_data.get("score"),
                "our_prediction_score": round(prediction_score, 3),
                "statistics": team_data.get("statistics", [])
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching game detail {game_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch game details: {str(e)}"
        )
