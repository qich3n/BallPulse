import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
try:
    from nbainjuries import injury
    NBA_INJURIES_AVAILABLE = True
except ImportError:
    NBA_INJURIES_AVAILABLE = False
    injury = None

logger = logging.getLogger(__name__)


class InjuryService:
    """Service for fetching NBA player injuries using nbainjuries package"""
    
    # Team name mapping (normalized)
    TEAM_NAME_MAP = {
        "atlanta hawks": "Atlanta Hawks",
        "boston celtics": "Boston Celtics",
        "brooklyn nets": "Brooklyn Nets",
        "charlotte hornets": "Charlotte Hornets",
        "chicago bulls": "Chicago Bulls",
        "cleveland cavaliers": "Cleveland Cavaliers",
        "dallas mavericks": "Dallas Mavericks",
        "denver nuggets": "Denver Nuggets",
        "detroit pistons": "Detroit Pistons",
        "golden state warriors": "Golden State Warriors",
        "houston rockets": "Houston Rockets",
        "indiana pacers": "Indiana Pacers",
        "los angeles clippers": "LA Clippers",
        "los angeles lakers": "Los Angeles Lakers",
        "memphis grizzlies": "Memphis Grizzlies",
        "miami heat": "Miami Heat",
        "milwaukee bucks": "Milwaukee Bucks",
        "minnesota timberwolves": "Minnesota Timberwolves",
        "new orleans pelicans": "New Orleans Pelicans",
        "new york knicks": "New York Knicks",
        "oklahoma city thunder": "Oklahoma City Thunder",
        "orlando magic": "Orlando Magic",
        "philadelphia 76ers": "Philadelphia 76ers",
        "phoenix suns": "Phoenix Suns",
        "portland trail blazers": "Portland Trail Blazers",
        "sacramento kings": "Sacramento Kings",
        "san antonio spurs": "San Antonio Spurs",
        "toronto raptors": "Toronto Raptors",
        "utah jazz": "Utah Jazz",
        "washington wizards": "Washington Wizards",
    }
    
    def __init__(self):
        """Initialize injury service"""
        self.logger = logging.getLogger(__name__)
        if not NBA_INJURIES_AVAILABLE:
            self.logger.warning("nbainjuries package not available. Injury tracking will be limited.")
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name to match injury data format"""
        team_lower = team_name.lower()
        return self.TEAM_NAME_MAP.get(team_lower, team_name.title())
    
    def fetch_team_injuries(self, team_name: str) -> List[str]:
        """
        Fetch injuries for a team
        
        Args:
            team_name: Name of the team
            
        Returns:
            List of injury descriptions (e.g., ["Player X - Out", "Player Y - Questionable"])
        """
        if not NBA_INJURIES_AVAILABLE:
            self.logger.warning("nbainjuries package not available")
            return []
        
        try:
            # Get current injury report
            report_datetime = datetime.now()
            injury_data = injury.get_reportdata(report_datetime)
            
            if not injury_data:
                return []
            
            # Normalize team name
            normalized_team = self._normalize_team_name(team_name)
            
            # Filter injuries by team
            team_injuries = []
            for injury_item in injury_data:
                injury_team = injury_item.get('team', '')
                
                # Check if team matches (case-insensitive, partial match)
                if normalized_team.lower() in injury_team.lower() or injury_team.lower() in normalized_team.lower():
                    player_name = injury_item.get('player', 'Unknown Player')
                    status = injury_item.get('status', 'Unknown')
                    reason = injury_item.get('reason', '')
                    
                    # Format: "Player Name - Status (Reason)" or "Player Name - Status"
                    if reason:
                        injury_str = f"{player_name} - {status} ({reason})"
                    else:
                        injury_str = f"{player_name} - {status}"
                    
                    team_injuries.append(injury_str)
            
            # Filter to only "Out" and "Questionable" statuses (most relevant)
            relevant_injuries = [
                inj for inj in team_injuries
                if any(status in inj for status in ['Out', 'Questionable', 'Doubtful', 'Probable'])
            ]
            
            return relevant_injuries[:10]  # Limit to 10 injuries
            
        except Exception as e:
            self.logger.error("Error fetching injuries for %s: %s", team_name, e, exc_info=True)
            return []

