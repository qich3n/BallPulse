from unittest.mock import patch

from fastapi.testclient import TestClient

from src.app.main import app
from src.app.routes.teams import cache_service, _teams_stats_cache_key

client = TestClient(app)


def test_teams_list_without_stats():
    response = client.get("/teams")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert len(data["teams"]) == 30
    assert data["teams"][0]["stats"] is None


@patch("src.app.routes.teams.basketball_provider.get_team_stats_summary")
def test_teams_list_with_stats_uses_cache(mock_get_stats):
    cache_service.backend.delete(_teams_stats_cache_key)

    mock_get_stats.return_value = {
        "shooting_pct": 0.47,
        "rebounding_avg": 44.0,
        "turnovers_avg": 13.5,
        "net_rating_proxy": 2.1,
        "data_source": "test",
    }

    response1 = client.get("/teams?include_stats=true")
    assert response1.status_code == 200
    assert response1.json()["total"] == 30
    assert mock_get_stats.call_count == 30

    response2 = client.get("/teams?include_stats=true")
    assert response2.status_code == 200
    # Second request should be served from disk cache, not refetch stats
    assert mock_get_stats.call_count == 30
