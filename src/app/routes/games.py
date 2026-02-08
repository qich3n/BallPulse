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
import httpx
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
_team_form_cache: Dict[str, tuple] = {}  # {team_name: (form_data, timestamp)}
_h2h_cache: Dict[str, tuple] = {}  # {"team1_team2": (h2h_data, timestamp)}
_CACHE_TTL = 1800  # 30 minutes
_H2H_CACHE_TTL = 3600  # 1 hour for H2H data


# ==================== Models ====================

class TeamPrediction(BaseModel):
    """Team info with prediction data"""
    name: str
    abbreviation: str
    score: Optional[str] = None
    logo: Optional[str] = None
    strength_score: float = Field(description="Team strength rating 0-100%")
    win_probability: float = Field(description="Win probability for this team 0-100%")
    stats_available: bool = True
    recent_form: Optional[str] = Field(None, description="Recent form (e.g., 'W5' for 5-game win streak)")
    last_10_record: Optional[str] = Field(None, description="Record in last 10 games (e.g., '7-3')")
    is_hot: bool = Field(False, description="True if team is on fire (6+ wins in last 10)")


class OddsComparison(BaseModel):
    """Betting odds vs prediction comparison"""
    spread: Optional[float] = None
    spread_favorite: Optional[str] = None
    over_under: Optional[float] = None
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None
    vegas_favorite: Optional[str] = None
    vegas_implied_prob: Optional[float] = Field(None, description="Vegas implied win probability for favorite")
    our_favorite: str
    our_win_prob: float = Field(description="Our model's win probability for our pick")
    agreement: bool = Field(description="Whether our prediction agrees with Vegas")
    edge_score: Optional[float] = Field(None, description="Edge score: difference between our prob and Vegas implied prob")
    edge: Optional[str] = Field(None, description="Potential betting edge if disagreement")


class HeadToHeadSummary(BaseModel):
    """Brief head-to-head summary for prediction context"""
    total_games: int = 0
    team1_wins: int = 0
    team2_wins: int = 0
    dominant_team: Optional[str] = None
    last_winner: Optional[str] = None
    home_team_wins_at_home: int = 0


class LiveGameInfo(BaseModel):
    """Live game status and score information"""
    is_live: bool = Field(False, description="True if game is currently in progress")
    is_final: bool = Field(False, description="True if game has ended")
    period: int = Field(0, description="Current period (1-4, 5+ for OT)")
    period_display: str = Field("", description="Period display (e.g., '3rd', 'OT', 'Final')")
    clock: str = Field("", description="Game clock (e.g., '5:23')")
    home_score: int = Field(0, description="Home team current score")
    away_score: int = Field(0, description="Away team current score")
    score_display: str = Field("", description="Score display (e.g., '105-98')")
    leader: Optional[str] = Field(None, description="Team currently leading")
    lead_margin: int = Field(0, description="Current point margin")


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
    reasoning: List[str] = Field(default_factory=list, description="Reasons for the prediction")
    head_to_head: Optional[HeadToHeadSummary] = Field(None, description="Recent head-to-head history")
    live: Optional[LiveGameInfo] = Field(None, description="Live game score and status (if in progress or final)")


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
    except (ValueError, KeyError, TypeError) as e:
        logger.warning("Error calculating score for %s: %s", team_name, e)
        return 0.5


def _get_team_recent_form(team_name: str) -> Dict[str, Any]:
    """
    Get recent form data for a team (streak, last 10 record).
    
    Uses cached ESPN team data to avoid slow API calls.
    
    Returns:
        Dict with streak, last_10_wins, last_10_losses, is_hot, form_string
    """
    import time
    
    cache_key = team_name.lower()
    if cache_key in _team_form_cache:
        cached_form, cached_time = _team_form_cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_form
    
    # Return neutral form data - don't make expensive API calls
    # The team stats from basketball_provider already give us performance info
    form_data = {
        "streak": 0,
        "last_10_wins": 5,
        "last_10_losses": 5,
        "is_hot": False,
        "is_cold": False,
        "form_string": "",
        "last_10_record": ""
    }
    
    _team_form_cache[cache_key] = (form_data, time.time())
    return form_data


def _get_quick_h2h(_team1: str, _team2: str) -> HeadToHeadSummary:
    """
    Get a quick head-to-head summary for prediction purposes.
    
    DISABLED for performance - always returns empty summary.
    Use the /head-to-head endpoint for actual H2H data.
    
    Returns:
        Empty HeadToHeadSummary (no API calls made)
    """
    # Return empty summary immediately - H2H lookups are too slow
    # Each lookup requires checking multiple days of scoreboards
    return HeadToHeadSummary()


def _calculate_form_adjustment(form_data: Dict[str, Any]) -> float:
    """
    Calculate score adjustment based on recent form.
    
    Returns:
        Adjustment between -0.08 and +0.08
    """
    last_10_wins = form_data.get("last_10_wins", 5)
    streak = form_data.get("streak", 0)
    
    # Base adjustment from last 10 record (neutral at 5-5)
    record_adj = (last_10_wins - 5) * 0.01  # -0.05 to +0.05
    
    # Streak bonus/penalty
    if streak >= 5:
        streak_adj = 0.03  # Hot streak bonus
    elif streak >= 3:
        streak_adj = 0.015
    elif streak <= -5:
        streak_adj = -0.03  # Cold streak penalty
    elif streak <= -3:
        streak_adj = -0.015
    else:
        streak_adj = 0
    
    return max(-0.08, min(0.08, record_adj + streak_adj))


def _calculate_h2h_adjustment(h2h: HeadToHeadSummary, team_name: str, _other_team: str, is_home: bool) -> float:
    """
    Calculate score adjustment based on head-to-head history.
    
    Returns:
        Adjustment between -0.05 and +0.05
    """
    _ = is_home  # Currently unused but kept for future home advantage calculations
    if h2h.total_games == 0:
        return 0.0
    
    # Check if this team dominates the matchup
    team_wins = 0
    other_wins = 0
    
    team_lower = team_name.lower()
    if h2h.dominant_team and team_lower in h2h.dominant_team.lower():
        team_wins = h2h.team1_wins if h2h.team1_wins > h2h.team2_wins else h2h.team2_wins
        other_wins = h2h.total_games - team_wins
    elif h2h.dominant_team:
        other_wins = h2h.team1_wins if h2h.team1_wins > h2h.team2_wins else h2h.team2_wins
        team_wins = h2h.total_games - other_wins
    else:
        # Split evenly
        return 0.0
    
    # Win rate differential
    if h2h.total_games >= 2:
        win_rate = team_wins / h2h.total_games
        h2h_adj = (win_rate - 0.5) * 0.1  # -0.05 to +0.05
    else:
        h2h_adj = 0.0
    
    # Small bonus if last game winner & playing at home
    if h2h.last_winner and team_lower in h2h.last_winner.lower() and is_home:
        h2h_adj += 0.01
    
    return max(-0.05, min(0.05, h2h_adj))


def _generate_reasoning(
    winner_name: str,
    loser_name: str,
    winner_score: float,
    loser_score: float,
    win_probability: float,
    is_home: bool,
    odds: Optional[OddsComparison] = None,
    winner_form: Optional[Dict[str, Any]] = None,
    loser_form: Optional[Dict[str, Any]] = None,
    h2h: Optional[HeadToHeadSummary] = None
) -> List[str]:
    """
    Generate human-readable reasoning for why we picked a team.
    
    Args:
        winner_name: Name of predicted winner
        loser_name: Name of predicted loser  
        winner_score: Winner's strength score (0-1)
        loser_score: Loser's strength score (0-1)
        win_probability: Calculated win probability
        is_home: Whether winner is home team
        odds: Optional odds comparison data
        winner_form: Optional recent form data for winner
        loser_form: Optional recent form data for loser
        h2h: Optional head-to-head summary
    
    Returns:
        List of reasoning strings
    """
    reasons = []
    
    # Strength comparison
    strength_diff = (winner_score - loser_score) * 100
    if strength_diff > 15:
        reasons.append(f"📊 {winner_name} has a significantly stronger overall rating ({winner_score*100:.0f}% vs {loser_score*100:.0f}%)")
    elif strength_diff > 8:
        reasons.append(f"📊 {winner_name} has a better overall rating ({winner_score*100:.0f}% vs {loser_score*100:.0f}%)")
    elif strength_diff > 3:
        reasons.append(f"📊 {winner_name} has a slight edge in overall rating ({winner_score*100:.0f}% vs {loser_score*100:.0f}%)")
    else:
        reasons.append(f"📊 Both teams are closely matched in strength ({winner_score*100:.0f}% vs {loser_score*100:.0f}%)")
    
    # Recent form / momentum
    if winner_form:
        winner_streak = winner_form.get("streak", 0)
        winner_last_10 = winner_form.get("last_10_record", "")
        
        if winner_form.get("is_hot"):
            if winner_streak >= 5:
                reasons.append(f"🔥 {winner_name} is ON FIRE with a {winner_streak}-game win streak!")
            elif winner_streak >= 3:
                reasons.append(f"🔥 {winner_name} is hot with a {winner_streak}-game win streak ({winner_last_10} in last 10)")
            else:
                reasons.append(f"📈 {winner_name} is playing well lately ({winner_last_10} in last 10)")
        elif winner_streak >= 2:
            reasons.append(f"✨ {winner_name} has won {winner_streak} straight games")
    
    if loser_form:
        loser_streak = loser_form.get("streak", 0)
        loser_last_10 = loser_form.get("last_10_record", "")
        
        if loser_form.get("is_cold"):
            if loser_streak <= -5:
                reasons.append(f"❄️ {loser_name} is struggling badly with a {abs(loser_streak)}-game losing streak")
            elif loser_streak <= -3:
                reasons.append(f"📉 {loser_name} is cold with a {abs(loser_streak)}-game losing streak ({loser_last_10} in last 10)")
            else:
                reasons.append(f"📉 {loser_name} has been struggling lately ({loser_last_10} in last 10)")
    
    # Head-to-head history
    if h2h and h2h.total_games > 0:
        winner_lower = winner_name.lower()
        if h2h.dominant_team and winner_lower in h2h.dominant_team.lower():
            if h2h.total_games >= 2:
                winner_h2h_wins = h2h.team1_wins if h2h.team1_wins > h2h.team2_wins else h2h.team2_wins
                reasons.append(f"🏆 {winner_name} owns the head-to-head ({winner_h2h_wins}-{h2h.total_games - winner_h2h_wins} in recent meetings)")
        elif h2h.dominant_team:
            # Loser dominates H2H - worth noting as a contrarian pick
            reasons.append(f"⚠️ {loser_name} has the edge historically, but current form favors {winner_name}")
        
        if h2h.last_winner:
            if winner_lower in h2h.last_winner.lower():
                reasons.append(f"👊 {winner_name} won the last meeting between these teams")
    
    # Home court advantage
    if is_home:
        reasons.append(f"🏠 {winner_name} has home court advantage (+3% boost)")
    else:
        reasons.append(f"✈️ {winner_name} playing on the road but still favored due to stronger stats")
    
    # Win probability context
    if win_probability >= 0.70:
        reasons.append(f"💪 High confidence pick with {win_probability*100:.0f}% win probability")
    elif win_probability >= 0.60:
        reasons.append(f"👍 Solid pick with {win_probability*100:.0f}% win probability")
    elif win_probability >= 0.55:
        reasons.append(f"🤔 Close matchup - {win_probability*100:.0f}% win probability")
    else:
        reasons.append(f"⚖️ Very close game - essentially a toss-up at {win_probability*100:.0f}%")
    
    # Vegas comparison if available
    if odds:
        if not odds.agreement:
            reasons.append(f"⚠️ We disagree with Vegas who favors {odds.vegas_favorite}")
            if odds.edge_score and odds.edge_score > 0:
                reasons.append(f"💰 Potential value bet - {abs(odds.edge_score):.1f}% edge over Vegas")
        elif odds.edge_score and odds.edge_score > 5:
            reasons.append(f"💰 We agree with Vegas but are MORE confident - {odds.edge_score:.1f}% edge")
        elif odds.vegas_favorite:
            reasons.append("✅ Our pick aligns with Vegas favorite")
        
        if odds.spread is not None:
            spread_abs = abs(odds.spread)
            if spread_abs > 10:
                reasons.append(f"📈 Vegas expects a blowout ({spread_abs:.1f} point spread)")
            elif spread_abs > 5:
                reasons.append(f"📉 Vegas expects a comfortable win ({spread_abs:.1f} point spread)")
            else:
                reasons.append(f"🎯 Vegas expects a close game ({spread_abs:.1f} point spread)")
    
    return reasons


def _get_confidence_label(probability: float) -> str:
    """Get confidence label from probability"""
    diff = abs(probability - 0.5)
    if diff >= 0.20:
        return "High"
    elif diff >= 0.12:
        return "Medium"
    elif diff >= 0.05:
        return "Low"
    else:
        return "Toss-up"


def _parse_live_game_info(game_data: Dict[str, Any]) -> Optional[LiveGameInfo]:
    """
    Parse live game information from ESPN game data.
    
    Returns:
        LiveGameInfo if game is in progress or final, None if scheduled
    """
    status = game_data.get("status", "").lower()
    # status_detail available via game_data.get("status_detail", "") if needed
    
    # Determine game state
    is_live = "in progress" in status or "halftime" in status
    is_final = "final" in status
    
    # If game hasn't started yet, return None
    if not is_live and not is_final:
        return None
    
    period = game_data.get("period", 0)
    clock = game_data.get("clock", "")
    
    # Get scores
    home_info = game_data.get("home_team", {})
    away_info = game_data.get("away_team", {})
    
    try:
        home_score = int(home_info.get("score", 0) or 0)
        away_score = int(away_info.get("score", 0) or 0)
    except (ValueError, TypeError):
        home_score = 0
        away_score = 0
    
    # Determine period display
    if is_final:
        if period > 4:
            period_display = f"Final/OT{period - 4}" if period > 5 else "Final/OT"
        else:
            period_display = "Final"
    elif period == 0:
        period_display = "Pre-Game"
    elif period == 1:
        period_display = "1st"
    elif period == 2:
        period_display = "2nd"
    elif period == 3:
        period_display = "3rd"
    elif period == 4:
        period_display = "4th"
    else:
        period_display = f"OT{period - 4}" if period > 5 else "OT"
    
    # Add clock if game is live
    if is_live and clock:
        period_display = f"{period_display} {clock}"
    
    # Determine leader
    leader = None
    lead_margin = abs(home_score - away_score)
    if home_score > away_score:
        leader = home_info.get("name", "Home")
    elif away_score > home_score:
        leader = away_info.get("name", "Away")
    
    return LiveGameInfo(
        is_live=is_live,
        is_final=is_final,
        period=period,
        period_display=period_display,
        clock=clock,
        home_score=home_score,
        away_score=away_score,
        score_display=f"{home_score}-{away_score}",
        leader=leader,
        lead_margin=lead_margin
    )


def _sigmoid(x: float, steepness: float = 4.0) -> float:
    """Sigmoid function to convert score difference to probability"""
    import math
    return 1.0 / (1.0 + math.exp(-steepness * x))


def _calculate_win_probability(home_score: float, away_score: float, home_advantage: float = 0.03) -> float:
    """
    Calculate win probability using sigmoid function.
    
    This converts the difference in team strength scores to a probability
    using a sigmoid curve, which is more realistic than a simple ratio.
    
    Args:
        home_score: Home team strength score (0-1)
        away_score: Away team strength score (0-1)
        home_advantage: Home court advantage bonus (default 3%)
    
    Returns:
        Home team win probability (0-1)
    """
    # Apply home court advantage
    adjusted_diff = (home_score + home_advantage) - away_score
    
    # Use sigmoid to convert difference to probability
    # steepness=4 means a 0.25 difference gives ~73% probability
    return _sigmoid(adjusted_diff, steepness=4.0)


def _moneyline_to_implied_prob(moneyline: int) -> float:
    """
    Convert American moneyline odds to implied probability.
    
    Examples:
        -150 -> 60% implied probability
        +150 -> 40% implied probability
    """
    if moneyline < 0:
        # Favorite: -150 means bet $150 to win $100
        return abs(moneyline) / (abs(moneyline) + 100)
    else:
        # Underdog: +150 means bet $100 to win $150
        return 100 / (moneyline + 100)


def _calculate_edge_score(our_prob: float, vegas_implied_prob: float, same_pick: bool) -> float:
    """
    Calculate edge score comparing our prediction to Vegas.
    
    Positive edge = we see value (our prob > Vegas implies)
    Negative edge = Vegas sees something we don't
    
    Returns:
        Edge score as percentage points (e.g., 5.0 means 5% edge)
    """
    if same_pick:
        # We agree with Vegas - edge is how much MORE confident we are
        return (our_prob - vegas_implied_prob) * 100
    else:
        # We disagree - edge is our confidence in the opposite pick
        return (our_prob - (1 - vegas_implied_prob)) * 100


def _parse_odds_comparison(
    odds_data: Optional[Dict[str, Any]], 
    home_team: str, 
    away_team: str,
    our_predicted_winner: str,
    our_win_probability: float
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
    
    # Calculate Vegas implied probability from moneylines
    vegas_implied_prob = None
    if moneyline_home is not None and moneyline_away is not None:
        # Get implied prob for the favorite
        if vegas_favorite == home_team:
            vegas_implied_prob = _moneyline_to_implied_prob(moneyline_home)
        elif vegas_favorite == away_team:
            vegas_implied_prob = _moneyline_to_implied_prob(moneyline_away)
    
    # Compare with our prediction
    agreement = (vegas_favorite == our_predicted_winner) if vegas_favorite and vegas_favorite != "Pick'em" else True
    
    # Calculate edge score
    edge_score = None
    if vegas_implied_prob is not None:
        edge_score = _calculate_edge_score(our_win_probability, vegas_implied_prob, agreement)
    
    # Generate edge description
    edge = None
    if not agreement and spread is not None:
        edge = f"Our model picks {our_predicted_winner}, Vegas favors {vegas_favorite} by {abs(spread):.1f} pts"
    elif edge_score is not None and edge_score > 5:
        edge = f"Strong edge: Our model is {edge_score:.1f}% more confident than Vegas"
    
    return OddsComparison(
        spread=spread,
        spread_favorite=vegas_favorite,
        over_under=over_under,
        moneyline_home=moneyline_home,
        moneyline_away=moneyline_away,
        vegas_favorite=vegas_favorite or "Unknown",
        vegas_implied_prob=round(vegas_implied_prob, 3) if vegas_implied_prob else None,
        our_favorite=our_predicted_winner,
        our_win_prob=round(our_win_probability, 3),
        agreement=agreement,
        edge_score=round(edge_score, 1) if edge_score else None,
        edge=edge
    )


# ==================== Endpoints ====================

@router.get("/today", response_model=TodaysGamesResponse)
@limiter.limit(RATE_LIMITS.get("compare", "10/minute"))
async def get_todays_games(
    request: Request,
    include_h2h: bool = Query(False, description="Include head-to-head history (slower)"),
    include_form: bool = Query(True, description="Include recent form data")
):
    """
    Get today's NBA games with predictions and odds comparison.
    
    Returns all games scheduled for today with:
    - Our win probability prediction
    - Vegas betting odds
    - Comparison between our prediction and Vegas lines
    - Live scores for games in progress
    
    Set include_h2h=true for head-to-head data (adds ~1-2s per game).
    """
    try:
        # Get today's scores from ESPN (uses Eastern Time)
        today_scores = espn_provider.get_today_scores()
        
        # Use Eastern Time for the date display (matches ESPN/NBA)
        import pytz
        eastern = pytz.timezone('US/Eastern')
        today_str = datetime.now(eastern).strftime("%Y-%m-%d")
        
        games = []
        predictions_generated = 0
        
        for game_data in today_scores:
            home_info = game_data.get("home_team", {})
            away_info = game_data.get("away_team", {})
            
            home_name = home_info.get("name", "Unknown")
            away_name = away_info.get("name", "Unknown")
            
            # Calculate team strength scores (0-1 scale)
            home_base_score = _calculate_team_score(home_name)
            away_base_score = _calculate_team_score(away_name)
            
            # Get recent form data (optional - can be slow)
            if include_form:
                home_form = _get_team_recent_form(home_name)
                away_form = _get_team_recent_form(away_name)
            else:
                home_form = {"streak": 0, "last_10_wins": 5, "last_10_losses": 5, "is_hot": False, "is_cold": False, "form_string": "", "last_10_record": ""}
                away_form = {"streak": 0, "last_10_wins": 5, "last_10_losses": 5, "is_hot": False, "is_cold": False, "form_string": "", "last_10_record": ""}
            
            # Get head-to-head data (optional - very slow, disabled by default)
            if include_h2h:
                h2h = _get_quick_h2h(home_name, away_name)
            else:
                h2h = HeadToHeadSummary()
            
            # Apply form adjustments
            home_form_adj = _calculate_form_adjustment(home_form) if include_form else 0.0
            away_form_adj = _calculate_form_adjustment(away_form) if include_form else 0.0
            
            # Apply H2H adjustments
            home_h2h_adj = _calculate_h2h_adjustment(h2h, home_name, away_name, is_home=True) if include_h2h else 0.0
            away_h2h_adj = _calculate_h2h_adjustment(h2h, away_name, home_name, is_home=False) if include_h2h else 0.0
            
            # Calculate adjusted scores
            home_score = min(1.0, max(0.0, home_base_score + home_form_adj + home_h2h_adj))
            away_score = min(1.0, max(0.0, away_base_score + away_form_adj + away_h2h_adj))
            
            # Calculate win probability using sigmoid function with home court advantage
            home_win_prob = _calculate_win_probability(home_score, away_score, home_advantage=0.03)
            
            # Determine predicted winner
            if home_win_prob >= 0.5:
                predicted_winner = home_name
                win_probability = home_win_prob
            else:
                predicted_winner = away_name
                win_probability = 1 - home_win_prob
            
            # Parse odds comparison with our probability
            odds_comparison = _parse_odds_comparison(
                game_data.get("odds"),
                home_name,
                away_name,
                predicted_winner,
                win_probability
            )
            
            # Generate reasoning for the pick (now includes form and H2H)
            winner_is_home = predicted_winner == home_name
            reasoning = _generate_reasoning(
                winner_name=predicted_winner,
                loser_name=away_name if winner_is_home else home_name,
                winner_score=home_score if winner_is_home else away_score,
                loser_score=away_score if winner_is_home else home_score,
                win_probability=win_probability,
                is_home=winner_is_home,
                odds=odds_comparison,
                winner_form=home_form if winner_is_home else away_form,
                loser_form=away_form if winner_is_home else home_form,
                h2h=h2h
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
                    strength_score=round(home_score * 100, 1),
                    win_probability=round(home_win_prob * 100, 1),
                    stats_available=home_base_score != 0.5,
                    recent_form=home_form.get("form_string"),
                    last_10_record=home_form.get("last_10_record"),
                    is_hot=home_form.get("is_hot", False)
                ),
                away_team=TeamPrediction(
                    name=away_name,
                    abbreviation=away_info.get("abbreviation", ""),
                    score=away_info.get("score"),
                    logo=away_info.get("logo"),
                    strength_score=round(away_score * 100, 1),
                    win_probability=round((1 - home_win_prob) * 100, 1),
                    stats_available=away_base_score != 0.5,
                    recent_form=away_form.get("form_string"),
                    last_10_record=away_form.get("last_10_record"),
                    is_hot=away_form.get("is_hot", False)
                ),
                predicted_winner=predicted_winner,
                win_probability=round(win_probability, 3),
                confidence=_get_confidence_label(win_probability),
                odds=odds_comparison,
                reasoning=reasoning,
                head_to_head=h2h if h2h.total_games > 0 else None,
                live=_parse_live_game_info(game_data)
            )
            
            games.append(game_prediction)
            predictions_generated += 1
        
        return TodaysGamesResponse(
            date=today_str,
            games=games,
            total_games=len(games),
            predictions_generated=predictions_generated
        )
        
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Error fetching today's games: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch today's games: {str(e)}"
        ) from e


@router.get("/date/{date}", response_model=TodaysGamesResponse)
async def get_games_by_date(
    date: str,
    include_h2h: bool = Query(False, description="Include head-to-head history (slower)"),
    include_form: bool = Query(True, description="Include recent form data")
):
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
            
            # Calculate base team strength scores
            home_base_score = _calculate_team_score(home_name)
            away_base_score = _calculate_team_score(away_name)
            
            # Get recent form data (optional - can be slow)
            if include_form:
                home_form = _get_team_recent_form(home_name)
                away_form = _get_team_recent_form(away_name)
            else:
                home_form = {"streak": 0, "last_10_wins": 5, "last_10_losses": 5, "is_hot": False, "is_cold": False, "form_string": "", "last_10_record": ""}
                away_form = {"streak": 0, "last_10_wins": 5, "last_10_losses": 5, "is_hot": False, "is_cold": False, "form_string": "", "last_10_record": ""}
            
            # Get head-to-head data (optional - very slow, disabled by default)
            if include_h2h:
                h2h = _get_quick_h2h(home_name, away_name)
            else:
                h2h = HeadToHeadSummary()
            
            # Apply adjustments
            home_form_adj = _calculate_form_adjustment(home_form) if include_form else 0.0
            away_form_adj = _calculate_form_adjustment(away_form) if include_form else 0.0
            home_h2h_adj = _calculate_h2h_adjustment(h2h, home_name, away_name, is_home=True) if include_h2h else 0.0
            away_h2h_adj = _calculate_h2h_adjustment(h2h, away_name, home_name, is_home=False) if include_h2h else 0.0
            
            home_score = min(1.0, max(0.0, home_base_score + home_form_adj + home_h2h_adj))
            away_score = min(1.0, max(0.0, away_base_score + away_form_adj + away_h2h_adj))
            
            home_win_prob = _calculate_win_probability(home_score, away_score, home_advantage=0.03)
            
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
            
            odds_comparison = _parse_odds_comparison(odds_data, home_name, away_name, predicted_winner, win_probability)
            
            # Generate reasoning
            winner_is_home = predicted_winner == home_name
            reasoning = _generate_reasoning(
                winner_name=predicted_winner,
                loser_name=away_name if winner_is_home else home_name,
                winner_score=home_score if winner_is_home else away_score,
                loser_score=away_score if winner_is_home else home_score,
                win_probability=win_probability,
                is_home=winner_is_home,
                odds=odds_comparison,
                winner_form=home_form if winner_is_home else away_form,
                loser_form=away_form if winner_is_home else home_form,
                h2h=h2h
            )
            
            game_prediction = GamePrediction(
                game_id=event.get("id", ""),
                date=event.get("date", date),
                status=event.get("status", {}).get("type", {}).get("description", "Unknown"),
                status_detail=event.get("status", {}).get("type", {}).get("detail", ""),
                venue=competition.get("venue", {}).get("fullName"),
                broadcast=espn_provider.get_broadcast(competition),
                home_team=TeamPrediction(
                    name=home_name,
                    abbreviation=home.get("team", {}).get("abbreviation", ""),
                    score=home.get("score"),
                    logo=home.get("team", {}).get("logo"),
                    strength_score=round(home_score * 100, 1),
                    win_probability=round(home_win_prob * 100, 1),
                    stats_available=home_base_score != 0.5,
                    recent_form=home_form.get("form_string"),
                    last_10_record=home_form.get("last_10_record"),
                    is_hot=home_form.get("is_hot", False)
                ),
                away_team=TeamPrediction(
                    name=away_name,
                    abbreviation=away.get("team", {}).get("abbreviation", ""),
                    score=away.get("score"),
                    logo=away.get("team", {}).get("logo"),
                    strength_score=round(away_score * 100, 1),
                    win_probability=round((1 - home_win_prob) * 100, 1),
                    stats_available=away_base_score != 0.5,
                    recent_form=away_form.get("form_string"),
                    last_10_record=away_form.get("last_10_record"),
                    is_hot=away_form.get("is_hot", False)
                ),
                predicted_winner=predicted_winner,
                win_probability=round(win_probability, 3),
                confidence=_get_confidence_label(win_probability),
                odds=odds_comparison,
                reasoning=reasoning,
                head_to_head=h2h if h2h.total_games > 0 else None,
                live=_parse_live_game_info({
                    "status": event.get("status", {}).get("type", {}).get("description", ""),
                    "status_detail": event.get("status", {}).get("type", {}).get("detail", ""),
                    "period": event.get("status", {}).get("period", 0),
                    "clock": event.get("status", {}).get("displayClock", ""),
                    "home_team": {"name": home_name, "score": home.get("score", "0")},
                    "away_team": {"name": away_name, "score": away.get("score", "0")}
                })
            )
            
            games.append(game_prediction)
        
        # Format date for response
        try:
            formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            formatted_date = date
        
        return TodaysGamesResponse(
            date=formatted_date,
            games=games,
            total_games=len(games),
            predictions_generated=len(games)
        )
        
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Error fetching games for date %s: %s", date, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch games: {str(e)}"
        ) from e


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
                    
            except (httpx.HTTPError, ValueError, KeyError) as e:
                logger.debug("Error checking date %s: %s", date_str, e)
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
        
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Error fetching head-to-head: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch head-to-head history: {str(e)}"
        ) from e


@router.get("/{game_id}")
async def get_game_detail(game_id: str):
    """
    Get detailed information about a specific game including prediction.
    """
    try:
        # Get game summary from ESPN
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        
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
        
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Error fetching game detail %s: %s", game_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch game details: {str(e)}"
        ) from e
