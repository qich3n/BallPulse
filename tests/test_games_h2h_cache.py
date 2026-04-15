from datetime import datetime, timedelta

from src.app.services.h2h_service import HeadToHeadService

# pylint: disable=protected-access


class _DummyEspnProvider:
    def get_scoreboard(self, date=None):
        _ = date
        return {"events": []}

    async def get_team_async(self, team_identifier):
        _ = team_identifier
        return None


def _new_service():
    return HeadToHeadService(_DummyEspnProvider(), {"h2h_ttl": 60})


def test_h2h_cache_key_is_order_independent_with_team_ids():
    service = _new_service()
    key1 = service.build_cache_key("Lakers", "Celtics", 10, "13", "2")
    key2 = service.build_cache_key("Celtics", "Lakers", 10, "2", "13")
    assert key1 == key2


def test_h2h_cache_key_is_order_independent_without_team_ids():
    service = _new_service()
    key1 = service.build_cache_key("Los Angeles Lakers", "Boston Celtics", 5)
    key2 = service.build_cache_key("Boston Celtics", "Los Angeles Lakers", 5)
    assert key1 == key2


def test_h2h_snapshot_freshness_respects_ttl():
    service = _new_service()
    fresh_snapshot = {
        "fetched_at": (datetime.now() - timedelta(seconds=30)).isoformat(),
        "payload": {"total_games": 1},
    }
    stale_snapshot = {
        "fetched_at": (datetime.now() - timedelta(seconds=120)).isoformat(),
        "payload": {"total_games": 1},
    }

    assert service._snapshot_is_fresh(fresh_snapshot) is True
    assert service._snapshot_is_fresh(stale_snapshot) is False
