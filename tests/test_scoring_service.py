import pytest
from src.app.services.scoring_service import ScoringService


@pytest.fixture
def scoring_service():
    """Create a ScoringService instance for testing"""
    return ScoringService()


@pytest.fixture
def sample_stats():
    """Sample team stats for testing"""
    return {
        'shooting_pct': 0.465,
        'rebounding_avg': 44.5,
        'turnovers_avg': 13.2,
        'net_rating_proxy': 4.2,
        'team_name': 'Lakers',
        'data_source': 'nba_api'
    }


@pytest.fixture
def placeholder_stats():
    """Placeholder stats for testing"""
    return {
        'shooting_pct': 0.450,
        'rebounding_avg': 42.0,
        'turnovers_avg': 14.0,
        'net_rating_proxy': 0.0,
        'team_name': 'Team',
        'data_source': 'placeholder'
    }


def test_sigmoid(scoring_service):
    """Test sigmoid function"""
    # Test midpoint
    result = scoring_service._sigmoid(0.0, midpoint=0.0)
    assert abs(result - 0.5) < 0.01
    
    # Test positive value
    result_pos = scoring_service._sigmoid(1.0, midpoint=0.0)
    assert result_pos > 0.5
    
    # Test negative value
    result_neg = scoring_service._sigmoid(-1.0, midpoint=0.0)
    assert result_neg < 0.5


def test_normalize_stat(scoring_service):
    """Test stat normalization"""
    # Test middle value
    result = scoring_service._normalize_stat(50.0, 0.0, 100.0)
    assert abs(result - 0.5) < 0.01
    
    # Test min value
    result_min = scoring_service._normalize_stat(0.0, 0.0, 100.0)
    assert abs(result_min - 0.0) < 0.01
    
    # Test max value
    result_max = scoring_service._normalize_stat(100.0, 0.0, 100.0)
    assert abs(result_max - 1.0) < 0.01


def test_calculate_stats_score(scoring_service, sample_stats):
    """Test stats score calculation"""
    score = scoring_service.calculate_stats_score(sample_stats)
    
    assert 0.0 <= score <= 1.0
    assert isinstance(score, float)


def test_calculate_stats_score_placeholder(scoring_service, placeholder_stats):
    """Test stats score with placeholder data"""
    score = scoring_service.calculate_stats_score(placeholder_stats)
    assert score == 0.5  # Should return neutral score


def test_calculate_sentiment_tilt(scoring_service):
    """Test sentiment tilt calculation"""
    # Positive sentiment
    positive_summary = "Overall sentiment is very positive. Great performance!"
    tilt_pos = scoring_service.calculate_sentiment_tilt(positive_summary)
    assert tilt_pos > 0
    assert -0.2 <= tilt_pos <= 0.2
    
    # Negative sentiment
    negative_summary = "Overall sentiment is negative. Concerns about performance."
    tilt_neg = scoring_service.calculate_sentiment_tilt(negative_summary)
    assert tilt_neg < 0
    assert -0.2 <= tilt_neg <= 0.2
    
    # Empty sentiment
    tilt_empty = scoring_service.calculate_sentiment_tilt("")
    assert tilt_empty == 0.0


def test_calculate_injuries_penalty(scoring_service):
    """Test injuries penalty calculation"""
    # No injuries
    penalty_none = scoring_service.calculate_injuries_penalty(None)
    assert penalty_none == 0.0
    
    penalty_empty = scoring_service.calculate_injuries_penalty([])
    assert penalty_empty == 0.0
    
    # One significant injury
    injuries_one = ["Player X - out"]
    penalty_one = scoring_service.calculate_injuries_penalty(injuries_one)
    assert penalty_one < 0
    assert -0.15 <= penalty_one <= 0.0
    
    # Multiple injuries
    injuries_multi = ["Player X - out", "Player Y - injured", "Player Z - surgery"]
    penalty_multi = scoring_service.calculate_injuries_penalty(injuries_multi)
    assert penalty_multi <= -0.05
    assert penalty_multi >= -0.15


def test_calculate_team_score(scoring_service, sample_stats):
    """Test team score calculation"""
    score = scoring_service.calculate_team_score(sample_stats)
    
    assert 0.0 <= score <= 1.0
    assert isinstance(score, float)
    
    # Test with adjustments
    score_with_tilt = scoring_service.calculate_team_score(
        sample_stats,
        sentiment_tilt=0.1,
        injuries_penalty=-0.05
    )
    assert 0.0 <= score_with_tilt <= 1.0


def test_calculate_win_probability(scoring_service):
    """Test win probability calculation"""
    # Team 1 stronger
    prob = scoring_service.calculate_win_probability(0.7, 0.5)
    assert 0.5 < prob <= 1.0
    
    # Team 2 stronger
    prob2 = scoring_service.calculate_win_probability(0.5, 0.7)
    assert 0.0 <= prob2 < 0.5
    
    # Equal teams
    prob_equal = scoring_service.calculate_win_probability(0.5, 0.5)
    assert abs(prob_equal - 0.5) < 0.1


def test_generate_score_breakdown(scoring_service):
    """Test score breakdown generation"""
    breakdown = scoring_service.generate_score_breakdown(0.6, 0.4, "Lakers", "Warriors")
    
    assert isinstance(breakdown, str)
    assert "Lakers" in breakdown
    assert "Warriors" in breakdown
    assert "Predicted final score" in breakdown


def test_generate_confidence_label(scoring_service):
    """Test confidence label generation"""
    # High confidence
    label_high = scoring_service.generate_confidence_label(0.85)
    assert "High" in label_high
    
    label_high_neg = scoring_service.generate_confidence_label(0.15)
    assert "High" in label_high_neg
    
    # Moderate confidence
    label_mod = scoring_service.generate_confidence_label(0.65)
    assert "Moderate" in label_mod or "High" in label_mod
    
    # Low confidence
    label_low = scoring_service.generate_confidence_label(0.52)
    assert "Low" in label_low


def test_calculate_matchup(scoring_service, sample_stats):
    """Test complete matchup calculation"""
    team1_stats = sample_stats
    team2_stats = {
        'shooting_pct': 0.450,
        'rebounding_avg': 42.0,
        'turnovers_avg': 14.5,
        'net_rating_proxy': -1.0,
        'team_name': 'Warriors',
        'data_source': 'nba_api'
    }
    
    result = scoring_service.calculate_matchup(
        team1_name="Lakers",
        team2_name="Warriors",
        team1_stats=team1_stats,
        team2_stats=team2_stats,
        team1_sentiment="Very positive sentiment",
        team2_sentiment="Neutral sentiment",
        team1_injuries=None,
        team2_injuries=["Player X - out"]
    )
    
    assert isinstance(result, dict)
    assert 'predicted_winner' in result
    assert 'win_probability' in result
    assert 'score_breakdown' in result
    assert 'confidence_label' in result
    
    assert result['predicted_winner'] in ["Lakers", "Warriors"]
    assert 0.0 <= result['win_probability'] <= 1.0
    assert isinstance(result['score_breakdown'], str)
    assert isinstance(result['confidence_label'], str)

