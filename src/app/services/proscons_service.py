import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ProsConsService:
    """Service for generating pros and cons for teams based on stats, injuries, and sentiment"""
    
    def __init__(self):
        """Initialize the pros/cons service"""
        self.logger = logging.getLogger(__name__)
    
    def _generate_pros_from_stats(self, stats: Dict[str, Any]) -> List[str]:
        """Generate pros from team statistics"""
        pros = []
        
        if not stats or stats.get('data_source') == 'placeholder':
            return pros
        
        shooting_pct = stats.get('shooting_pct', 0.45)
        rebounding_avg = stats.get('rebounding_avg', 42.0)
        turnovers_avg = stats.get('turnovers_avg', 14.0)
        net_rating_proxy = stats.get('net_rating_proxy', 0.0)
        
        # Shooting percentage
        if shooting_pct >= 0.47:
            pros.append("Excellent shooting efficiency")
        elif shooting_pct >= 0.45:
            pros.append("Strong field goal percentage")
        
        # Rebounding
        if rebounding_avg >= 45:
            pros.append("Dominant rebounding presence")
        elif rebounding_avg >= 43:
            pros.append("Strong rebounding performance")
        
        # Turnovers (lower is better)
        if turnovers_avg <= 12:
            pros.append("Excellent ball control and low turnover rate")
        elif turnovers_avg <= 13.5:
            pros.append("Good ball security")
        
        # Net rating
        if net_rating_proxy >= 5:
            pros.append("Strong positive point differential")
        elif net_rating_proxy >= 2:
            pros.append("Consistent scoring advantage")
        
        return pros
    
    def _generate_cons_from_stats(self, stats: Dict[str, Any]) -> List[str]:
        """Generate cons from team statistics"""
        cons = []
        
        if not stats or stats.get('data_source') == 'placeholder':
            return cons
        
        shooting_pct = stats.get('shooting_pct', 0.45)
        rebounding_avg = stats.get('rebounding_avg', 42.0)
        turnovers_avg = stats.get('turnovers_avg', 14.0)
        net_rating_proxy = stats.get('net_rating_proxy', 0.0)
        
        # Shooting percentage
        if shooting_pct < 0.43:
            cons.append("Below-average shooting efficiency")
        elif shooting_pct < 0.45:
            cons.append("Inconsistent shooting performance")
        
        # Rebounding
        if rebounding_avg < 40:
            cons.append("Rebounding struggles")
        elif rebounding_avg < 42:
            cons.append("Average rebounding numbers")
        
        # Turnovers (higher is worse)
        if turnovers_avg >= 16:
            cons.append("High turnover rate and ball security concerns")
        elif turnovers_avg >= 15:
            cons.append("Turnover-prone in key situations")
        
        # Net rating
        if net_rating_proxy <= -3:
            cons.append("Negative point differential indicates defensive issues")
        elif net_rating_proxy <= 0:
            cons.append("Marginal scoring differential")
        
        return cons
    
    def _generate_pros_from_sentiment(self, sentiment_summary: str) -> List[str]:
        """Generate pros from sentiment analysis"""
        pros = []
        
        if not sentiment_summary:
            return pros
        
        summary_lower = sentiment_summary.lower()
        
        if any(word in summary_lower for word in ['positive', 'optimistic', 'confident']):
            pros.append("Positive fan and community sentiment")
        if any(word in summary_lower for word in ['strong', 'excellent', 'great']):
            pros.append("Strong community support and enthusiasm")
        if 'confidence' in summary_lower and 'high' in summary_lower:
            pros.append("High confidence in team performance")
        
        return pros
    
    def _generate_cons_from_sentiment(self, sentiment_summary: str) -> List[str]:
        """Generate cons from sentiment analysis"""
        cons = []
        
        if not sentiment_summary:
            return cons
        
        summary_lower = sentiment_summary.lower()
        
        if any(word in summary_lower for word in ['negative', 'concerns', 'worries', 'uncertainty']):
            cons.append("Community sentiment shows concerns")
        if any(word in summary_lower for word in ['poor', 'disappointing', 'struggling']):
            cons.append("Disappointing performance from fan perspective")
        if 'mixed' in summary_lower or 'uncertain' in summary_lower:
            cons.append("Uncertainty in team outlook")
        
        return cons
    
    def _generate_pros_from_injuries(self, injuries: Optional[list]) -> List[str]:
        """Generate pros from injuries (healthy roster)"""
        pros = []
        
        if not injuries or len(injuries) == 0:
            pros.append("Full roster availability")
            pros.append("No significant injury concerns")
        
        return pros
    
    def _generate_cons_from_injuries(self, injuries: Optional[list]) -> List[str]:
        """Generate cons from injuries"""
        cons = []
        
        if not injuries or len(injuries) == 0:
            return cons
        
        # Count significant injuries
        significant_injuries = [
            inj for inj in injuries
            if any(word in inj.lower() for word in ['out', 'injured', 'surgery', 'fracture', 'torn'])
        ]
        
        if len(significant_injuries) >= 2:
            cons.append(f"Multiple key players injured: {', '.join(significant_injuries[:2])}")
        elif len(significant_injuries) == 1:
            cons.append(f"Key player injury concern: {significant_injuries[0]}")
        elif len(injuries) > 0:
            cons.append(f"Injury concerns: {', '.join(injuries[:2])}")
        
        return cons
    
    def generate_pros_cons(
        self,
        stats: Dict[str, Any],
        sentiment_summary: str = "",
        injuries: Optional[list] = None,
        min_pros: int = 3,
        max_pros: int = 5,
        min_cons: int = 3,
        max_cons: int = 5
    ) -> Dict[str, List[str]]:
        """
        Generate pros and cons for a team
        
        Args:
            stats: Team stats dictionary
            sentiment_summary: Sentiment summary string
            injuries: List of injury descriptions
            min_pros: Minimum number of pros to generate
            max_pros: Maximum number of pros to generate
            min_cons: Minimum number of cons to generate
            max_cons: Maximum number of cons to generate
            
        Returns:
            Dictionary with 'pros' and 'cons' lists
        """
        # Collect pros from different sources
        all_pros = []
        all_pros.extend(self._generate_pros_from_stats(stats))
        all_pros.extend(self._generate_pros_from_sentiment(sentiment_summary))
        all_pros.extend(self._generate_pros_from_injuries(injuries))
        
        # Collect cons from different sources
        all_cons = []
        all_cons.extend(self._generate_cons_from_stats(stats))
        all_cons.extend(self._generate_cons_from_sentiment(sentiment_summary))
        all_cons.extend(self._generate_cons_from_injuries(injuries))
        
        # Select final pros (prioritize, remove duplicates, limit count)
        # Remove duplicates while preserving order
        seen = set()
        unique_pros = []
        for pro in all_pros:
            if pro not in seen:
                seen.add(pro)
                unique_pros.append(pro)
        
        # Select final count
        final_pros = unique_pros[:max_pros]
        
        # Ensure minimum if we have enough data
        if len(final_pros) < min_pros and len(all_pros) >= min_pros:
            final_pros = all_pros[:max_pros]
        
        # If still not enough, add generic pros
        if len(final_pros) < min_pros:
            generic_pros = [
                "Experienced roster with playoff potential",
                "Strong team chemistry and coaching",
                "Competitive in key matchups"
            ]
            for gp in generic_pros:
                if len(final_pros) >= max_pros:
                    break
                if gp not in final_pros:
                    final_pros.append(gp)
        
        # Select final cons (same process)
        seen = set()
        unique_cons = []
        for con in all_cons:
            if con not in seen:
                seen.add(con)
                unique_cons.append(con)
        
        final_cons = unique_cons[:max_cons]
        
        if len(final_cons) < min_cons and len(all_cons) >= min_cons:
            final_cons = all_cons[:max_cons]
        
        # If still not enough, add generic cons
        if len(final_cons) < min_cons:
            generic_cons = [
                "Consistency issues in recent performances",
                "Room for improvement in key areas",
                "Challenges in closing out games"
            ]
            for gc in generic_cons:
                if len(final_cons) >= max_cons:
                    break
                if gc not in final_cons:
                    final_cons.append(gc)
        
        return {
            'pros': final_pros[:max_pros],
            'cons': final_cons[:max_cons]
        }

