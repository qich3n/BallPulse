import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)


class InjuryService:
    """
    Service for fetching NBA player injuries
    
    Now integrates with ESPN's hidden API for real injury data.
    Falls back to context-provided injuries if ESPN data unavailable.
    """
    
    def __init__(self):
        """Initialize injury service with ESPN provider"""
        self.logger = logging.getLogger(__name__)
        self._espn_provider = None
        self._init_espn_provider()
        self.logger.info("InjuryService initialized with ESPN integration")
    
    def _init_espn_provider(self):
        """Lazily initialize ESPN provider"""
        try:
            from ..providers.espn_provider import ESPNProvider, Sport, League
            self._espn_provider = ESPNProvider(sport=Sport.BASKETBALL, league=League.NBA)
        except (ImportError, ValueError, RuntimeError) as e:
            self.logger.warning("Failed to initialize ESPN provider: %s", e)
            self._espn_provider = None
    
    def fetch_team_injuries(self, team_name: str) -> List[str]:
        """
        Fetch injuries for a team from ESPN
        
        Args:
            team_name: Name of the team
            
        Returns:
            List of injury descriptions in format "Player Name - Status (Reason)"
        """
        if not self._espn_provider:
            self.logger.debug("ESPN provider not available, returning empty injuries")
            return []
        
        try:
            injuries = self._espn_provider.get_team_injuries(team_name)
            
            injury_strings = []
            for injury in injuries:
                player = injury.get("player_name", "Unknown")
                status = injury.get("status", "Unknown")
                injury_type = injury.get("injury_type", "")
                
                if injury_type:
                    injury_strings.append(f"{player} - {status} ({injury_type})")
                else:
                    injury_strings.append(f"{player} - {status}")
            
            self.logger.info("Found %d injuries for %s", len(injury_strings), team_name)
            return injury_strings
            
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error fetching injuries for %s: %s", team_name, e)
            return []
    
    def fetch_all_injuries(self) -> List[Dict[str, any]]:
        """
        Fetch all injuries across the league
        
        Returns:
            List of injury dictionaries with full details
        """
        if not self._espn_provider:
            return []
        
        try:
            return self._espn_provider.get_injuries()
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error fetching all injuries: %s", e)
            return []
    
    def get_injury_report(self, team_name: str) -> Dict[str, List[Dict]]:
        """
        Get a structured injury report for a team
        
        Args:
            team_name: Name of the team
            
        Returns:
            Dictionary with injuries grouped by status
        """
        if not self._espn_provider:
            return {"out": [], "doubtful": [], "questionable": [], "probable": []}
        
        try:
            injuries = self._espn_provider.get_team_injuries(team_name)
            
            report = {
                "out": [],
                "doubtful": [],
                "questionable": [],
                "probable": [],
                "day_to_day": []
            }
            
            for injury in injuries:
                status = injury.get("status", "").lower()
                
                injury_info = {
                    "player": injury.get("player_name"),
                    "position": injury.get("player_position"),
                    "injury": injury.get("injury_type"),
                    "detail": injury.get("injury_detail"),
                    "return_date": injury.get("return_date"),
                    "comment": injury.get("short_comment")
                }
                
                if "out" in status:
                    report["out"].append(injury_info)
                elif "doubtful" in status:
                    report["doubtful"].append(injury_info)
                elif "questionable" in status:
                    report["questionable"].append(injury_info)
                elif "probable" in status:
                    report["probable"].append(injury_info)
                else:
                    report["day_to_day"].append(injury_info)
            
            return report
            
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error getting injury report for %s: %s", team_name, e)
            return {"out": [], "doubtful": [], "questionable": [], "probable": [], "day_to_day": []}
    
    def parse_injury_string(self, injury_string: str) -> Dict[str, str]:
        """
        Parse an injury string into structured data
        
        Args:
            injury_string: Injury string like "Player Name - Out" or "Player Name - Questionable (reason)"
            
        Returns:
            Dictionary with player, status, and reason
        """
        # Simple parsing: "Player Name - Status (Reason)" or "Player Name - Status"
        parts = injury_string.split(' - ', 1)
        if len(parts) == 2:
            player = parts[0].strip()
            status_part = parts[1].strip()
            
            # Check for reason in parentheses
            reason_match = re.search(r'\(([^)]+)\)', status_part)
            reason = reason_match.group(1) if reason_match else ''
            status = re.sub(r'\s*\([^)]+\)\s*', '', status_part).strip()
            
            return {
                'player': player,
                'status': status,
                'reason': reason
            }
        
        return {
            'player': injury_string,
            'status': 'Unknown',
            'reason': ''
        }
