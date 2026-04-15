import logging
import math
from typing import Dict, Any, Optional

from ..config import cfg

logger = logging.getLogger(__name__)

# Shorthand references into config.json sections
_scoring = cfg.get("scoring", {})
_norm    = _scoring.get("normalize", {})
_fb      = cfg.get("fallback_stats", {})


class ScoringService:
    """Service for calculating team scores and win probabilities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _sigmoid(self, x: float, midpoint: float = 0.0, steepness: float = 1.0) -> float:
        """Sigmoid function to convert score difference to probability"""
        return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
    
    def _normalize_stat(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a stat value to 0-1 range"""
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)
    
    def calculate_stats_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate score from team statistics.

        All weights and normalization ranges are read from config.json
        so they can be tuned without code changes.
        """
        if not stats or stats.get('data_source') == 'placeholder':
            return 0.5

        shooting_pct     = stats.get('shooting_pct',     _fb.get("shooting_pct", 0.45))
        rebounding_avg   = stats.get('rebounding_avg',   _fb.get("rebounding_avg", 42.0))
        turnovers_avg    = stats.get('turnovers_avg',    _fb.get("turnovers_avg", 14.0))
        net_rating_proxy = stats.get('net_rating_proxy', _fb.get("net_rating_proxy", 0.0))
        assists_avg      = stats.get('assists_avg',      _fb.get("assists_avg", 24.0))
        win_pct          = stats.get('win_pct',          _fb.get("win_pct", 0.0))

        # Normalization ranges from config
        nr = _norm
        shooting_score    = self._normalize_stat(shooting_pct,     nr.get("shooting_pct",     {}).get("min", 0.35),  nr.get("shooting_pct",     {}).get("max", 0.55))
        rebounding_score  = self._normalize_stat(rebounding_avg,   nr.get("rebounding_avg",   {}).get("min", 35.0),  nr.get("rebounding_avg",   {}).get("max", 50.0))
        turnover_score    = 1.0 - self._normalize_stat(turnovers_avg, nr.get("turnovers_avg", {}).get("min", 12.0),  nr.get("turnovers_avg",    {}).get("max", 18.0))
        net_rating_score  = self._normalize_stat(net_rating_proxy, nr.get("net_rating_proxy", {}).get("min", -10.0), nr.get("net_rating_proxy", {}).get("max", 10.0))
        assists_score     = self._normalize_stat(assists_avg,      nr.get("assists_avg",      {}).get("min", 20.0),  nr.get("assists_avg",      {}).get("max", 30.0))

        if win_pct > 0:
            win_pct_score = self._normalize_stat(win_pct, nr.get("win_pct", {}).get("min", 0.25), nr.get("win_pct", {}).get("max", 0.75))
            w = _scoring.get("weights_with_win_pct", {})
            stats_score = (
                win_pct_score    * w.get("win_pct",    0.25) +
                net_rating_score * w.get("net_rating", 0.22) +
                shooting_score   * w.get("shooting",   0.18) +
                assists_score    * w.get("assists",    0.12) +
                rebounding_score * w.get("rebounding", 0.12) +
                turnover_score   * w.get("turnovers",  0.11)
            )
        else:
            w = _scoring.get("weights_no_win_pct", {})
            stats_score = (
                net_rating_score * w.get("net_rating", 0.28) +
                shooting_score   * w.get("shooting",   0.22) +
                assists_score    * w.get("assists",    0.15) +
                rebounding_score * w.get("rebounding", 0.18) +
                turnover_score   * w.get("turnovers",  0.17)
            )

        return max(0.0, min(1.0, stats_score))
    
    def calculate_sentiment_tilt(self, sentiment_summary: str) -> float:
        """
        Calculate sentiment tilt from sentiment summary text.

        Returns:
            Tilt value (small adjustment to score)
        """
        if not sentiment_summary:
            return 0.0
        
        sent_cfg = _scoring.get("sentiment", {})
        tilt_max = sent_cfg.get("tilt_max", 0.2)
        tilt_per = sent_cfg.get("tilt_per_word", 0.05)

        summary_lower = sentiment_summary.lower()
        
        positive_words = sent_cfg.get("positive_words", ['positive', 'great', 'excellent', 'amazing', 'fantastic', 'strong', 'good'])
        positive_count = sum(1 for word in positive_words if word in summary_lower)
        
        negative_words = sent_cfg.get("negative_words", ['negative', 'poor', 'bad', 'terrible', 'weak', 'concerns', 'worries'])
        negative_count = sum(1 for word in negative_words if word in summary_lower)
        
        if positive_count > negative_count:
            tilt = min(tilt_max, positive_count * tilt_per)
        elif negative_count > positive_count:
            tilt = max(-tilt_max, negative_count * -tilt_per)
        else:
            tilt = 0.0
        
        return tilt
    
    def calculate_injuries_penalty(self, injuries: Optional[list]) -> float:
        """
        Calculate penalty for injuries.

        Returns:
            Penalty value (negative float, or 0.0 for no injuries)
        """
        if not injuries or len(injuries) == 0:
            return 0.0
        
        inj_cfg = _scoring.get("injuries", {})
        keywords = inj_cfg.get("significant_keywords", ['out', 'injured', 'surgery', 'fracture'])
        per_injury = inj_cfg.get("penalty_per_injury", -0.05)
        penalty_max = inj_cfg.get("penalty_max", -0.15)

        significant_injuries = sum(
            1 for injury in injuries
            if any(word in injury.lower() for word in keywords)
        )
        
        penalty = max(penalty_max, significant_injuries * per_injury)
        
        return penalty
    
    def calculate_team_score(
        self,
        stats: Dict[str, Any],
        sentiment_tilt: float = 0.0,
        injuries_penalty: float = 0.0
    ) -> float:
        """Calculate overall team score"""
        stats_score = self.calculate_stats_score(stats)
        team_score = stats_score + sentiment_tilt + injuries_penalty
        return max(0.0, min(1.0, team_score))
    
    def calculate_win_probability(
        self,
        team1_score: float,
        team2_score: float,
        steepness: float | None = None
    ) -> float:
        """Calculate win probability for team1 using sigmoid"""
        wp_cfg = _scoring.get("win_probability", {})
        if steepness is None:
            steepness = wp_cfg.get("sigmoid_steepness", 3.0)
        scale = wp_cfg.get("score_diff_scale", 2.0)
        score_diff = (team1_score - team2_score) * scale
        return self._sigmoid(score_diff, midpoint=0.0, steepness=steepness)
    
    def generate_score_breakdown(
        self,
        team1_score: float,
        team2_score: float,
        team1_name: str,
        team2_name: str
    ) -> str:
        """Generate human-readable score breakdown"""
        sb_cfg = _scoring.get("score_breakdown", {})
        base_score = sb_cfg.get("base_score", 110)
        margin_scale = sb_cfg.get("margin_scale", 20)

        score_diff = team1_score - team2_score
        score_margin = score_diff * margin_scale
        
        team1_points = base_score + score_margin
        team2_points = base_score - score_margin
        
        if team1_points < team2_points:
            team1_points, team2_points = team2_points, team1_points
            team1_name, team2_name = team2_name, team1_name
        elif team1_points == team2_points:
            team1_points += 1
        
        team1_name_formatted = team1_name.title()
        team2_name_formatted = team2_name.title()
        
        return f"Predicted final score: {team1_name_formatted} {int(team1_points)}-{int(team2_points)} {team2_name_formatted}"
    
    def generate_confidence_label(self, win_probability: float) -> str:
        """Generate confidence label based on win probability"""
        conf_cfg = _scoring.get("confidence", {})
        high = conf_cfg.get("high_threshold", 0.3)
        moderate = conf_cfg.get("moderate_threshold", 0.15)

        distance_from_neutral = abs(win_probability - 0.5)
        
        if distance_from_neutral > high:
            return "High confidence"
        elif distance_from_neutral > moderate:
            return "Moderate confidence"
        else:
            return "Low confidence"
    
    def _extract_stat_comparison(self, team1_stats: Dict[str, Any], team2_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Extract stat comparisons for display"""
        stats1 = team1_stats if team1_stats and team1_stats.get('data_source') != 'placeholder' else {}
        stats2 = team2_stats if team2_stats and team2_stats.get('data_source') != 'placeholder' else {}

        fb_sp = _fb.get("shooting_pct", 0.45)
        fb_rb = _fb.get("rebounding_avg", 42.0)
        fb_to = _fb.get("turnovers_avg", 14.0)
        fb_nr = _fb.get("net_rating_proxy", 0.0)

        return {
            'shooting_pct': {
                'team1': stats1.get('shooting_pct', fb_sp),
                'team2': stats2.get('shooting_pct', fb_sp),
                'advantage': 'team1' if stats1.get('shooting_pct', fb_sp) > stats2.get('shooting_pct', fb_sp) else 'team2'
            },
            'rebounding_avg': {
                'team1': stats1.get('rebounding_avg', fb_rb),
                'team2': stats2.get('rebounding_avg', fb_rb),
                'advantage': 'team1' if stats1.get('rebounding_avg', fb_rb) > stats2.get('rebounding_avg', fb_rb) else 'team2'
            },
            'turnovers_avg': {
                'team1': stats1.get('turnovers_avg', fb_to),
                'team2': stats2.get('turnovers_avg', fb_to),
                'advantage': 'team1' if stats1.get('turnovers_avg', fb_to) < stats2.get('turnovers_avg', fb_to) else 'team2'
            },
            'net_rating_proxy': {
                'team1': stats1.get('net_rating_proxy', fb_nr),
                'team2': stats2.get('net_rating_proxy', fb_nr),
                'advantage': 'team1' if stats1.get('net_rating_proxy', fb_nr) > stats2.get('net_rating_proxy', fb_nr) else 'team2'
            }
        }
    
    def _extract_sentiment_factors(self, team1_sentiment: str, team2_sentiment: str) -> Dict[str, Any]:
        """Extract sentiment factors for display"""
        sl = _scoring.get("sentiment_labels", {})

        def parse_sentiment(sentiment_str: str) -> Dict[str, Any]:
            if not sentiment_str or 'unavailable' in sentiment_str.lower():
                return {'score': 0.0, 'label': 'Neutral', 'positive_pct': 0, 'negative_pct': 0}
            
            import re
            score_match = re.search(r'compound score[:\s]+([-]?\d+\.?\d*)', sentiment_str.lower())
            pos_match = re.search(r'(\d+)% positive', sentiment_str.lower())
            neg_match = re.search(r'(\d+)% negative', sentiment_str.lower())
            
            score = float(score_match.group(1)) if score_match else 0.0
            pos_pct = int(pos_match.group(1)) if pos_match else 0
            neg_pct = int(neg_match.group(1)) if neg_match else 0
            
            if score > sl.get("very_positive", 0.3):
                label = 'Very Positive'
            elif score > sl.get("positive", 0.1):
                label = 'Positive'
            elif score < sl.get("very_negative", -0.3):
                label = 'Very Negative'
            elif score < sl.get("negative", -0.1):
                label = 'Negative'
            else:
                label = 'Neutral'
            
            return {'score': score, 'label': label, 'positive_pct': pos_pct, 'negative_pct': neg_pct}
        
        team1_sent = parse_sentiment(team1_sentiment)
        team2_sent = parse_sentiment(team2_sentiment)
        
        return {
            'team1': team1_sent,
            'team2': team2_sent,
            'advantage': 'team1' if team1_sent['score'] > team2_sent['score'] else 'team2'
        }
    
    def _extract_injury_factors(self, team1_injuries: Optional[list], team2_injuries: Optional[list]) -> Dict[str, Any]:
        """Extract injury factors for display"""
        inj_cfg = _scoring.get("injuries", {})
        sig_kw = inj_cfg.get("significant_keywords", ['out', 'injured', 'surgery', 'fracture', 'torn'])
        q_kw = inj_cfg.get("questionable_keywords", ['questionable', 'doubtful', 'probable'])

        def parse_injuries(injuries: Optional[list]) -> Dict[str, Any]:
            if not injuries:
                return {'count': 0, 'significant': 0, 'players': []}
            
            significant = []
            questionable = []
            
            for injury in injuries:
                injury_lower = str(injury).lower()
                if any(word in injury_lower for word in sig_kw):
                    significant.append(str(injury))
                elif any(word in injury_lower for word in q_kw):
                    questionable.append(str(injury))
            
            return {
                'count': len(injuries),
                'significant': len(significant),
                'questionable': len(questionable),
                'players': significant + questionable
            }
        
        team1_inj = parse_injuries(team1_injuries)
        team2_inj = parse_injuries(team2_injuries)
        
        return {
            'team1': team1_inj,
            'team2': team2_inj,
            'advantage': 'team1' if team1_inj['significant'] < team2_inj['significant'] else 'team2'
        }

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
        """Calculate complete matchup analysis"""
        team1_sentiment_tilt = self.calculate_sentiment_tilt(team1_sentiment)
        team2_sentiment_tilt = self.calculate_sentiment_tilt(team2_sentiment)
        
        team1_injuries_penalty = self.calculate_injuries_penalty(team1_injuries)
        team2_injuries_penalty = self.calculate_injuries_penalty(team2_injuries)
        
        team1_stats_score = self.calculate_stats_score(team1_stats)
        team2_stats_score = self.calculate_stats_score(team2_stats)
        team1_score = self.calculate_team_score(team1_stats, team1_sentiment_tilt, team1_injuries_penalty)
        team2_score = self.calculate_team_score(team2_stats, team2_sentiment_tilt, team2_injuries_penalty)
        
        win_probability = self.calculate_win_probability(team1_score, team2_score)
        predicted_winner = team1_name if win_probability > 0.5 else team2_name
        
        score_breakdown = self.generate_score_breakdown(team1_score, team2_score, team1_name, team2_name)
        confidence_label = self.generate_confidence_label(win_probability)
        
        stat_comparison = self._extract_stat_comparison(team1_stats, team2_stats)
        sentiment_factors = self._extract_sentiment_factors(team1_sentiment, team2_sentiment)
        injury_factors = self._extract_injury_factors(team1_injuries, team2_injuries)
        
        prediction_factors = {
            'stats': stat_comparison,
            'sentiment': sentiment_factors,
            'injuries': injury_factors,
            'score_breakdown': {
                'team1_base_score': round(team1_stats_score, 3),
                'team2_base_score': round(team2_stats_score, 3),
                'team1_sentiment_adjustment': round(team1_sentiment_tilt, 3),
                'team2_sentiment_adjustment': round(team2_sentiment_tilt, 3),
                'team1_injury_adjustment': round(team1_injuries_penalty, 3),
                'team2_injury_adjustment': round(team2_injuries_penalty, 3),
                'team1_final_score': round(team1_score, 3),
                'team2_final_score': round(team2_score, 3)
            }
        }
        
        return {
            'predicted_winner': predicted_winner,
            'win_probability': round(win_probability, 3),
            'score_breakdown': score_breakdown,
            'confidence_label': confidence_label,
            'team1_score': round(team1_score, 3),
            'team2_score': round(team2_score, 3),
            'prediction_factors': prediction_factors
        }
