import logging
import time
from typing import Dict, Any, Optional
from nba_api.stats.endpoints import teamgamelog, teamdashboardbygeneralsplits
from nba_api.stats.static import teams
from nba_api.stats.library.parameters import SeasonAll
from requests.exceptions import ReadTimeout, ConnectionError as RequestsConnectionError

logger = logging.getLogger(__name__)

# Browser-like headers required for stats.nba.com to accept requests from
# cloud/datacenter IPs (e.g. Render, Heroku). Without these, the NBA API
# returns a timeout or connection refused from non-residential IPs.
NBA_API_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

# stats.nba.com blocks cloud/datacenter IPs (Render, Heroku, AWS, etc.).
# Keep timeout short so requests fail fast and fall back to placeholder data
# instead of hanging the server for several minutes.
NBA_API_TIMEOUT = 8  # seconds — fail fast on Render
NBA_API_MAX_RETRIES = 1  # no retries; cloud IPs are blocked, not flaky
NBA_API_RETRY_BACKOFF = 1  # seconds base delay between retries

# Team name aliases for ESPN -> NBA API mapping
TEAM_NAME_ALIASES = {
    "la clippers": "los angeles clippers",
    "la lakers": "los angeles lakers",
    "ny knicks": "new york knicks",
    "philly": "philadelphia 76ers",
    "sixers": "philadelphia 76ers",
    "blazers": "portland trail blazers",
    "wolves": "minnesota timberwolves",
    "cavs": "cleveland cavaliers",
    "mavs": "dallas mavericks",
}


class BasketballProvider:
    """Provider for fetching basketball team statistics using nba_api"""
    
    def __init__(self):
        """Initialize the basketball provider"""
        self.logger = logging.getLogger(__name__)
        self._team_cache: Dict[str, Optional[int]] = {}
        self._espn_provider = None  # cached ESPNProvider instance (avoids repeated get_all_teams calls)
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name using aliases"""
        name_lower = team_name.lower()
        return TEAM_NAME_ALIASES.get(name_lower, name_lower)
    
    def _get_team_id(self, team_name: str) -> Optional[int]:
        """
        Get NBA team ID from team name
        
        Args:
            team_name: Name of the team
            
        Returns:
            Team ID or None if not found
        """
        # Check cache with original name first
        original_key = team_name.lower()
        if original_key in self._team_cache:
            return self._team_cache[original_key]
        
        # Normalize and check cache with normalized name
        normalized_name = self._normalize_team_name(team_name)
        cache_key = normalized_name
        if cache_key in self._team_cache:
            # Cache the original name too
            self._team_cache[original_key] = self._team_cache[cache_key]
            return self._team_cache[cache_key]
        
        try:
            nba_teams = teams.get_teams()
            # Try exact match first
            team = next(
                (t for t in nba_teams if t['full_name'].lower() == cache_key),
                None
            )
            
            # Try partial match (e.g., "Lakers" -> "Los Angeles Lakers")
            if not team:
                team = next(
                    (t for t in nba_teams if cache_key in t['full_name'].lower() or t['full_name'].lower() in cache_key),
                    None
                )
            
            # Try abbreviation match
            if not team:
                team = next(
                    (t for t in nba_teams if t['abbreviation'].lower() == cache_key),
                    None
                )
            
            team_id = team['id'] if team else None
            self._team_cache[cache_key] = team_id
            # Also cache the original name for faster future lookups
            original_key = team_name.lower()
            if original_key != cache_key:
                self._team_cache[original_key] = team_id
            
            if not team_id:
                self.logger.warning("Team '%s' not found in NBA teams", team_name)
            
            return team_id
            
        except (ValueError, KeyError, AttributeError) as e:
            self.logger.error("Error fetching team ID for '%s': %s", team_name, e)
            return None
    
    def _fetch_team_gamelog(self, team_id: int, season: str):
        """
        Fetch team game log with retry logic for transient network errors.
        
        Args:
            team_id: NBA team ID
            season: Season string (e.g., '2025-26')
            
        Returns:
            TeamGameLog object or raises the last exception
        """
        last_exc = None
        for attempt in range(1, NBA_API_MAX_RETRIES + 1):
            try:
                time.sleep(0.6)
                return teamgamelog.TeamGameLog(
                    team_id=team_id,
                    season=season,
                    headers=NBA_API_HEADERS,
                    timeout=NBA_API_TIMEOUT,
                )
            except (ReadTimeout, RequestsConnectionError) as e:
                last_exc = e
                wait = NBA_API_RETRY_BACKOFF * attempt
                self.logger.warning(
                    "Transient network error for team_id=%s season=%s (attempt %d/%d): %s. Retrying in %ds...",
                    team_id, season, attempt, NBA_API_MAX_RETRIES, e, wait
                )
                if attempt < NBA_API_MAX_RETRIES:
                    time.sleep(wait)
        raise last_exc

    def _fetch_team_dashboard(self, team_id: int, season: str):
        """
        Fetch team dashboard stats with retry logic for transient network errors.

        Args:
            team_id: NBA team ID
            season: Season string (e.g., '2025-26')

        Returns:
            TeamDashboardByGeneralSplits object or raises the last exception
        """
        last_exc = None
        for attempt in range(1, NBA_API_MAX_RETRIES + 1):
            try:
                time.sleep(0.6)
                return teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
                    team_id=team_id,
                    season=season,
                    headers=NBA_API_HEADERS,
                    timeout=NBA_API_TIMEOUT,
                )
            except (ReadTimeout, RequestsConnectionError) as e:
                last_exc = e
                wait = NBA_API_RETRY_BACKOFF * attempt
                self.logger.warning(
                    "Transient network error for team_id=%s season=%s (attempt %d/%d): %s. Retrying in %ds...",
                    team_id, season, attempt, NBA_API_MAX_RETRIES, e, wait
                )
                if attempt < NBA_API_MAX_RETRIES:
                    time.sleep(wait)
        raise last_exc

    def get_placeholder_stats(self, team_name: str) -> Dict[str, Any]:
        """
        Return placeholder stats when API fetch fails
        
        Args:
            team_name: Name of the team
            
        Returns:
            Dictionary with placeholder stats
        """
        return {
            "last_10_games": 10,
            "shooting_pct": 0.450,
            "rebounding_avg": 42.0,
            "turnovers_avg": 14.0,
            "net_rating_proxy": 0.0,
            "team_name": team_name,
            "data_source": "placeholder"
        }
    
    def get_team_stats_summary(self, team_name: str) -> Dict[str, Any]:
        """
        Get normalized stats summary for a team.

        Strategy (in order):
          1. ESPN – works from any IP including Render/cloud (preferred).
          2. NBA API – works locally but stats.nba.com blocks cloud IPs,
             so this is kept as a secondary fallback with a short timeout.
          3. Placeholder – safe defaults so the app never crashes.

        Returns:
            Dict with keys: last_10_games, shooting_pct, rebounding_avg,
            turnovers_avg, net_rating_proxy, team_name, data_source
        """
        # -------------------------------------------------------------------
        # 1. Try ESPN (primary – works on Render)
        # -------------------------------------------------------------------
        try:
            from .espn_provider import ESPNProvider, Sport, League
            # Reuse a single ESPNProvider instance so _team_cache and
            # _teams_list persist across repeated calls (avoids refetching
            # the full team list for every team).
            if self._espn_provider is None:
                self._espn_provider = ESPNProvider(
                    sport=Sport.BASKETBALL, league=League.NBA, timeout=10.0
                )
            espn = self._espn_provider
            espn_stats = espn.get_team_stats_summary(team_name)
            if espn_stats:
                self.logger.info("ESPN stats fetched successfully for '%s'", team_name)
                espn_stats["last_10_games"] = 10  # ESPN gives season averages, not last-10
                return espn_stats
            else:
                self.logger.warning("ESPN returned no stats for '%s', trying NBA API", team_name)
        except Exception as e:
            self.logger.warning("ESPN stats fetch failed for '%s': %s – trying NBA API", team_name, e)

        # -------------------------------------------------------------------
        # 2. NBA API fallback (works locally; fast-fails on Render)
        # -------------------------------------------------------------------
        team_id = self._get_team_id(team_name)
        if not team_id:
            self.logger.warning("Team ID not found for '%s', using placeholder", team_name)
            return self.get_placeholder_stats(team_name)

        try:
            season = SeasonAll.current_season
            self.logger.debug("Fetching NBA API stats for team_id=%s, season=%s", team_id, season)
            try:
                gamelog = self._fetch_team_gamelog(team_id, season)
                games_df = gamelog.get_data_frames()[0]
            except (ReadTimeout, RequestsConnectionError) as api_error:
                self.logger.warning(
                    "NBA API timeout for '%s' (likely running on cloud): %s. Using placeholder.",
                    team_name, api_error
                )
                return self.get_placeholder_stats(team_name)
            except (ValueError, KeyError, AttributeError):
                games_df = None

            # Try previous season if current is empty
            if games_df is None or games_df.empty:
                year = int(season.split("-")[0])
                for prev_season in [f"{year-1}-{str(year)[2:]}", f"{year-2}-{str(year-1)[2:]}"]:
                    try:
                        prev_gl = self._fetch_team_gamelog(team_id, prev_season)
                        prev_df = prev_gl.get_data_frames()[0]
                        if prev_df is not None and not prev_df.empty:
                            games_df = prev_df
                            season = prev_season
                            break
                    except (ReadTimeout, RequestsConnectionError) as timeout_err:
                        # stats.nba.com is blocked on cloud; bail out immediately
                        self.logger.warning(
                            "NBA API timeout on prev season '%s' – returning placeholder: %s",
                            prev_season, timeout_err
                        )
                        return self.get_placeholder_stats(team_name)
                    except Exception:
                        continue

            if games_df is None or games_df.empty:
                self.logger.warning("No NBA API data for '%s' after all seasons. Using placeholder.", team_name)
                return self.get_placeholder_stats(team_name)

            recent = games_df.head(10)
            num_games = len(recent)

            shooting_pct = float(recent["FG_PCT"].mean()) if "FG_PCT" in recent.columns else 0.450
            rebounding_avg = float(recent["REB"].mean()) if "REB" in recent.columns else 42.0
            turnovers_avg = float(recent["TOV"].mean()) if "TOV" in recent.columns else 14.0
            if "PLUS_MINUS" in recent.columns:
                net_rating_proxy = float(recent["PLUS_MINUS"].mean())
            elif "PTS" in recent.columns:
                net_rating_proxy = float(recent["PTS"].mean()) - 108.0
            else:
                net_rating_proxy = 0.0

            # Replace NaN with defaults
            def _safe(val: float, default: float) -> float:
                return val if val == val else default

            return {
                "last_10_games": num_games,
                "shooting_pct": round(_safe(shooting_pct, 0.450), 3),
                "rebounding_avg": round(_safe(rebounding_avg, 42.0), 1),
                "turnovers_avg": round(_safe(turnovers_avg, 14.0), 1),
                "net_rating_proxy": round(_safe(net_rating_proxy, 0.0), 1),
                "team_name": team_name,
                "data_source": "nba_api",
            }

        except Exception as e:
            self.logger.error("Error fetching NBA API stats for '%s': %s", team_name, e, exc_info=True)
            return self.get_placeholder_stats(team_name)

