import logging
from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..services.cache_service import CacheService
from ..services.scoring_service import ScoringService
from ..services.proscons_service import ProsConsService
from ..services.sentiment_service import SentimentService
from ..services.reddit_service import RedditService
from ..providers.basketball_provider import BasketballProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])

# Initialize services
cache_service = CacheService(default_ttl=3600)  # 1 hour TTL
scoring_service = ScoringService()
proscons_service = ProsConsService()
sentiment_service = SentimentService()
reddit_service = RedditService(cache_service=cache_service)
basketball_provider = BasketballProvider()


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


def _format_stats_summary(stats: dict) -> str:
    """Format stats dictionary into human-readable summary"""
    if not stats or stats.get('data_source') == 'placeholder':
        return "Stats data not available"
    
    shooting_pct = stats.get('shooting_pct', 0.45)
    rebounding_avg = stats.get('rebounding_avg', 42.0)
    turnovers_avg = stats.get('turnovers_avg', 14.0)
    net_rating_proxy = stats.get('net_rating_proxy', 0.0)
    
    parts = [
        f"Averaging {rebounding_avg:.1f} rebounds per game",
        f"{shooting_pct:.1%} field goal percentage",
        f"{turnovers_avg:.1f} turnovers per game"
    ]
    
    if net_rating_proxy != 0:
        sign = "+" if net_rating_proxy > 0 else ""
        parts.append(f"{sign}{net_rating_proxy:.1f} point differential")
    
    return ", ".join(parts)


async def _generate_analysis(request: CompareRequest) -> CompareResponse:
    """Generate analysis using all services"""
    team1_name = request.team1
    team2_name = request.team2
    injuries1 = request.context.injuries if request.context else None
    injuries2 = request.context.injuries if request.context else None  # Could be different in future
    
    # Get stats from BasketballProvider
    logger.info(f"Fetching stats for {team1_name} and {team2_name}")
    team1_stats = basketball_provider.get_team_stats_summary(team1_name)
    team2_stats = basketball_provider.get_team_stats_summary(team2_name)
    
    # Get Reddit data
    logger.info(f"Fetching Reddit data for {team1_name} and {team2_name}")
    team1_reddit_posts = reddit_service.fetch_team_posts(team1_name, limit=10, include_comments=True)
    team2_reddit_posts = reddit_service.fetch_team_posts(team2_name, limit=10, include_comments=True)
    
    # Analyze sentiment
    team1_sentiment = sentiment_service.analyze_sentiment(team1_reddit_posts)
    team2_sentiment = sentiment_service.analyze_sentiment(team2_reddit_posts)
    
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
    
    # Format stats summaries
    team1_stats_summary = _format_stats_summary(team1_stats)
    team2_stats_summary = _format_stats_summary(team2_stats)
    
    # Build sources
    reddit_sources = []
    if team1_reddit_posts:
        reddit_sources.extend([post.get('url', '') for post in team1_reddit_posts[:3] if post.get('url')])
    if team2_reddit_posts:
        reddit_sources.extend([post.get('url', '') for post in team2_reddit_posts[:3] if post.get('url')])
    reddit_sources = list(set(reddit_sources))[:5]  # Deduplicate and limit
    
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
async def compare(request: CompareRequest):
    """Compare endpoint with caching and full analysis"""
    logger.info(f"Compare endpoint called: {request.team1} vs {request.team2} ({request.sport})")
    
    # Extract date from context if available
    date = request.context.gameDate if request.context else None
    
    # Check cache
    cached_response = cache_service.get(
        sport=request.sport,
        team1=request.team1,
        team2=request.team2,
        date=date
    )
    
    if cached_response is not None:
        logger.info("Returning cached response")
        return cached_response
    
    # Generate analysis using all services
    logger.info("Cache miss - generating new analysis")
    response = await _generate_analysis(request)
    
    # Cache the response
    cache_service.set(
        sport=request.sport,
        team1=request.team1,
        team2=request.team2,
        value=response,
        date=date
    )
    
    return response

