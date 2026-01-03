import pytest
from src.app.services.proscons_service import ProsConsService


@pytest.fixture
def proscons_service():
    """Create a ProsConsService instance for testing"""
    return ProsConsService()


@pytest.fixture
def sample_stats():
    """Sample team stats for testing"""
    return {
        'shooting_pct': 0.480,
        'rebounding_avg': 46.0,
        'turnovers_avg': 12.0,
        'net_rating_proxy': 6.5,
        'team_name': 'Lakers',
        'data_source': 'nba_api'
    }


@pytest.fixture
def poor_stats():
    """Poor team stats for testing"""
    return {
        'shooting_pct': 0.420,
        'rebounding_avg': 38.0,
        'turnovers_avg': 17.0,
        'net_rating_proxy': -4.0,
        'team_name': 'Team',
        'data_source': 'nba_api'
    }


def test_generate_pros_from_stats(proscons_service, sample_stats):
    """Test pros generation from stats"""
    pros = proscons_service._generate_pros_from_stats(sample_stats)
    
    assert isinstance(pros, list)
    assert len(pros) > 0
    assert all(isinstance(pro, str) for pro in pros)


def test_generate_cons_from_stats(proscons_service, poor_stats):
    """Test cons generation from stats"""
    cons = proscons_service._generate_cons_from_stats(poor_stats)
    
    assert isinstance(cons, list)
    assert len(cons) > 0
    assert all(isinstance(con, str) for con in cons)


def test_generate_pros_from_sentiment(proscons_service):
    """Test pros generation from sentiment"""
    positive_sentiment = "Overall sentiment is very positive. Great performance and high confidence!"
    pros = proscons_service._generate_pros_from_sentiment(positive_sentiment)
    
    assert isinstance(pros, list)
    
    empty_pros = proscons_service._generate_pros_from_sentiment("")
    assert empty_pros == []


def test_generate_cons_from_sentiment(proscons_service):
    """Test cons generation from sentiment"""
    negative_sentiment = "Overall sentiment is negative. Concerns about performance and worries about the future."
    cons = proscons_service._generate_cons_from_sentiment(negative_sentiment)
    
    assert isinstance(cons, list)
    
    empty_cons = proscons_service._generate_cons_from_sentiment("")
    assert empty_cons == []


def test_generate_pros_from_injuries(proscons_service):
    """Test pros generation from injuries (healthy roster)"""
    # No injuries
    pros_none = proscons_service._generate_pros_from_injuries(None)
    assert len(pros_none) > 0
    assert any('full' in pro.lower() or 'healthy' in pro.lower() for pro in pros_none)
    
    pros_empty = proscons_service._generate_pros_from_injuries([])
    assert len(pros_empty) > 0


def test_generate_cons_from_injuries(proscons_service):
    """Test cons generation from injuries"""
    # No injuries
    cons_none = proscons_service._generate_cons_from_injuries(None)
    assert cons_none == []
    
    # One injury
    injuries_one = ["Player X - out"]
    cons_one = proscons_service._generate_cons_from_injuries(injuries_one)
    assert len(cons_one) > 0
    assert "Player X" in cons_one[0] or "injury" in cons_one[0].lower()
    
    # Multiple injuries
    injuries_multi = ["Player X - out", "Player Y - injured"]
    cons_multi = proscons_service._generate_cons_from_injuries(injuries_multi)
    assert len(cons_multi) > 0


def test_generate_pros_cons(proscons_service, sample_stats):
    """Test complete pros/cons generation"""
    result = proscons_service.generate_pros_cons(
        stats=sample_stats,
        sentiment_summary="Very positive sentiment with great performance!",
        injuries=None
    )
    
    assert isinstance(result, dict)
    assert 'pros' in result
    assert 'cons' in result
    assert isinstance(result['pros'], list)
    assert isinstance(result['cons'], list)
    
    # Should have at least minimum pros/cons
    assert len(result['pros']) >= 3
    assert len(result['cons']) >= 3
    assert len(result['pros']) <= 5
    assert len(result['cons']) <= 5


def test_generate_pros_cons_with_injuries(proscons_service, sample_stats):
    """Test pros/cons generation with injuries"""
    result = proscons_service.generate_pros_cons(
        stats=sample_stats,
        sentiment_summary="Positive sentiment",
        injuries=["Player X - out", "Player Y - injured"]
    )
    
    assert isinstance(result, dict)
    assert 'pros' in result
    assert 'cons' in result
    
    # Should have injury-related cons
    cons_text = ' '.join(result['cons']).lower()
    assert any(word in cons_text for word in ['injury', 'injured', 'player'])


def test_generate_pros_cons_placeholder_stats(proscons_service):
    """Test pros/cons generation with placeholder stats"""
    placeholder_stats = {
        'data_source': 'placeholder'
    }
    
    result = proscons_service.generate_pros_cons(
        stats=placeholder_stats,
        sentiment_summary="",
        injuries=None
    )
    
    assert isinstance(result, dict)
    assert 'pros' in result
    assert 'cons' in result
    # Should still generate pros/cons (generic ones)
    assert len(result['pros']) >= 3
    assert len(result['cons']) >= 3


def test_generate_pros_cons_empty_data(proscons_service):
    """Test pros/cons generation with empty data"""
    result = proscons_service.generate_pros_cons(
        stats={},
        sentiment_summary="",
        injuries=None
    )
    
    assert isinstance(result, dict)
    assert 'pros' in result
    assert 'cons' in result
    # Should generate generic pros/cons
    assert len(result['pros']) >= 3
    assert len(result['cons']) >= 3


def test_generate_pros_cons_custom_limits(proscons_service, sample_stats):
    """Test pros/cons generation with custom limits"""
    result = proscons_service.generate_pros_cons(
        stats=sample_stats,
        sentiment_summary="Positive sentiment",
        injuries=None,
        min_pros=2,
        max_pros=3,
        min_cons=2,
        max_cons=3
    )
    
    assert len(result['pros']) <= 3
    assert len(result['cons']) <= 3
    assert len(result['pros']) >= 2
    assert len(result['cons']) >= 2

