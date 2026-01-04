import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)


class InjuryService:
    """
    Service for fetching NBA player injuries
    
    Note: Currently uses manual input from context. 
    Future enhancement: Integrate with free injury API when available.
    """
    
    def __init__(self):
        """Initialize injury service"""
        self.logger = logging.getLogger(__name__)
        self.logger.info("InjuryService initialized - using context-provided injuries")
    
    def fetch_team_injuries(self, team_name: str) -> List[str]:
        """
        Fetch injuries for a team
        
        Currently returns empty list - injuries should be provided via context.
        This is a placeholder for future API integration.
        
        Args:
            team_name: Name of the team
            
        Returns:
            List of injury descriptions (currently empty - use context injuries)
        """
        # TODO: Integrate with free injury API when available
        # For now, return empty list and rely on context-provided injuries
        self.logger.debug("InjuryService.fetch_team_injuries called for %s - using context injuries", team_name)
        return []
    
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
