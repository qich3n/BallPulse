from datetime import datetime, timedelta

from src.app.routes import games

# pylint: disable=protected-access


def test_h2h_cache_key_is_order_independent_with_team_ids():
    key1 = games._build_h2h_cache_key("Lakers", "Celtics", 10, "13", "2")
    key2 = games._build_h2h_cache_key("Celtics", "Lakers", 10, "2", "13")
    assert key1 == key2


def test_h2h_cache_key_is_order_independent_without_team_ids():
    key1 = games._build_h2h_cache_key("Los Angeles Lakers", "Boston Celtics", 5)
    key2 = games._build_h2h_cache_key("Boston Celtics", "Los Angeles Lakers", 5)
    assert key1 == key2


def test_h2h_snapshot_freshness_respects_ttl(monkeypatch):
    monkeypatch.setattr(games, "_H2H_CACHE_TTL", 60)

    fresh_snapshot = {
        "fetched_at": (datetime.now() - timedelta(seconds=30)).isoformat(),
        "payload": {"total_games": 1},
    }
    stale_snapshot = {
        "fetched_at": (datetime.now() - timedelta(seconds=120)).isoformat(),
        "payload": {"total_games": 1},
    }

    assert games._snapshot_is_fresh(fresh_snapshot) is True
    assert games._snapshot_is_fresh(stale_snapshot) is False
