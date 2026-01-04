import logging
import math
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for calculating team scores and win probabilities"""
    
    def __init__(self):
        """Initialize the scoring service"""
        self.logger = logging.getLogger(__name__)
    
    def _sigmoid(self, x: float, midpoint: float = 0.0, steepness: float = 1.0) -> float:
        """
        Sigmoid function to convert score difference to probability
        
        Args:
            x: Input value (score difference)
            midpoint: Midpoint of sigmoid (default 0)
            steepness: Steepness factor (default 1.0)
            
        Returns:
            Probability between 0 and 1
        """
        return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
    
    def _normalize_stat(self, value: float, min_val: float, max_val: float) -> float:
        """
        Normalize a stat value to 0-1 range
        
        Args:
            value: Value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value
            
        Returns:
            Normalized value between 0 and 1
        """
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)
    
    def calculate_stats_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate score from team statistics
        
        Args:
            stats: Team stats dictionary from BasketballProvider
            
        Returns:
            Score between 0 and 1
        """
        # Default values if stats not available
        if not stats or stats.get('data_source') == 'placeholder':
            return 0.5  # Neutral score
        
        # Extract stats (normalized to reasonable ranges)
        shooting_pct = stats.get('shooting_pct', 0.45)
        rebounding_avg = stats.get('rebounding_avg', 42.0)
        turnovers_avg = stats.get('turnovers_avg', 14.0)
        net_rating_proxy = stats.get('net_rating_proxy', 0.0)
        
        # Normalize stats to 0-1 range
        # Shooting: 0.35-0.55 (typical NBA range)
        shooting_score = self._normalize_stat(shooting_pct, 0.35, 0.55)
        
        # Rebounding: 35-50 (typical NBA range)
        rebounding_score = self._normalize_stat(rebounding_avg, 35.0, 50.0)
        
        # Turnovers: lower is better, so invert (12-18 range)
        turnover_score = 1.0 - self._normalize_stat(turnovers_avg, 12.0, 18.0)
        
        # Net rating: -10 to +10 range
        net_rating_score = self._normalize_stat(net_rating_proxy, -10.0, 10.0)
        
        # Weighted combination
        stats_score = (
            shooting_score * 0.3 +
            rebounding_score * 0.2 +
            turnover_score * 0.2 +
            net_rating_score * 0.3
        )
        
        return max(0.0, min(1.0, stats_score))
    
    def calculate_sentiment_tilt(self, sentiment_summary: str) -> float:
        """
        Calculate sentiment tilt from sentiment summary text
        
        Args:
            sentiment_summary: Sentiment summary string
            
        Returns:
            Tilt value between -0.2 and 0.2 (small adjustment to score)
        """
        if not sentiment_summary:
            return 0.0
        
        summary_lower = sentiment_summary.lower()
        
        # Positive indicators
        positive_words = ['positive', 'great', 'excellent', 'amazing', 'fantastic', 'strong', 'good']
        positive_count = sum(1 for word in positive_words if word in summary_lower)
        
        # Negative indicators
        negative_words = ['negative', 'poor', 'bad', 'terrible', 'weak', 'concerns', 'worries']
        negative_count = sum(1 for word in negative_words if word in summary_lower)
        
        # Calculate tilt (-0.2 to 0.2 range)
        if positive_count > negative_count:
            tilt = min(0.2, positive_count * 0.05)
        elif negative_count > positive_count:
            tilt = max(-0.2, negative_count * -0.05)
        else:
            tilt = 0.0
        
        return tilt
    
    def calculate_injuries_penalty(self, injuries: Optional[list]) -> float:
        """
        Calculate penalty for injuries
        
        Args:
            injuries: List of injury descriptions
            
        Returns:
            Penalty value between 0 and -0.15
        """
        if not injuries or len(injuries) == 0:
            return 0.0
        
        # Count significant injuries (those mentioning "out" or similar)
        significant_injuries = sum(
            1 for injury in injuries
            if any(word in injury.lower() for word in ['out', 'injured', 'surgery', 'fracture'])
        )
        
        # Penalty: -0.05 per significant injury, max -0.15
        penalty = min(-0.15, significant_injuries * -0.05)
        
        return penalty
    
    def calculate_team_score(
        self,
        stats: Dict[str, Any],
        sentiment_tilt: float = 0.0,
        injuries_penalty: float = 0.0
    ) -> float:
        """
        Calculate overall team score
        
        Args:
            stats: Team stats dictionary
            sentiment_tilt: Sentiment adjustment (-0.2 to 0.2)
            injuries_penalty: Injuries penalty (0 to -0.15)
            
        Returns:
            Team score between 0 and 1
        """
        stats_score = self.calculate_stats_score(stats)
        
        # Apply adjustments
        team_score = stats_score + sentiment_tilt + injuries_penalty
        
        # Clamp to valid range
        return max(0.0, min(1.0, team_score))
    
    def calculate_win_probability(
        self,
        team1_score: float,
        team2_score: float,
        steepness: float = 3.0
    ) -> float:
        """
        Calculate win probability for team1 using sigmoid
        
        Args:
            team1_score: Score for team 1 (0-1)
            team2_score: Score for team 2 (0-1)
            steepness: Sigmoid steepness factor
            
        Returns:
            Win probability for team1 (0-1)
        """
        # Score difference (scaled to -2 to 2 range for sigmoid)
        score_diff = (team1_score - team2_score) * 2.0
        
        # Convert to probability using sigmoid
        probability = self._sigmoid(score_diff, midpoint=0.0, steepness=steepness)
        
        return probability
    
    def generate_score_breakdown(
        self,
        team1_score: float,
        team2_score: float,
        team1_name: str,
        team2_name: str
    ) -> str:
        """
        Generate human-readable score breakdown
        
        Args:
            team1_score: Score for team 1
            team2_score: Score for team 2
            team1_name: Name of team 1
            team2_name: Name of team 2
            
        Returns:
            Formatted score breakdown string
        """
        score_diff = team1_score - team2_score
        
        # Estimate score based on score difference
        # Typical NBA scores: 100-120 range
        base_score = 110
        score_margin = score_diff * 20  # Scale difference to realistic margin
        
        team1_points = base_score + score_margin
        team2_points = base_score - score_margin
        
        # Ensure team1_points >= team2_points (winner first)
        # Also ensure minimum difference to avoid ties
        if team1_points < team2_points:
            team1_points, team2_points = team2_points, team1_points
            team1_name, team2_name = team2_name, team1_name
        elif team1_points == team2_points:
            # Add small margin to avoid ties
            team1_points += 1
        
        # Capitalize team names properly
        team1_name_formatted = team1_name.title()
        team2_name_formatted = team2_name.title()
        
        return f"Predicted final score: {team1_name_formatted} {int(team1_points)}-{int(team2_points)} {team2_name_formatted}"
    
    def generate_confidence_label(self, win_probability: float) -> str:
        """
        Generate confidence label based on win probability
        
        Args:
            win_probability: Win probability for team 1 (0-1)
            
        Returns:
            Confidence label string
        """
        # Calculate distance from 0.5 (neutral)
        distance_from_neutral = abs(win_probability - 0.5)
        
        if distance_from_neutral > 0.3:
            return "High confidence"
        elif distance_from_neutral > 0.15:
            return "Moderate confidence"
        else:
            return "Low confidence"
    
    def calculate_matchup(
        self,
        team1_name: str,
        team2_name: str,
        team1_stats: Dict[str, Any],
        team2_stats: Dict[str, Any],
        team1_sentiment: str = "",
        team2_sentiment: str = "",
        team1_injuries: Optional[list] = None,
        team2_injuries: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete matchup analysis
        
        Args:
            team1_name: Name of team 1
            team2_name: Name of team 2
            team1_stats: Stats for team 1
            team2_stats: Stats for team 2
            team1_sentiment: Sentiment summary for team 1
            team2_sentiment: Sentiment summary for team 2
            team1_injuries: Injuries for team 1
            team2_injuries: Injuries for team 2
            
        Returns:
            Dictionary with predicted_winner, win_probability, score_breakdown, confidence_label
        """
        # Calculate sentiment tilts
        team1_sentiment_tilt = self.calculate_sentiment_tilt(team1_sentiment)
        team2_sentiment_tilt = self.calculate_sentiment_tilt(team2_sentiment)
        
        # Calculate injuries penalties
        team1_injuries_penalty = self.calculate_injuries_penalty(team1_injuries)
        team2_injuries_penalty = self.calculate_injuries_penalty(team2_injuries)
        
        # Calculate team scores
        team1_score = self.calculate_team_score(team1_stats, team1_sentiment_tilt, team1_injuries_penalty)
        team2_score = self.calculate_team_score(team2_stats, team2_sentiment_tilt, team2_injuries_penalty)
        
        # Calculate win probability
        win_probability = self.calculate_win_probability(team1_score, team2_score)
        
        # Determine winner
        predicted_winner = team1_name if win_probability > 0.5 else team2_name
        
        # Generate breakdown and confidence
        score_breakdown = self.generate_score_breakdown(team1_score, team2_score, team1_name, team2_name)
        confidence_label = self.generate_confidence_label(win_probability)
        
        return {
            'predicted_winner': predicted_winner,
            'win_probability': round(win_probability, 3),
            'score_breakdown': score_breakdown,
            'confidence_label': confidence_label,
            'team1_score': round(team1_score, 3),
            'team2_score': round(team2_score, 3)
        }

