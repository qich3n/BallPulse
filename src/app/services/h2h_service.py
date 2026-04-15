import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

import diskcache
import httpx


logger = logging.getLogger(__name__)


class HeadToHeadService:
    """Persistent cached H2H lookup with stale-while-revalidate."""

    def __init__(self, espn_provider, cache_cfg: Optional[Dict[str, Any]] = None):
        self.espn_provider = espn_provider
        cache_cfg = cache_cfg or {}
        self.h2h_ttl = cache_cfg.get("h2h_ttl", 3600)
        self.h2h_stale_ttl = cache_cfg.get("h2h_stale_ttl", 21600)
        self.refresh_lock_ttl = cache_cfg.get("h2h_refresh_lock_ttl", 30)
        self.scan_days = cache_cfg.get("h2h_scan_days", 120)
        self.cache_dir = cache_cfg.get("h2h_cache_dir", ".cache/h2h")
        self.cache = diskcache.Cache(self.cache_dir)

    def _canonical_team_pair(
        self,
        team1_name: str,
        team2_name: str,
        team1_id: Optional[str] = None,
        team2_id: Optional[str] = None,
    ) -> tuple[str, str]:
        one = f"id:{team1_id}" if team1_id else f"name:{team1_name.lower().strip()}"
        two = f"id:{team2_id}" if team2_id else f"name:{team2_name.lower().strip()}"
        return tuple(sorted([one, two]))

    def build_cache_key(
        self,
        team1_name: str,
        team2_name: str,
        limit: int,
        team1_id: Optional[str] = None,
        team2_id: Optional[str] = None,
    ) -> str:
        t1, t2 = self._canonical_team_pair(team1_name, team2_name, team1_id, team2_id)
        return f"h2h:nba:{t1}:{t2}:limit:{limit}"

    def _snapshot_is_fresh(self, snapshot: Dict[str, Any]) -> bool:
        fetched_at = snapshot.get("fetched_at")
        if not fetched_at:
            return False
        try:
            fetched_ts = datetime.fromisoformat(fetched_at).timestamp()
        except (TypeError, ValueError):
            return False
        return (time.time() - fetched_ts) < self.h2h_ttl

    @staticmethod
    def _resolve_team_match(
        query_name: str,
        query_abbrev: str,
        query_id: Optional[str],
        home_name: str,
        away_name: str,
        home_abbrev: str,
        away_abbrev: str,
        home_id: Optional[str],
        away_id: Optional[str],
    ) -> bool:
        if query_id and (query_id == home_id or query_id == away_id):
            return True
        return (
            query_name in home_name
            or query_name in away_name
            or (query_abbrev and (query_abbrev == home_abbrev or query_abbrev == away_abbrev))
        )

    def _compute_head_to_head(
        self,
        team1: str,
        team2: str,
        limit: int,
        team1_info: Optional[Dict[str, Any]] = None,
        team2_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        team1_lower = team1.lower()
        team2_lower = team2.lower()

        team1_name = team1_info.get("name", team1) if team1_info else team1
        team2_name = team2_info.get("name", team2) if team2_info else team2
        team1_abbrev = team1_info.get("abbreviation", "").lower() if team1_info else ""
        team2_abbrev = team2_info.get("abbreviation", "").lower() if team2_info else ""
        team1_id = str(team1_info.get("id")) if team1_info and team1_info.get("id") is not None else None
        team2_id = str(team2_info.get("id")) if team2_info and team2_info.get("id") is not None else None

        games: List[Dict[str, Any]] = []
        team1_wins = 0
        team2_wins = 0
        current_date = datetime.now()

        for days_back in range(self.scan_days):
            check_date = current_date - timedelta(days=days_back)
            date_str = check_date.strftime("%Y%m%d")
            try:
                scoreboard = self.espn_provider.get_scoreboard(date=date_str)
                for event in scoreboard.get("events", []):
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])
                    if len(competitors) < 2:
                        continue

                    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

                    home_team = home.get("team", {})
                    away_team = away.get("team", {})

                    home_name = home_team.get("displayName", "").lower()
                    away_name = away_team.get("displayName", "").lower()
                    home_abbrev = home_team.get("abbreviation", "").lower()
                    away_abbrev = away_team.get("abbreviation", "").lower()
                    home_id = str(home_team.get("id")) if home_team.get("id") is not None else None
                    away_id = str(away_team.get("id")) if away_team.get("id") is not None else None

                    team1_in_game = self._resolve_team_match(
                        team1_lower, team1_abbrev, team1_id,
                        home_name, away_name, home_abbrev, away_abbrev, home_id, away_id
                    )
                    team2_in_game = self._resolve_team_match(
                        team2_lower, team2_abbrev, team2_id,
                        home_name, away_name, home_abbrev, away_abbrev, home_id, away_id
                    )
                    if not (team1_in_game and team2_in_game):
                        continue

                    status = event.get("status", {}).get("type", {}).get("name", "")
                    if status != "STATUS_FINAL":
                        continue

                    home_score = int(home.get("score", 0))
                    away_score = int(away.get("score", 0))
                    home_display = home_team.get("displayName", "Unknown")
                    away_display = away_team.get("displayName", "Unknown")
                    winner = home_display if home_score > away_score else away_display

                    winner_lower = winner.lower()
                    if (
                        (team1_id and (winner_lower == home_name and home_id == team1_id))
                        or (team1_id and (winner_lower == away_name and away_id == team1_id))
                        or (team1_lower in winner_lower)
                        or (team1_abbrev and team1_abbrev in winner_lower)
                    ):
                        team1_wins += 1
                    else:
                        team2_wins += 1

                    games.append({
                        "game_id": event.get("id", ""),
                        "date": event.get("date", ""),
                        "season": event.get("season", {}).get("year"),
                        "home_team": home_display,
                        "away_team": away_display,
                        "home_score": home_score,
                        "away_score": away_score,
                        "winner": winner,
                        "venue": competition.get("venue", {}).get("fullName"),
                    })
                    if len(games) >= limit:
                        break
                if len(games) >= limit:
                    break
            except (httpx.HTTPError, ValueError, KeyError) as e:
                logger.debug("Error checking date %s for H2H: %s", date_str, e)
                continue

        games.sort(key=lambda g: g.get("date", ""), reverse=True)
        last_meeting = games[0] if games else None

        home_advantage = None
        if games:
            team1_home_wins = sum(1 for g in games if team1_lower in g["home_team"].lower() and team1_lower in g["winner"].lower())
            team2_home_wins = sum(1 for g in games if team2_lower in g["home_team"].lower() and team2_lower in g["winner"].lower())
            home_advantage = {
                "team1_home_record": f"{team1_home_wins} wins at home",
                "team2_home_record": f"{team2_home_wins} wins at home",
            }

        return {
            "team1": team1_name,
            "team2": team2_name,
            "total_games": len(games),
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "games": games[:limit],
            "last_meeting": last_meeting,
            "home_advantage": home_advantage,
        }

    async def _refresh_h2h_cache(
        self,
        cache_key: str,
        team1: str,
        team2: str,
        limit: int,
        team1_info: Optional[Dict[str, Any]],
        team2_info: Optional[Dict[str, Any]],
    ) -> None:
        lock_key = f"{cache_key}:lock"
        if not self.cache.add(lock_key, 1, expire=self.refresh_lock_ttl):
            return
        try:
            payload = await asyncio.to_thread(
                self._compute_head_to_head,
                team1,
                team2,
                limit,
                team1_info,
                team2_info,
            )
            snapshot = {"fetched_at": datetime.now().isoformat(), "payload": payload}
            self.cache.set(cache_key, snapshot, expire=self.h2h_stale_ttl)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Background H2H refresh failed for key=%s: %s", cache_key, e)
        finally:
            self.cache.delete(lock_key)

    async def get_head_to_head(self, team1: str, team2: str, limit: int) -> Dict[str, Any]:
        team1_info = await self.espn_provider.get_team_async(team1)
        team2_info = await self.espn_provider.get_team_async(team2)
        team1_id = str(team1_info.get("id")) if team1_info and team1_info.get("id") is not None else None
        team2_id = str(team2_info.get("id")) if team2_info and team2_info.get("id") is not None else None
        cache_key = self.build_cache_key(team1, team2, limit, team1_id, team2_id)

        snapshot = self.cache.get(cache_key)
        if snapshot and isinstance(snapshot, dict) and snapshot.get("payload"):
            if self._snapshot_is_fresh(snapshot):
                logger.info("H2H cache hit (fresh) for %s vs %s", team1, team2)
            else:
                logger.info("H2H cache hit (stale) for %s vs %s; refreshing in background", team1, team2)
                asyncio.create_task(self._refresh_h2h_cache(cache_key, team1, team2, limit, team1_info, team2_info))
            return snapshot["payload"]

        logger.info("H2H cache miss for %s vs %s", team1, team2)
        payload = await asyncio.to_thread(self._compute_head_to_head, team1, team2, limit, team1_info, team2_info)
        new_snapshot = {"fetched_at": datetime.now().isoformat(), "payload": payload}
        self.cache.set(cache_key, new_snapshot, expire=self.h2h_stale_ttl)
        return payload
