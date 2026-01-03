import logging
from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])


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


@router.post("", response_model=CompareResponse)
async def compare(request: CompareRequest):
    """Compare endpoint with mock data"""
    logger.info(f"Compare endpoint called: {request.team1} vs {request.team2} ({request.sport})")
    
    # Mock data
    return CompareResponse(
        team1=TeamAnalysis(
            pros=[
                "Strong defensive rebounding",
                "Excellent three-point shooting percentage",
                "Depth in bench players"
            ],
            cons=[
                "Turnover-prone in fast break situations",
                "Weak free-throw shooting"
            ],
            stats_summary="Averaging 112.3 PPG with 45.2% FG, ranking 8th in the league",
            sentiment_summary="Fan sentiment is generally positive with high confidence in playoff potential"
        ),
        team2=TeamAnalysis(
            pros=[
                "Elite perimeter defense",
                "Strong home court advantage",
                "Experienced playoff roster"
            ],
            cons=[
                "Injury concerns with key players",
                "Limited bench scoring production"
            ],
            stats_summary="Averaging 108.7 PPG with 43.8% FG, ranking 12th in the league",
            sentiment_summary="Mixed sentiment with concerns about recent performance trends"
        ),
        matchup=MatchupAnalysis(
            predicted_winner=request.team1,
            win_probability=0.62,
            score_breakdown="Predicted final score: 115-109",
            confidence_label="High confidence"
        ),
        sources=Sources(
            reddit=[
                "https://reddit.com/r/nba/comments/example1",
                "https://reddit.com/r/nba/comments/example2"
            ],
            stats=[
                "https://stats.example.com/game/12345",
                "https://stats.example.com/teams/team1-vs-team2"
            ]
        )
    )

