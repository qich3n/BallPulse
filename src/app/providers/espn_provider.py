"""
ESPN Provider - Full Implementation

This module provides integration with ESPN's hidden/unofficial API.
Endpoints discovered via: https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b

Supports multiple sports and leagues:
- NBA, WNBA, Men's/Women's College Basketball
- NFL, College Football
- MLB, NHL, Soccer (various leagues)

Note: This is an unofficial API and may be subject to rate limiting or changes.
Use responsibly and respect ESPN's terms of service.
"""

import logging
import httpx
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class Sport(Enum):
    """Supported sports"""
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    SOCCER = "soccer"


class League(Enum):
    """Supported leagues"""
    # Basketball
    NBA = "nba"
    WNBA = "wnba"
    MENS_COLLEGE_BASKETBALL = "mens-college-basketball"
    WOMENS_COLLEGE_BASKETBALL = "womens-college-basketball"
    # Football
    NFL = "nfl"
    COLLEGE_FOOTBALL = "college-football"
    # Baseball
    MLB = "mlb"
    # Hockey
    NHL = "nhl"
    # Soccer (use league codes like 'eng.1' for EPL, 'usa.1' for MLS)


class ESPNProvider:
    """
    Provider for fetching sports data from ESPN's unofficial API.
    
    Supports multiple sports and leagues with endpoints for:
    - Scoreboard (live scores)
    - News
    - Teams (list and individual)
    - Injuries
    - Standings
    - Game summaries
    - Rankings (college sports)
    
    WARNING: This is an unofficial API. Use at your own risk and respect rate limits.
    """
    
    def __init__(
        self, 
        sport: Sport = Sport.BASKETBALL, 
        league: League = League.NBA,
        timeout: float = 10.0
    ):
        """
        Initialize the ESPN provider
        
        Args:
            sport: Sport enum (default: BASKETBALL)
            league: League enum (default: NBA)
            timeout: Request timeout in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports"
        self.core_url = "https://sports.core.api.espn.com/v2/sports"
        self.sport = sport
        self.league = league
        self.timeout = timeout
        self._team_cache: Dict[str, Dict[str, Any]] = {}
        self._teams_list: Optional[List[Dict[str, Any]]] = None
        
        self.logger.info(f"ESPNProvider initialized for {sport.value}/{league.value}")
    
    def _build_url(self, endpoint: str, use_core: bool = False) -> str:
        """Build the full API URL"""
        base = self.core_url if use_core else self.base_url
        return f"{base}/{self.sport.value}/{self.league.value}/{endpoint}"
    
    async def _fetch(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make an async HTTP request to ESPN API
        
        Args:
            url: Full URL to fetch
            params: Optional query parameters
            
        Returns:
            JSON response as dict or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            self.logger.error(f"Timeout fetching {url}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error {e.response.status_code} fetching {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_sync(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a synchronous HTTP request to ESPN API
        
        Args:
            url: Full URL to fetch
            params: Optional query parameters
            
        Returns:
            JSON response as dict or None on error
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            self.logger.error(f"Timeout fetching {url}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error {e.response.status_code} fetching {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    # ==================== SCOREBOARD ====================
    
    def get_scoreboard(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get scoreboard with live/scheduled/completed games
        
        Args:
            date: Optional date in YYYYMMDD format (default: today)
            
        Returns:
            Dictionary with games, events, and league info
        """
        url = self._build_url("scoreboard")
        params = {"dates": date} if date else None
        
        data = self._fetch_sync(url, params)
        if not data:
            return {"events": [], "error": "Failed to fetch scoreboard"}
        
        return data
    
    def get_today_scores(self) -> List[Dict[str, Any]]:
        """
        Get today's scores in a simplified format.
        Uses US Eastern timezone since that's what ESPN/NBA uses for game dates.
        
        Returns:
            List of game dictionaries with scores, teams, status
        """
        from datetime import datetime
        import pytz
        
        # Use Eastern Time since ESPN/NBA uses ET for game dates
        eastern = pytz.timezone('US/Eastern')
        today_et = datetime.now(eastern).strftime("%Y%m%d")
        
        scoreboard = self.get_scoreboard(date=today_et)
        games = []
        
        for event in scoreboard.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])
            
            if len(competitors) >= 2:
                home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                
                game = {
                    "id": event.get("id"),
                    "name": event.get("name"),
                    "date": event.get("date"),
                    "status": event.get("status", {}).get("type", {}).get("description", "Unknown"),
                    "status_detail": event.get("status", {}).get("type", {}).get("detail", ""),
                    "period": event.get("status", {}).get("period", 0),
                    "clock": event.get("status", {}).get("displayClock", ""),
                    "home_team": {
                        "id": home.get("team", {}).get("id"),
                        "name": home.get("team", {}).get("displayName"),
                        "abbreviation": home.get("team", {}).get("abbreviation"),
                        "score": home.get("score", "0"),
                        "logo": home.get("team", {}).get("logo"),
                        "winner": home.get("winner", False)
                    },
                    "away_team": {
                        "id": away.get("team", {}).get("id"),
                        "name": away.get("team", {}).get("displayName"),
                        "abbreviation": away.get("team", {}).get("abbreviation"),
                        "score": away.get("score", "0"),
                        "logo": away.get("team", {}).get("logo"),
                        "winner": away.get("winner", False)
                    },
                    "venue": competition.get("venue", {}).get("fullName", ""),
                    "broadcast": self._get_broadcast(competition),
                    "odds": self._get_odds(competition)
                }
                games.append(game)
        
        return games
    
    def _get_broadcast(self, competition: Dict) -> str:
        """Extract broadcast info from competition"""
        broadcasts = competition.get("broadcasts", [])
        if broadcasts:
            names = broadcasts[0].get("names", [])
            return ", ".join(names) if names else ""
        return ""
    
    def _get_odds(self, competition: Dict) -> Optional[Dict[str, Any]]:
        """Extract betting odds from competition"""
        odds_list = competition.get("odds", [])
        if odds_list:
            odds = odds_list[0]
            return {
                "provider": odds.get("provider", {}).get("name", ""),
                "spread": odds.get("spread"),
                "over_under": odds.get("overUnder"),
                "home_team_odds": odds.get("homeTeamOdds", {}),
                "away_team_odds": odds.get("awayTeamOdds", {})
            }
        return None

    # ==================== TEAMS ====================
    
    def get_all_teams(self) -> List[Dict[str, Any]]:
        """
        Get list of all teams in the league
        
        Returns:
            List of team dictionaries
        """
        if self._teams_list:
            return self._teams_list
        
        url = self._build_url("teams")
        data = self._fetch_sync(url)
        
        if not data:
            return []
        
        teams = []
        for group in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = group.get("team", {})
            teams.append({
                "id": team.get("id"),
                "name": team.get("displayName"),
                "abbreviation": team.get("abbreviation"),
                "nickname": team.get("nickname"),
                "location": team.get("location"),
                "color": team.get("color"),
                "alternate_color": team.get("alternateColor"),
                "logo": team.get("logos", [{}])[0].get("href") if team.get("logos") else None,
                "links": {link.get("rel", [""])[0]: link.get("href") for link in team.get("links", [])}
            })
        
        self._teams_list = teams
        return teams
    
    def get_team(self, team_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific team
        
        Args:
            team_identifier: Team abbreviation, name, or ID
            
        Returns:
            Team dictionary or None if not found
        """
        # Check cache first
        cache_key = team_identifier.lower()
        if cache_key in self._team_cache:
            return self._team_cache[cache_key]
        
        # Try direct fetch with identifier
        url = self._build_url(f"teams/{team_identifier}")
        data = self._fetch_sync(url)
        
        if data and "team" in data:
            team_data = self._parse_team_response(data)
            self._team_cache[cache_key] = team_data
            return team_data
        
        # Search in all teams
        all_teams = self.get_all_teams()
        identifier_lower = team_identifier.lower()
        
        for team in all_teams:
            if (team.get("abbreviation", "").lower() == identifier_lower or
                team.get("name", "").lower() == identifier_lower or
                team.get("nickname", "").lower() == identifier_lower or
                identifier_lower in team.get("name", "").lower()):
                # Fetch full details
                team_id = team.get("id")
                if team_id:
                    url = self._build_url(f"teams/{team_id}")
                    data = self._fetch_sync(url)
                    if data and "team" in data:
                        team_data = self._parse_team_response(data)
                        self._team_cache[cache_key] = team_data
                        return team_data
        
        return None
    
    def _parse_team_response(self, data: Dict) -> Dict[str, Any]:
        """Parse the team API response into a clean format"""
        team = data.get("team", {})
        
        # Get record/standings
        record = team.get("record", {}).get("items", [{}])[0] if team.get("record") else {}
        stats = record.get("stats", [])
        stats_dict = {s.get("name"): s.get("value") for s in stats}
        
        # Get next event
        next_event = team.get("nextEvent", [{}])[0] if team.get("nextEvent") else {}
        
        return {
            "id": team.get("id"),
            "name": team.get("displayName"),
            "abbreviation": team.get("abbreviation"),
            "nickname": team.get("nickname"),
            "location": team.get("location"),
            "color": team.get("color"),
            "alternate_color": team.get("alternateColor"),
            "logo": team.get("logos", [{}])[0].get("href") if team.get("logos") else None,
            "record": {
                "summary": record.get("summary", ""),
                "wins": stats_dict.get("wins", 0),
                "losses": stats_dict.get("losses", 0),
                "win_percent": stats_dict.get("winPercent", 0),
                "games_behind": stats_dict.get("gamesBehind", 0),
                "streak": stats_dict.get("streak", 0),
                "home_record": stats_dict.get("home", ""),
                "away_record": stats_dict.get("away", ""),
                "conference_record": stats_dict.get("vs. Conf.", "")
            },
            "standings_summary": team.get("standingSummary", ""),
            "next_event": {
                "id": next_event.get("id"),
                "name": next_event.get("name"),
                "date": next_event.get("date"),
                "short_name": next_event.get("shortName")
            } if next_event else None,
            "franchise": team.get("franchise", {})
        }

    # ==================== NEWS ====================
    
    def get_news(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Get latest news articles
        
        Args:
            limit: Maximum number of articles (default: 25)
            
        Returns:
            List of news article dictionaries
        """
        url = self._build_url("news")
        params = {"limit": limit}
        
        data = self._fetch_sync(url, params)
        if not data:
            return []
        
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "headline": article.get("headline"),
                "description": article.get("description"),
                "published": article.get("published"),
                "link": article.get("links", {}).get("web", {}).get("href"),
                "images": [img.get("url") for img in article.get("images", [])],
                "categories": [cat.get("description") for cat in article.get("categories", [])],
                "type": article.get("type")
            })
        
        return articles
    
    def get_team_news(self, team_identifier: str) -> List[Dict[str, Any]]:
        """
        Get news for a specific team
        
        Args:
            team_identifier: Team abbreviation, name, or ID
            
        Returns:
            List of news articles for the team
        """
        team = self.get_team(team_identifier)
        if not team:
            return []
        
        team_id = team.get("id")
        url = self._build_url(f"teams/{team_id}/news")
        
        data = self._fetch_sync(url)
        if not data:
            return []
        
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "headline": article.get("headline"),
                "description": article.get("description"),
                "published": article.get("published"),
                "link": article.get("links", {}).get("web", {}).get("href"),
                "type": article.get("type")
            })
        
        return articles

    # ==================== INJURIES ====================
    
    def get_injuries(self, team_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get injury reports
        
        Args:
            team_name: Optional team name to filter injuries
            
        Returns:
            List of injury dictionaries grouped by team
        """
        # Try the injuries endpoint (not all leagues support this)
        url = self._build_url("injuries")
        data = self._fetch_sync(url)
        
        injuries = []
        
        if data:
            for team_injuries in data.get("injuries", []):
                team_info = team_injuries.get("team", {})
                team_display_name = team_info.get("displayName", "")
                
                # Filter by team if specified
                if team_name:
                    team_name_lower = team_name.lower()
                    if (team_name_lower not in team_display_name.lower() and
                        team_name_lower not in team_info.get("abbreviation", "").lower()):
                        continue
                
                for injury in team_injuries.get("injuries", []):
                    athlete = injury.get("athlete", {})
                    injuries.append({
                        "team": team_display_name,
                        "team_abbreviation": team_info.get("abbreviation"),
                        "team_logo": team_info.get("logos", [{}])[0].get("href") if team_info.get("logos") else None,
                        "player_id": athlete.get("id"),
                        "player_name": athlete.get("displayName"),
                        "player_position": athlete.get("position", {}).get("abbreviation"),
                        "player_headshot": athlete.get("headshot", {}).get("href"),
                        "status": injury.get("status"),
                        "injury_type": injury.get("type", {}).get("description"),
                        "injury_detail": injury.get("details", {}).get("detail"),
                        "return_date": injury.get("details", {}).get("returnDate"),
                        "long_comment": injury.get("longComment"),
                        "short_comment": injury.get("shortComment")
                    })
        
        return injuries
    
    def get_team_injuries(self, team_name: str) -> List[Dict[str, Any]]:
        """
        Get injuries for a specific team
        
        Args:
            team_name: Team name, abbreviation, or ID
            
        Returns:
            List of injury dictionaries for the team
        """
        return self.get_injuries(team_name=team_name)

    # ==================== STANDINGS ====================
    
    def get_standings(self) -> Dict[str, Any]:
        """
        Get current league standings
        
        Returns:
            Dictionary with standings organized by conference/division
        """
        # Standings uses a different API path
        url = f"https://site.api.espn.com/apis/v2/sports/{self.sport.value}/{self.league.value}/standings"
        data = self._fetch_sync(url)
        
        if not data:
            return {"error": "Failed to fetch standings"}
        
        standings = {"conferences": []}
        
        for group in data.get("children", []):
            conference = {
                "name": group.get("name"),
                "abbreviation": group.get("abbreviation"),
                "divisions": []
            }
            
            # Handle divisions if present
            if group.get("children"):
                for division in group.get("children", []):
                    div_standings = self._parse_standings_entries(division.get("standings", {}).get("entries", []))
                    conference["divisions"].append({
                        "name": division.get("name"),
                        "teams": div_standings
                    })
            else:
                # No divisions, just conference
                conf_standings = self._parse_standings_entries(group.get("standings", {}).get("entries", []))
                conference["teams"] = conf_standings
            
            standings["conferences"].append(conference)
        
        return standings
    
    def _parse_standings_entries(self, entries: List[Dict]) -> List[Dict[str, Any]]:
        """Parse standings entries into a clean format"""
        teams = []
        for entry in entries:
            team = entry.get("team", {})
            stats = entry.get("stats", [])
            stats_dict = {s.get("name"): s.get("value") for s in stats}
            
            # Get playoff seed for proper ranking
            playoff_seed = int(stats_dict.get("playoffSeed", 99))
            
            teams.append({
                "rank": playoff_seed,
                "team_id": team.get("id"),
                "team_name": team.get("displayName"),
                "abbreviation": team.get("abbreviation"),
                "logo": team.get("logos", [{}])[0].get("href") if team.get("logos") else None,
                "wins": int(stats_dict.get("wins", 0)),
                "losses": int(stats_dict.get("losses", 0)),
                "win_percent": stats_dict.get("winPercent", 0),
                "games_behind": stats_dict.get("gamesBehind", 0),
                "home_record": stats_dict.get("home", ""),
                "away_record": stats_dict.get("away", ""),
                "streak": int(stats_dict.get("streak", 0)),
                "last_10": stats_dict.get("last10", ""),
                "points_for": stats_dict.get("pointsFor", 0),
                "points_against": stats_dict.get("pointsAgainst", 0),
                "differential": stats_dict.get("differential", 0)
            })
        
        # Sort by playoff seed (rank)
        teams.sort(key=lambda x: x["rank"])
        
        return teams

    # ==================== GAME DETAILS ====================
    
    def get_game_details(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific game
        
        Args:
            game_id: ESPN game/event ID
            
        Returns:
            Dictionary with comprehensive game details or None if not found
        """
        url = self._build_url("summary")
        params = {"event": game_id}
        
        data = self._fetch_sync(url, params)
        if not data:
            return None
        
        # Parse the detailed response
        header = data.get("header", {})
        boxscore = data.get("boxscore", {})
        game_info = data.get("gameInfo", {})
        leaders = data.get("leaders", [])
        
        competition = header.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})
        
        return {
            "id": header.get("id"),
            "game_date": header.get("gameDate"),
            "status": competition.get("status", {}).get("type", {}).get("description"),
            "status_detail": competition.get("status", {}).get("type", {}).get("detail"),
            "venue": {
                "name": game_info.get("venue", {}).get("fullName"),
                "city": game_info.get("venue", {}).get("address", {}).get("city"),
                "state": game_info.get("venue", {}).get("address", {}).get("state"),
                "capacity": game_info.get("venue", {}).get("capacity"),
                "attendance": game_info.get("attendance")
            },
            "home_team": self._parse_competitor(home),
            "away_team": self._parse_competitor(away),
            "boxscore": self._parse_boxscore(boxscore, home, away),
            "leaders": self._parse_leaders(leaders),
            "officials": [ref.get("displayName") for ref in game_info.get("officials", [])],
            "broadcasts": [b.get("media", {}).get("shortName") for b in header.get("broadcasts", [])]
        }
    
    def _parse_competitor(self, competitor: Dict) -> Dict[str, Any]:
        """Parse competitor info from game details"""
        team = competitor.get("team", {})
        score = competitor.get("score")
        
        # Get line scores (quarter/period scores)
        linescores = []
        for ls in competitor.get("linescores", []):
            linescores.append(ls.get("displayValue", ls.get("value", 0)))
        
        return {
            "id": team.get("id"),
            "name": team.get("displayName"),
            "abbreviation": team.get("abbreviation"),
            "logo": team.get("logos", [{}])[0].get("href") if team.get("logos") else None,
            "color": team.get("color"),
            "score": score,
            "linescores": linescores,
            "record": competitor.get("record", [{}])[0].get("displayValue") if competitor.get("record") else "",
            "winner": competitor.get("winner", False)
        }
    
    def _parse_boxscore(self, boxscore: Dict, home: Dict, away: Dict) -> Dict[str, Any]:
        """Parse boxscore data"""
        result = {"home": {}, "away": {}}
        
        for player_stats in boxscore.get("players", []):
            team_id = player_stats.get("team", {}).get("id")
            team_key = "home" if team_id == home.get("team", {}).get("id") else "away"
            
            result[team_key] = {
                "team": player_stats.get("team", {}).get("displayName"),
                "statistics": []
            }
            
            for stat_group in player_stats.get("statistics", []):
                stat_entry = {
                    "name": stat_group.get("name"),
                    "labels": stat_group.get("labels", []),
                    "players": []
                }
                
                for athlete in stat_group.get("athletes", []):
                    stat_entry["players"].append({
                        "name": athlete.get("athlete", {}).get("displayName"),
                        "position": athlete.get("athlete", {}).get("position", {}).get("abbreviation"),
                        "starter": athlete.get("starter", False),
                        "stats": athlete.get("stats", [])
                    })
                
                result[team_key]["statistics"].append(stat_entry)
        
        return result
    
    def _parse_leaders(self, leaders: List) -> List[Dict[str, Any]]:
        """Parse game leaders (top performers)"""
        result = []
        for leader_category in leaders:
            category = {
                "name": leader_category.get("name"),
                "display_name": leader_category.get("displayName"),
                "leaders": []
            }
            
            for leader in leader_category.get("leaders", []):
                athlete = leader.get("athlete", {})
                team = leader.get("team", {})
                category["leaders"].append({
                    "player_name": athlete.get("displayName"),
                    "player_id": athlete.get("id"),
                    "headshot": athlete.get("headshot"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "team": team.get("displayName"),
                    "team_abbreviation": team.get("abbreviation"),
                    "value": leader.get("displayValue"),
                    "stats": leader.get("statistics", [])
                })
            
            result.append(category)
        
        return result

    # ==================== RANKINGS (College Sports) ====================
    
    def get_rankings(self) -> List[Dict[str, Any]]:
        """
        Get rankings (primarily for college sports)
        
        Returns:
            List of ranking polls with teams
        """
        url = self._build_url("rankings")
        data = self._fetch_sync(url)
        
        if not data:
            return []
        
        rankings = []
        for poll in data.get("rankings", []):
            ranking = {
                "name": poll.get("name"),
                "short_name": poll.get("shortName"),
                "type": poll.get("type"),
                "teams": []
            }
            
            for rank in poll.get("ranks", []):
                team = rank.get("team", {})
                ranking["teams"].append({
                    "rank": rank.get("current"),
                    "previous_rank": rank.get("previous"),
                    "trend": rank.get("trend"),
                    "points": rank.get("points"),
                    "team_id": team.get("id"),
                    "team_name": team.get("nickname") or team.get("name"),
                    "location": team.get("location"),
                    "logo": team.get("logo"),
                    "record": rank.get("recordSummary")
                })
            
            rankings.append(ranking)
        
        return rankings

    # ==================== SCHEDULE ====================
    
    def get_team_schedule(self, team_identifier: str, season: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get schedule for a specific team
        
        Args:
            team_identifier: Team abbreviation, name, or ID
            season: Optional season year (default: current)
            
        Returns:
            List of scheduled/completed games
        """
        team = self.get_team(team_identifier)
        if not team:
            return []
        
        team_id = team.get("id")
        url = self._build_url(f"teams/{team_id}/schedule")
        params = {"season": season} if season else None
        
        data = self._fetch_sync(url, params)
        if not data:
            return []
        
        schedule = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])
            
            opponent = None
            is_home = False
            for comp in competitors:
                if comp.get("team", {}).get("id") != team_id:
                    opponent = comp.get("team", {})
                else:
                    is_home = comp.get("homeAway") == "home"
            
            schedule.append({
                "id": event.get("id"),
                "date": event.get("date"),
                "name": event.get("name"),
                "short_name": event.get("shortName"),
                "home_away": "home" if is_home else "away",
                "opponent": {
                    "id": opponent.get("id") if opponent else None,
                    "name": opponent.get("displayName") if opponent else None,
                    "abbreviation": opponent.get("abbreviation") if opponent else None,
                    "logo": opponent.get("logos", [{}])[0].get("href") if opponent and opponent.get("logos") else None
                },
                "status": event.get("status", {}).get("type", {}).get("description"),
                "result": self._get_game_result(competition, team_id)
            })
        
        return schedule
    
    def _get_game_result(self, competition: Dict, team_id: str) -> Optional[Dict[str, Any]]:
        """Get game result for a team"""
        if competition.get("status", {}).get("type", {}).get("completed"):
            for comp in competition.get("competitors", []):
                if comp.get("team", {}).get("id") == team_id:
                    return {
                        "score": comp.get("score", {}).get("value"),
                        "winner": comp.get("winner", False)
                    }
        return None

    # ==================== HELPER: Change Sport/League ====================
    
    def set_sport_league(self, sport: Sport, league: League) -> None:
        """
        Change the sport and league for this provider
        
        Args:
            sport: New sport
            league: New league
        """
        self.sport = sport
        self.league = league
        self._team_cache.clear()
        self._teams_list = None
        self.logger.info(f"ESPNProvider switched to {sport.value}/{league.value}")
