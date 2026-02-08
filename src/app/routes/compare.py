import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from ..services.cache_service import CacheService
from ..services.scoring_service import ScoringService
from ..services.proscons_service import ProsConsService
from ..services.sentiment_service import SentimentService
from ..services.async_reddit_service import AsyncRedditService
from ..services.injury_service import InjuryService
from ..services.history_service import HistoryService
from ..services.rate_limiter import limiter, RATE_LIMITS
from ..providers.basketball_provider import BasketballProvider
from ..utils.team_normalizer import TeamNormalizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])

# Initialize services
cache_service = CacheService(default_ttl=3600)  # 1 hour TTL
scoring_service = ScoringService()
proscons_service = ProsConsService()
sentiment_service = SentimentService()
async_reddit_service = AsyncRedditService(cache_service=cache_service)
injury_service = InjuryService()
basketball_provider = BasketballProvider()
history_service = HistoryService()


# Request Schemas
class Context(BaseModel):
    """Optional context for the comparison"""
    injuries: Optional[List[str]] = None
    gameDate: Optional[str] = None


class CompareRequest(BaseModel):
    """Request model for compare endpoint"""
    sport: str = Field(default="basketball", description="Sport type")
    team1: str = Field(..., description="First team name")
    team2: str = Field(..., description="Second team name")
    context: Optional[Context] = Field(default=None, description="Optional context information")


# Response Schemas
class TeamAnalysis(BaseModel):
    """Team analysis data"""
    pros: List[str] = Field(..., description="Team strengths")
    cons: List[str] = Field(..., description="Team weaknesses")
    stats_summary: str = Field(..., description="Statistical summary")
    sentiment_summary: str = Field(..., description="Sentiment analysis summary")


class MatchupAnalysis(BaseModel):
    """Matchup analysis data"""
    predicted_winner: str = Field(..., description="Predicted winning team")
    win_probability: float = Field(..., ge=0.0, le=1.0, description="Win probability for team1")
    score_breakdown: str = Field(..., description="Predicted score breakdown")
    confidence_label: str = Field(..., description="Confidence level label")


class Sources(BaseModel):
    """Data sources"""
    reddit: List[str] = Field(..., description="Reddit source URLs/posts")
    stats: List[str] = Field(..., description="Stats source URLs")


class CompareResponse(BaseModel):
    """Response model for compare endpoint"""
    team1: TeamAnalysis
    team2: TeamAnalysis
    matchup: MatchupAnalysis
    sources: Sources


def _format_stats_summary(stats: Dict[str, Any]) -> str:
    """Format stats dictionary into human-readable summary"""
    if not stats:
        return "Stats data not available"
    
    shooting_pct = stats.get('shooting_pct', 0.45)
    rebounding_avg = stats.get('rebounding_avg', 42.0)
    turnovers_avg = stats.get('turnovers_avg', 14.0)
    net_rating_proxy = stats.get('net_rating_proxy', 0.0)
    data_source = stats.get('data_source', 'unknown')
    
    parts = [
        f"Averaging {rebounding_avg:.1f} rebounds per game",
        f"{shooting_pct:.1%} field goal percentage",
        f"{turnovers_avg:.1f} turnovers per game"
    ]
    
    if net_rating_proxy != 0:
        sign = "+" if net_rating_proxy > 0 else ""
        parts.append(f"{sign}{net_rating_proxy:.1f} point differential")
    
    summary = ", ".join(parts)
    
    # Add note if using placeholder/estimated data
    if data_source == 'placeholder':
        summary += " (estimated/placeholder data - actual stats unavailable)"
    
    return summary


async def _generate_analysis(request: CompareRequest) -> CompareResponse:
    """
    Generate analysis using all services
    
    Args:
        request: CompareRequest with team names and optional context
        
    Returns:
        CompareResponse with complete analysis
        
    Raises:
        Exception: If critical errors occur during analysis
    """
    team1_name = request.team1
    team2_name = request.team2
    
    # Get injuries from context (injury service is placeholder for future API integration)
    injuries1 = request.context.injuries if request.context else None
    injuries2 = request.context.injuries if request.context else None
    
    try:
        # Get stats from BasketballProvider
        logger.info("Fetching stats for %s and %s", team1_name, team2_name)
        team1_stats = basketball_provider.get_team_stats_summary(team1_name)
        team2_stats = basketball_provider.get_team_stats_summary(team2_name)
        logger.debug("Stats retrieved: team1=%s, team2=%s", team1_stats.get('data_source'), team2_stats.get('data_source'))
    except Exception as e:
        logger.error("Error fetching stats: %s", e, exc_info=True)
        # Use placeholder stats as fallback
        team1_stats = basketball_provider.get_placeholder_stats(team1_name)
        team2_stats = basketball_provider.get_placeholder_stats(team2_name)
    
    try:
        # Get Reddit data (async)
        logger.info("Fetching Reddit data for %s and %s", team1_name, team2_name)
        team1_reddit_posts = await async_reddit_service.fetch_team_posts(team1_name, limit=10, include_comments=True)
        team2_reddit_posts = await async_reddit_service.fetch_team_posts(team2_name, limit=10, include_comments=True)
        logger.debug("Reddit posts retrieved: team1=%d, team2=%d", len(team1_reddit_posts), len(team2_reddit_posts))
    except Exception as e:
        logger.warning("Error fetching Reddit data: %s, continuing without Reddit data", e)
        team1_reddit_posts = []
        team2_reddit_posts = []
    
    try:
        # Analyze sentiment
        team1_sentiment = sentiment_service.analyze_sentiment(team1_reddit_posts)
        team2_sentiment = sentiment_service.analyze_sentiment(team2_reddit_posts)
    except Exception as e:
        logger.warning("Error analyzing sentiment: %s, using default sentiment", e)
        team1_sentiment = "Sentiment analysis unavailable"
        team2_sentiment = "Sentiment analysis unavailable"
    
    try:
        # Generate pros/cons
        team1_proscons = proscons_service.generate_pros_cons(
            team1_stats,
            team1_sentiment,
            injuries1
        )
        team2_proscons = proscons_service.generate_pros_cons(
            team2_stats,
            team2_sentiment,
            injuries2
        )
    except Exception as e:
        logger.error("Error generating pros/cons: %s", e, exc_info=True)
        # Fallback to generic pros/cons
        team1_proscons = {'pros': ['Analysis available'], 'cons': ['Limited data']}
        team2_proscons = {'pros': ['Analysis available'], 'cons': ['Limited data']}
    
    try:
        # Calculate matchup
        matchup_result = scoring_service.calculate_matchup(
            team1_name=team1_name,
            team2_name=team2_name,
            team1_stats=team1_stats,
            team2_stats=team2_stats,
            team1_sentiment=team1_sentiment,
            team2_sentiment=team2_sentiment,
            team1_injuries=injuries1,
            team2_injuries=injuries2
        )
    except Exception as e:
        logger.error("Error calculating matchup: %s", e, exc_info=True)
        # Fallback matchup
        matchup_result = {
            'predicted_winner': team1_name,
            'win_probability': 0.5,
            'score_breakdown': f"Predicted final score: {team1_name} 110-110 {team2_name}",
            'confidence_label': 'Low confidence'
        }
    
    # Format stats summaries
    team1_stats_summary = _format_stats_summary(team1_stats)
    team2_stats_summary = _format_stats_summary(team2_stats)
    
    # Build sources
    reddit_sources: List[str] = []
    try:
        if team1_reddit_posts:
            reddit_sources.extend([post.get('url', '') for post in team1_reddit_posts[:3] if post.get('url')])
        if team2_reddit_posts:
            reddit_sources.extend([post.get('url', '') for post in team2_reddit_posts[:3] if post.get('url')])
        reddit_sources = list(set(reddit_sources))[:5]  # Deduplicate and limit
    except Exception as e:
        logger.warning("Error building Reddit sources: %s", e)
    
    stats_sources = [
        f"NBA API stats for {team1_name}",
        f"NBA API stats for {team2_name}"
    ]
    
    return CompareResponse(
        team1=TeamAnalysis(
            pros=team1_proscons['pros'],
            cons=team1_proscons['cons'],
            stats_summary=team1_stats_summary,
            sentiment_summary=team1_sentiment
        ),
        team2=TeamAnalysis(
            pros=team2_proscons['pros'],
            cons=team2_proscons['cons'],
            stats_summary=team2_stats_summary,
            sentiment_summary=team2_sentiment
        ),
        matchup=MatchupAnalysis(
            predicted_winner=matchup_result['predicted_winner'],
            win_probability=matchup_result['win_probability'],
            score_breakdown=matchup_result['score_breakdown'],
            confidence_label=matchup_result['confidence_label']
        ),
        sources=Sources(
            reddit=reddit_sources if reddit_sources else ["No Reddit sources available"],
            stats=stats_sources
        )
    )


@router.post("", response_model=CompareResponse)
@limiter.limit(RATE_LIMITS["compare"])
async def compare(request: Request, body: CompareRequest) -> CompareResponse:
    """
    Compare endpoint with caching and full analysis
    
    Args:
        request: FastAPI request object (for rate limiting)
        body: CompareRequest with team names and optional context
        
    Returns:
        CompareResponse with complete team analysis
        
    Raises:
        HTTPException: If comparison fails
    """
    logger.info("Compare endpoint called: %s vs %s (%s)", body.team1, body.team2, body.sport)
    
    # Validate sport (currently only basketball supported)
    if body.sport.lower() != "basketball":
        logger.warning("Unsupported sport requested: %s", body.sport)
        raise HTTPException(
            status_code=400,
            detail=f"Sport '{body.sport}' is not supported. Currently only 'basketball' is supported."
        )
    
    # Normalize team names (e.g., "celtics" -> "Boston Celtics", "lakers" -> "Los Angeles Lakers")
    original_team1 = body.team1
    original_team2 = body.team2
    normalized_team1 = TeamNormalizer.normalize(body.team1)
    normalized_team2 = TeamNormalizer.normalize(body.team2)
    
    # Log normalization if it changed
    if original_team1 != normalized_team1:
        logger.info("Normalized team1: '%s' -> '%s'", original_team1, normalized_team1)
    if original_team2 != normalized_team2:
        logger.info("Normalized team2: '%s' -> '%s'", original_team2, normalized_team2)
    
    # Update request with normalized names for processing
    body.team1 = normalized_team1
    body.team2 = normalized_team2
    
    # Extract date from context if available
    date = body.context.gameDate if body.context else None
    
    try:
        # Check cache (using normalized names to ensure cache hits for same teams)
        cached_response = cache_service.get(
            sport=body.sport,
            team1=normalized_team1,
            team2=normalized_team2,
            date=date
        )
        
        if cached_response is not None:
            logger.info("Returning cached response for %s vs %s", normalized_team1, normalized_team2)
            return cached_response
    except Exception as e:
        logger.warning("Cache check failed: %s, continuing without cache", e)
    
    try:
        # Generate analysis using all services (with normalized names)
        logger.info("Cache miss - generating new analysis for %s vs %s", normalized_team1, normalized_team2)
        response = await _generate_analysis(body)
        
        # Cache the response (using normalized names)
        try:
            cache_service.set(
                sport=body.sport,
                team1=normalized_team1,
                team2=normalized_team2,
                value=response,
                date=date
            )
        except Exception as e:
            logger.warning("Failed to cache response: %s", e)
        
        # Save to history
        try:
            history_service.add_comparison(
                team1=normalized_team1,
                team2=normalized_team2,
                sport=body.sport,
                result=response.dict() if hasattr(response, 'dict') else response
            )
        except Exception as e:
            logger.warning("Failed to save to history: %s", e)
        
        return response
        
    except Exception as e:
        logger.error("Error generating comparison: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate comparison: {str(e)}"
        ) from e

