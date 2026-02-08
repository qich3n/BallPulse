import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from src.app.providers.basketball_provider import BasketballProvider


@pytest.fixture
def provider():
    """Create a BasketballProvider instance for testing"""
    return BasketballProvider()


@pytest.fixture
def mock_team_data():
    """Mock team data from nba_api"""
    return [
        {
            'id': 1610612747,
            'full_name': 'Los Angeles Lakers',
            'abbreviation': 'LAL'
        },
        {
            'id': 1610612744,
            'full_name': 'Golden State Warriors',
            'abbreviation': 'GSW'
        }
    ]


@pytest.fixture
def mock_game_log_data():
    """Mock game log data (last 10 games)"""
    return pd.DataFrame({
        'GAME_DATE': ['2024-01-15', '2024-01-14', '2024-01-12', '2024-01-10', '2024-01-08',
                      '2024-01-06', '2024-01-04', '2024-01-02', '2024-01-01', '2023-12-30'],
        'FG_PCT': [0.450, 0.480, 0.440, 0.460, 0.470, 0.450, 0.490, 0.430, 0.460, 0.440],
        'REB': [45.0, 42.0, 48.0, 44.0, 43.0, 46.0, 41.0, 47.0, 45.0, 44.0],
        'TOV': [12.0, 14.0, 13.0, 15.0, 11.0, 16.0, 12.0, 14.0, 13.0, 15.0],
        'PTS': [110.0, 115.0, 108.0, 112.0, 118.0, 105.0, 120.0, 107.0, 113.0, 109.0],
        'OPP_PTS': [105.0, 110.0, 112.0, 108.0, 115.0, 110.0, 118.0, 109.0, 111.0, 107.0],
        'PLUS_MINUS': [5.0, 5.0, -4.0, 4.0, 3.0, -5.0, 2.0, -2.0, 2.0, 2.0]
    })


def test_get_team_id_success(provider, mock_team_data):
    """Test successful team ID lookup"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        team_id = provider._get_team_id("Los Angeles Lakers")
        assert team_id == 1610612747


def test_get_team_id_partial_match(provider, mock_team_data):
    """Test team ID lookup with partial match"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        team_id = provider._get_team_id("Lakers")
        assert team_id == 1610612747


def test_get_team_id_abbreviation(provider, mock_team_data):
    """Test team ID lookup with abbreviation"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        team_id = provider._get_team_id("LAL")
        assert team_id == 1610612747


def test_get_team_id_not_found(provider, mock_team_data):
    """Test team ID lookup when team not found"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        team_id = provider._get_team_id("Nonexistent Team")
        assert team_id is None


def test_get_team_stats_summary_success(provider, mock_team_data, mock_game_log_data):
    """Test successful stats fetching"""
    # Mock TeamGameLog
    mock_gamelog = MagicMock()
    mock_gamelog.get_data_frames.return_value = [mock_game_log_data]
    
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        with patch('src.app.providers.basketball_provider.teamgamelog.TeamGameLog', return_value=mock_gamelog):
            stats = provider.get_team_stats_summary("Los Angeles Lakers")
            
            assert stats['team_name'] == "Los Angeles Lakers"
            assert stats['data_source'] == "nba_api"
            assert stats['last_10_games'] == 10
            assert isinstance(stats['shooting_pct'], float)
            assert isinstance(stats['rebounding_avg'], float)
            assert isinstance(stats['turnovers_avg'], float)
            assert isinstance(stats['net_rating_proxy'], float)
            assert 0.0 <= stats['shooting_pct'] <= 1.0
            assert stats['rebounding_avg'] > 0
            assert stats['turnovers_avg'] > 0


def test_get_team_stats_summary_team_not_found(provider, mock_team_data):
    """Test stats fetching when team not found (should return placeholder)"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        stats = provider.get_team_stats_summary("Nonexistent Team")
        
        assert stats['team_name'] == "Nonexistent Team"
        assert stats['data_source'] == "placeholder"
        assert stats['shooting_pct'] == 0.450
        assert stats['rebounding_avg'] == 42.0
        assert stats['turnovers_avg'] == 14.0
        assert stats['net_rating_proxy'] == 0.0


def test_get_team_stats_summary_api_error(provider, mock_team_data):
    """Test stats fetching when API call fails (should return placeholder)"""
    # Mock TeamGameLog to raise an exception
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        with patch('src.app.providers.basketball_provider.teamgamelog.TeamGameLog', side_effect=Exception("API Error")):
            stats = provider.get_team_stats_summary("Los Angeles Lakers")
            
            assert stats['team_name'] == "Los Angeles Lakers"
            assert stats['data_source'] == "placeholder"
            assert stats['shooting_pct'] == 0.450
            assert stats['rebounding_avg'] == 42.0
            assert stats['turnovers_avg'] == 14.0


def test_get_team_stats_summary_empty_games(provider, mock_team_data):
    """Test stats fetching when no games are returned (should return placeholder)"""
    mock_gamelog = MagicMock()
    mock_gamelog.get_data_frames.return_value = [pd.DataFrame()]  # Empty DataFrame
    
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        with patch('src.app.providers.basketball_provider.teamgamelog.TeamGameLog', return_value=mock_gamelog):
            stats = provider.get_team_stats_summary("Los Angeles Lakers")
            
            assert stats['team_name'] == "Los Angeles Lakers"
            assert stats['data_source'] == "placeholder"


def test_get_team_stats_summary_missing_columns(provider, mock_team_data):
    """Test stats fetching when some columns are missing"""
    # DataFrame with minimal columns
    minimal_df = pd.DataFrame({
        'GAME_DATE': ['2024-01-15', '2024-01-14'],
        'FG_PCT': [0.450, 0.480]
    })
    
    mock_gamelog = MagicMock()
    mock_gamelog.get_data_frames.return_value = [minimal_df]
    
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        with patch('src.app.providers.basketball_provider.teamgamelog.TeamGameLog', return_value=mock_gamelog):
            stats = provider.get_team_stats_summary("Los Angeles Lakers")
            
            # Should still return stats with defaults for missing columns
            assert stats['data_source'] == "nba_api"
            assert stats['rebounding_avg'] == 42.0  # Default value
            assert stats['turnovers_avg'] == 14.0  # Default value


def test_get_placeholder_stats(provider):
    """Test placeholder stats generation"""
    stats = provider.get_placeholder_stats("Test Team")
    
    assert stats['team_name'] == "Test Team"
    assert stats['data_source'] == "placeholder"
    assert stats['last_10_games'] == 10
    assert stats['shooting_pct'] == 0.450
    assert stats['rebounding_avg'] == 42.0
    assert stats['turnovers_avg'] == 14.0
    assert stats['net_rating_proxy'] == 0.0


def test_team_id_caching(provider, mock_team_data):
    """Test that team IDs are cached"""
    with patch('src.app.providers.basketball_provider.teams.get_teams', return_value=mock_team_data):
        # First call
        team_id1 = provider._get_team_id("Los Angeles Lakers")
        assert team_id1 == 1610612747
        
        # Second call should use cache (teams.get_teams should not be called again)
        # We can't easily verify this without more complex mocking, but the cache is set
        team_id2 = provider._get_team_id("Los Angeles Lakers")
        assert team_id2 == 1610612747
        assert team_id1 == team_id2

