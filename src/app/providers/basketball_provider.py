import logging
import time
from typing import Dict, Any, Optional
from nba_api.stats.endpoints import teamgamelog
from nba_api.stats.static import teams
from nba_api.stats.library.parameters import SeasonAll

logger = logging.getLogger(__name__)


class BasketballProvider:
    """Provider for fetching basketball team statistics using nba_api"""
    
    def __init__(self):
        """Initialize the basketball provider"""
        self.logger = logging.getLogger(__name__)
        self._team_cache: Dict[str, Optional[int]] = {}
    
    def _get_team_id(self, team_name: str) -> Optional[int]:
        """
        Get NBA team ID from team name
        
        Args:
            team_name: Name of the team
            
        Returns:
            Team ID or None if not found
        """
        # Check cache first
        cache_key = team_name.lower()
        if cache_key in self._team_cache:
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
            
            if not team_id:
                self.logger.warning(f"Team '{team_name}' not found in NBA teams")
            
            return team_id
            
        except Exception as e:
            self.logger.error(f"Error fetching team ID for '{team_name}': {e}")
            return None
    
    def _get_placeholder_stats(self, team_name: str) -> Dict[str, Any]:
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
        Get normalized stats summary for a team (last 10 games)
        
        Args:
            team_name: Name of the team
            
        Returns:
            Dictionary with normalized stats:
            - last_10_games: Number of games (up to 10)
            - shooting_pct: Average field goal percentage
            - rebounding_avg: Average rebounds per game
            - turnovers_avg: Average turnovers per game
            - net_rating_proxy: Net rating proxy (offensive rating - defensive rating)
            - team_name: Team name
            - data_source: "nba_api" or "placeholder"
        """
        team_id = self._get_team_id(team_name)
        
        if not team_id:
            self.logger.warning(f"Team ID not found for '{team_name}', using placeholder data")
            return self._get_placeholder_stats(team_name)
        
        try:
            # Try current season first
            season = SeasonAll.current_season
            self.logger.debug(f"Fetching stats for team_id={team_id}, season={season}")
            
            try:
                # Add small delay to avoid rate limiting
                time.sleep(0.6)  # NBA API recommends delays between requests
                
                gamelog = teamgamelog.TeamGameLog(
                    team_id=team_id,
                    season=season
                )
                # Get the game log dataframe
                games_df = gamelog.get_data_frames()[0]
                
                # Log response details for debugging
                if hasattr(gamelog, 'get_dict'):
                    try:
                        response_dict = gamelog.get_dict()
                        result_sets = response_dict.get('resultSets', [])
                        if result_sets:
                            row_set = result_sets[0].get('rowSet', [])
                            self.logger.info(f"API response: {len(row_set)} rows returned for season {season}, team '{team_name}'")
                            if len(row_set) == 0:
                                self.logger.warning(f"API returned empty rowSet for season {season}. This may indicate the season hasn't started, data isn't available yet, or the API format changed.")
                        else:
                            self.logger.warning(f"API returned empty resultSets for season {season}")
                    except Exception as dict_error:
                        self.logger.debug(f"Could not parse API response dict: {dict_error}")
                
                self.logger.debug(f"API call successful for {season}. DataFrame shape: {games_df.shape}, columns: {list(games_df.columns) if not games_df.empty else 'empty'}")
            except Exception as api_error:
                self.logger.error(f"API error fetching current season {season} for team '{team_name}' (team_id={team_id}): {api_error}", exc_info=True)
                games_df = None
            
            # If no games in current season, try previous seasons
            if games_df is None or games_df.empty:
                self.logger.info(f"No games found in {season} for team '{team_name}' (team_id={team_id}), trying previous seasons")
                # Try multiple previous seasons (last 2 seasons should have data)
                year = int(season.split('-')[0])
                seasons_to_try = [
                    f"{year-1}-{str(year)[2:]}",  # Previous season
                    f"{year-2}-{str(year-1)[2:]}"  # Season before that
                ]
                
                for prev_season in seasons_to_try:
                    self.logger.debug(f"Trying season: {prev_season}")
                    try:
                        # Add delay between API requests
                        time.sleep(0.6)
                        
                        prev_gamelog = teamgamelog.TeamGameLog(
                            team_id=team_id,
                            season=prev_season
                        )
                        prev_games_df = prev_gamelog.get_data_frames()[0]
                        
                        if prev_games_df is not None and not prev_games_df.empty:
                            self.logger.info(f"Found {len(prev_games_df)} games in season {prev_season} for team '{team_name}'")
                            games_df = prev_games_df
                            season = prev_season
                            break
                        else:
                            self.logger.debug(f"No games in season {prev_season} for team '{team_name}'")
                    except Exception as e:
                        self.logger.debug(f"Error fetching season {prev_season} for team '{team_name}': {e}")
                        continue
                
                # If still no data, create empty dataframe
                if games_df is None or games_df.empty:
                    import pandas as pd
                    games_df = pd.DataFrame()
            
            # Get last 10 games (they're already sorted by date descending)
            recent_games = games_df.head(10) if games_df is not None and not games_df.empty else games_df
            
            if games_df is None or games_df.empty:
                self.logger.warning(f"No games found for team '{team_name}' (team_id={team_id}) after trying seasons {SeasonAll.current_season} and previous. API may not have data available or team may have no games. Using placeholder data.")
                return self._get_placeholder_stats(team_name)
            
            num_games = len(recent_games)
            
            # Calculate averages
            shooting_pct = recent_games['FG_PCT'].mean() if 'FG_PCT' in recent_games.columns else 0.450
            rebounding_avg = recent_games['REB'].mean() if 'REB' in recent_games.columns else 42.0
            turnovers_avg = recent_games['TOV'].mean() if 'TOV' in recent_games.columns else 14.0
            
            # Calculate net rating proxy (using point differential)
            # TeamGameLog provides PLUS_MINUS which is point differential per game
            if 'PLUS_MINUS' in recent_games.columns:
                net_rating_proxy = recent_games['PLUS_MINUS'].mean()
            else:
                # Fallback: calculate from points if available
                if 'PTS' in recent_games.columns:
                    # Use average points as a proxy (less accurate)
                    net_rating_proxy = recent_games['PTS'].mean() - 108.0  # League average proxy
                else:
                    net_rating_proxy = 0.0
            
            # Ensure values are not NaN
            shooting_pct = float(shooting_pct) if not (shooting_pct != shooting_pct) else 0.450
            rebounding_avg = float(rebounding_avg) if not (rebounding_avg != rebounding_avg) else 42.0
            turnovers_avg = float(turnovers_avg) if not (turnovers_avg != turnovers_avg) else 14.0
            net_rating_proxy = float(net_rating_proxy) if not (net_rating_proxy != net_rating_proxy) else 0.0
            
            return {
                "last_10_games": num_games,
                "shooting_pct": round(shooting_pct, 3),
                "rebounding_avg": round(rebounding_avg, 1),
                "turnovers_avg": round(turnovers_avg, 1),
                "net_rating_proxy": round(net_rating_proxy, 1),
                "team_name": team_name,
                "data_source": "nba_api"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching stats for team '{team_name}': {e}", exc_info=True)
            return self._get_placeholder_stats(team_name)

