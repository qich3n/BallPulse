"""Team name normalization utility"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TeamNormalizer:
    """Normalizes team names from short/nickname forms to full official names"""
    
    # Mapping of common short names, nicknames, and abbreviations to full official NBA team names
    TEAM_NAME_MAP: Dict[str, str] = {
        # Los Angeles Lakers
        "lakers": "Los Angeles Lakers",
        "la lakers": "Los Angeles Lakers",
        "los angeles lakers": "Los Angeles Lakers",
        "lal": "Los Angeles Lakers",
        
        # Boston Celtics
        "celtics": "Boston Celtics",
        "boston celtics": "Boston Celtics",
        "bos": "Boston Celtics",
        "boston": "Boston Celtics",
        
        # Golden State Warriors
        "warriors": "Golden State Warriors",
        "golden state warriors": "Golden State Warriors",
        "golden state": "Golden State Warriors",
        "gsw": "Golden State Warriors",
        "dubs": "Golden State Warriors",
        "gs": "Golden State Warriors",
        
        # Miami Heat
        "heat": "Miami Heat",
        "miami heat": "Miami Heat",
        "mia": "Miami Heat",
        "miami": "Miami Heat",
        
        # Philadelphia 76ers
        "76ers": "Philadelphia 76ers",
        "sixers": "Philadelphia 76ers",
        "philadelphia 76ers": "Philadelphia 76ers",
        "philadelphia": "Philadelphia 76ers",
        "philadelphia sixers": "Philadelphia 76ers",
        "phi": "Philadelphia 76ers",
        "philly": "Philadelphia 76ers",
        
        # Milwaukee Bucks
        "bucks": "Milwaukee Bucks",
        "milwaukee bucks": "Milwaukee Bucks",
        "milwaukee": "Milwaukee Bucks",
        "mil": "Milwaukee Bucks",
        
        # Denver Nuggets
        "nuggets": "Denver Nuggets",
        "denver nuggets": "Denver Nuggets",
        "denver": "Denver Nuggets",
        "den": "Denver Nuggets",
        
        # Phoenix Suns
        "suns": "Phoenix Suns",
        "phoenix suns": "Phoenix Suns",
        "phoenix": "Phoenix Suns",
        "phx": "Phoenix Suns",
        
        # Dallas Mavericks
        "mavericks": "Dallas Mavericks",
        "dallas mavericks": "Dallas Mavericks",
        "dallas": "Dallas Mavericks",
        "dal": "Dallas Mavericks",
        "mavs": "Dallas Mavericks",
        
        # Brooklyn Nets
        "nets": "Brooklyn Nets",
        "brooklyn nets": "Brooklyn Nets",
        "brooklyn": "Brooklyn Nets",
        "bkn": "Brooklyn Nets",
        "bkn nets": "Brooklyn Nets",
        
        # New York Knicks
        "knicks": "New York Knicks",
        "new york knicks": "New York Knicks",
        "ny knicks": "New York Knicks",
        "ny": "New York Knicks",
        "nyk": "New York Knicks",
        
        # Atlanta Hawks
        "hawks": "Atlanta Hawks",
        "atlanta hawks": "Atlanta Hawks",
        "atlanta": "Atlanta Hawks",
        "atl": "Atlanta Hawks",
        
        # Chicago Bulls
        "bulls": "Chicago Bulls",
        "chicago bulls": "Chicago Bulls",
        "chicago": "Chicago Bulls",
        "chi": "Chicago Bulls",
        
        # Cleveland Cavaliers
        "cavaliers": "Cleveland Cavaliers",
        "cavs": "Cleveland Cavaliers",
        "cleveland cavaliers": "Cleveland Cavaliers",
        "cleveland": "Cleveland Cavaliers",
        "cle": "Cleveland Cavaliers",
        "cleveland cavs": "Cleveland Cavaliers",
        
        # Detroit Pistons
        "pistons": "Detroit Pistons",
        "detroit pistons": "Detroit Pistons",
        "detroit": "Detroit Pistons",
        "det": "Detroit Pistons",
        
        # Indiana Pacers
        "pacers": "Indiana Pacers",
        "indiana pacers": "Indiana Pacers",
        "indiana": "Indiana Pacers",
        "ind": "Indiana Pacers",
        
        # Toronto Raptors
        "raptors": "Toronto Raptors",
        "toronto raptors": "Toronto Raptors",
        "toronto": "Toronto Raptors",
        "tor": "Toronto Raptors",
        
        # Charlotte Hornets
        "hornets": "Charlotte Hornets",
        "charlotte hornets": "Charlotte Hornets",
        "charlotte": "Charlotte Hornets",
        "cha": "Charlotte Hornets",
        
        # Orlando Magic
        "magic": "Orlando Magic",
        "orlando magic": "Orlando Magic",
        "orlando": "Orlando Magic",
        "orl": "Orlando Magic",
        
        # Washington Wizards
        "wizards": "Washington Wizards",
        "washington wizards": "Washington Wizards",
        "washington": "Washington Wizards",
        "was": "Washington Wizards",
        
        # Portland Trail Blazers
        "trail blazers": "Portland Trail Blazers",
        "blazers": "Portland Trail Blazers",
        "portland trail blazers": "Portland Trail Blazers",
        "portland": "Portland Trail Blazers",
        "por": "Portland Trail Blazers",
        "portland blazers": "Portland Trail Blazers",
        
        # Utah Jazz
        "jazz": "Utah Jazz",
        "utah jazz": "Utah Jazz",
        "utah": "Utah Jazz",
        "uta": "Utah Jazz",
        
        # Oklahoma City Thunder
        "thunder": "Oklahoma City Thunder",
        "okc": "Oklahoma City Thunder",
        "oklahoma city thunder": "Oklahoma City Thunder",
        "oklahoma city": "Oklahoma City Thunder",
        "okc thunder": "Oklahoma City Thunder",
        
        # Minnesota Timberwolves
        "timberwolves": "Minnesota Timberwolves",
        "wolves": "Minnesota Timberwolves",
        "minnesota timberwolves": "Minnesota Timberwolves",
        "minnesota": "Minnesota Timberwolves",
        "min": "Minnesota Timberwolves",
        "minnesota wolves": "Minnesota Timberwolves",
        
        # Sacramento Kings
        "kings": "Sacramento Kings",
        "sacramento kings": "Sacramento Kings",
        "sacramento": "Sacramento Kings",
        "sac": "Sacramento Kings",
        
        # Los Angeles Clippers
        "clippers": "Los Angeles Clippers",
        "la clippers": "Los Angeles Clippers",
        "los angeles clippers": "Los Angeles Clippers",
        "lac": "Los Angeles Clippers",
        "la clips": "Los Angeles Clippers",
        
        # Memphis Grizzlies
        "grizzlies": "Memphis Grizzlies",
        "memphis grizzlies": "Memphis Grizzlies",
        "memphis": "Memphis Grizzlies",
        "mem": "Memphis Grizzlies",
        
        # New Orleans Pelicans
        "pelicans": "New Orleans Pelicans",
        "new orleans pelicans": "New Orleans Pelicans",
        "new orleans": "New Orleans Pelicans",
        "no": "New Orleans Pelicans",
        "nop": "New Orleans Pelicans",
        "nola": "New Orleans Pelicans",
        
        # San Antonio Spurs
        "spurs": "San Antonio Spurs",
        "san antonio spurs": "San Antonio Spurs",
        "san antonio": "San Antonio Spurs",
        "sas": "San Antonio Spurs",
        
        # Houston Rockets
        "rockets": "Houston Rockets",
        "houston rockets": "Houston Rockets",
        "houston": "Houston Rockets",
        "hou": "Houston Rockets",
    }
    
    @classmethod
    def normalize(cls, team_name: str) -> str:
        """
        Normalize a team name to its full official NBA name
        
        Args:
            team_name: Team name in any form (short name, nickname, abbreviation, or full name)
            
        Returns:
            Full official NBA team name, or original name if no match found
        """
        if not team_name:
            return team_name
        
        team_name_lower = team_name.lower().strip()
        
        # Check if exact match exists
        if team_name_lower in cls.TEAM_NAME_MAP:
            normalized = cls.TEAM_NAME_MAP[team_name_lower]
            logger.debug(f"Normalized '{team_name}' -> '{normalized}'")
            return normalized
        
        # Try partial matching for edge cases
        # Check if any key in the map contains the input or vice versa
        for key, value in cls.TEAM_NAME_MAP.items():
            if team_name_lower in key or key in team_name_lower:
                normalized = value
                logger.debug(f"Normalized '{team_name}' -> '{normalized}' (partial match)")
                return normalized
        
        # If no match found, return original (case-preserved, but trimmed)
        logger.debug(f"No normalization found for '{team_name}', returning as-is")
        return team_name.strip()
    
    @classmethod
    def normalize_multiple(cls, *team_names: str) -> tuple:
        """
        Normalize multiple team names
        
        Args:
            *team_names: Variable number of team names to normalize
            
        Returns:
            Tuple of normalized team names
        """
        return tuple(cls.normalize(name) for name in team_names)

