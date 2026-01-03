import pytest
import tempfile
import shutil
import os
from src.app.services.cache_service import CacheService
from src.app.routes.compare import CompareRequest, CompareResponse, TeamAnalysis, MatchupAnalysis, Sources, Context


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing"""
    cache_dir = tempfile.mkdtemp(prefix="test_cache_")
    yield cache_dir
    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.fixture
def cache_service(temp_cache_dir):
    """Create a cache service instance for testing"""
    return CacheService(cache_dir=temp_cache_dir, default_ttl=60)


def test_cache_miss(cache_service):
    """Test cache miss behavior"""
    # Attempt to get a value that doesn't exist
    result = cache_service.get("basketball", "Lakers", "Warriors", date="2024-01-15")
    assert result is None


def test_cache_set_and_get(cache_service):
    """Test setting and getting a value from cache"""
    test_value = {"test": "data"}
    
    # Set value
    cache_service.set("basketball", "Lakers", "Warriors", test_value, date="2024-01-15")
    
    # Get value
    result = cache_service.get("basketball", "Lakers", "Warriors", date="2024-01-15")
    assert result == test_value


def test_cache_key_normalization(cache_service):
    """Test that cache keys are normalized (team order doesn't matter)"""
    test_value = {"test": "data"}
    
    # Set with team1, team2
    cache_service.set("basketball", "Lakers", "Warriors", test_value, date="2024-01-15")
    
    # Get with team2, team1 (reversed order)
    result = cache_service.get("basketball", "Warriors", "Lakers", date="2024-01-15")
    assert result == test_value


def test_cache_without_date(cache_service):
    """Test cache with and without date"""
    test_value1 = {"test": "data1"}
    test_value2 = {"test": "data2"}
    
    # Set with date
    cache_service.set("basketball", "Lakers", "Warriors", test_value1, date="2024-01-15")
    
    # Set without date (different key)
    cache_service.set("basketball", "Lakers", "Warriors", test_value2)
    
    # Get with date
    result1 = cache_service.get("basketball", "Lakers", "Warriors", date="2024-01-15")
    assert result1 == test_value1
    
    # Get without date
    result2 = cache_service.get("basketball", "Lakers", "Warriors")
    assert result2 == test_value2


def test_cache_delete(cache_service):
    """Test cache deletion"""
    test_value = {"test": "data"}
    
    # Set value
    cache_service.set("basketball", "Lakers", "Warriors", test_value)
    
    # Verify it exists
    assert cache_service.get("basketball", "Lakers", "Warriors") == test_value
    
    # Delete it
    cache_service.delete("basketball", "Lakers", "Warriors")
    
    # Verify it's gone
    assert cache_service.get("basketball", "Lakers", "Warriors") is None


def test_cache_ttl_expiration(cache_service):
    """Test that cache entries expire after TTL"""
    test_value = {"test": "data"}
    
    # Set with very short TTL (1 second)
    cache_service.set("basketball", "Lakers", "Warriors", test_value, ttl=1)
    
    # Should be available immediately
    assert cache_service.get("basketball", "Lakers", "Warriors") == test_value
    
    # Wait for expiration
    import time
    time.sleep(2)
    
    # Should be expired
    assert cache_service.get("basketball", "Lakers", "Warriors") is None


def test_cache_with_pydantic_model(cache_service):
    """Test caching Pydantic models"""
    # Create a CompareResponse object
    response = CompareResponse(
        team1=TeamAnalysis(
            pros=["Test pros"],
            cons=["Test cons"],
            stats_summary="Test stats",
            sentiment_summary="Test sentiment"
        ),
        team2=TeamAnalysis(
            pros=["Test pros 2"],
            cons=["Test cons 2"],
            stats_summary="Test stats 2",
            sentiment_summary="Test sentiment 2"
        ),
        matchup=MatchupAnalysis(
            predicted_winner="Lakers",
            win_probability=0.65,
            score_breakdown="115-110",
            confidence_label="High"
        ),
        sources=Sources(
            reddit=["http://example.com/reddit"],
            stats=["http://example.com/stats"]
        )
    )
    
    # Cache the response
    cache_service.set("basketball", "Lakers", "Warriors", response, date="2024-01-15")
    
    # Retrieve it
    cached = cache_service.get("basketball", "Lakers", "Warriors", date="2024-01-15")
    
    assert cached is not None
    assert isinstance(cached, CompareResponse)
    assert cached.team1.stats_summary == "Test stats"
    assert cached.matchup.predicted_winner == "Lakers"
    assert cached.matchup.win_probability == 0.65

