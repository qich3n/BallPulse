import logging
import time
from typing import Dict, Any, Optional
from nba_api.stats.endpoints import teamgamelog, teamdashboardbygeneralsplits
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
            
            # If TeamGameLog fails, try TeamDashboardByGeneralSplits as fallback
            if games_df is None or games_df.empty:
                self.logger.info(f"TeamGameLog returned no data, trying TeamDashboardByGeneralSplits as fallback for team '{team_name}'")
                games_df = None
                season = SeasonAll.current_season
                
                # Try dashboard endpoint (this endpoint seems to work better)
                seasons_to_try_dashboard = [
                    season,
                    f"{int(season.split('-')[0])-1}-{str(int(season.split('-')[0]))[2:]}",
                    f"{int(season.split('-')[0])-2}-{str(int(season.split('-')[0])-1)[2:]}",
                ]
                
                for dash_season in seasons_to_try_dashboard:
                    try:
                        time.sleep(0.6)
                        dashboard = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
                            team_id=team_id,
                            season=dash_season
                        )
                        dashboard_df = dashboard.get_data_frames()[0]
                        
                        if dashboard_df is not None and not dashboard_df.empty:
                            self.logger.info(f"Successfully fetched dashboard stats for season {dash_season}")
                            # Dashboard gives season averages, so we'll use those
                            # Convert to match our expected format by creating a synthetic games_df structure
                            season = dash_season
                            games_df = dashboard_df  # Use dashboard data
                            break
                    except Exception as e:
                        self.logger.debug(f"Dashboard endpoint error for season {dash_season}: {e}")
                        continue
            
            if games_df is None or games_df.empty:
                self.logger.warning(f"No stats found for team '{team_name}' (team_id={team_id}) after trying TeamGameLog and TeamDashboard endpoints. Using placeholder data.")
                return self._get_placeholder_stats(team_name)
            
            # Check if we're using dashboard data (different structure) or game log data
            is_dashboard_data = games_df.shape[0] == 1 and 'FG_PCT' in games_df.columns and 'REB' in games_df.columns
            
            if is_dashboard_data:
                # Dashboard data provides season totals, so we need to divide by games played for per-game averages
                self.logger.debug("Using TeamDashboard data (season totals, converting to per-game averages)")
                row = games_df.iloc[0]
                gp = float(row.get('GP', 82)) if 'GP' in games_df.columns else 82.0
                
                # FG_PCT is already a percentage, not a total
                shooting_pct = float(row.get('FG_PCT', 0.450)) if 'FG_PCT' in games_df.columns else 0.450
                
                # REB and TOV are totals, so divide by games played to get per-game averages
                rebounding_avg = float(row.get('REB', 0.0)) / gp if 'REB' in games_df.columns and gp > 0 else 42.0
                turnovers_avg = float(row.get('TOV', 0.0)) / gp if 'TOV' in games_df.columns and gp > 0 else 14.0
                
                # PLUS_MINUS is already a per-game average (or season total divided by games)
                # Actually, it appears to be season total, so divide by GP
                if 'PLUS_MINUS' in games_df.columns:
                    net_rating_proxy = float(row.get('PLUS_MINUS', 0.0)) / gp if gp > 0 else 0.0
                elif 'PTS' in games_df.columns:
                    # PTS is season total, divide by GP then subtract league average
                    pts_per_game = float(row.get('PTS', 0)) / gp if gp > 0 else 0
                    net_rating_proxy = pts_per_game - 108.0  # League average proxy
                else:
                    net_rating_proxy = 0.0
                
                # Use actual games played, capped at 10 for display purposes
                num_games = min(int(gp), 10) if gp > 0 else 10
            else:
                # Game log data - calculate from individual games
                recent_games = games_df.head(10) if games_df is not None and not games_df.empty else games_df
                num_games = len(recent_games)
                
                # Calculate averages from game log
                shooting_pct = recent_games['FG_PCT'].mean() if 'FG_PCT' in recent_games.columns else 0.450
                rebounding_avg = recent_games['REB'].mean() if 'REB' in recent_games.columns else 42.0
                turnovers_avg = recent_games['TOV'].mean() if 'TOV' in recent_games.columns else 14.0
                
                # Calculate net rating proxy (using point differential)
                if 'PLUS_MINUS' in recent_games.columns:
                    net_rating_proxy = recent_games['PLUS_MINUS'].mean()
                else:
                    # Fallback: calculate from points if available
                    if 'PTS' in recent_games.columns:
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

