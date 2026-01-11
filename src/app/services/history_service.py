import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import diskcache

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for storing and retrieving comparison history"""
    
    def __init__(self, history_dir: str = ".history"):
        """
        Initialize history service
        
        Args:
            history_dir: Directory for history storage
        """
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)
        self.cache = diskcache.Cache(history_dir)
        logger.info(f"History service initialized with history_dir={history_dir}")
    
    def add_comparison(self, team1: str, team2: str, sport: str, result: Dict[str, Any]) -> str:
        """
        Add a comparison to history
        
        Args:
            team1: First team name
            team2: Second team name
            sport: Sport type
            result: Comparison result data
            
        Returns:
            History entry ID
        """
        entry_id = f"{datetime.now().isoformat()}_{team1}_{team2}"
        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "team1": team1,
            "team2": team2,
            "sport": sport,
            "predicted_winner": result.get("matchup", {}).get("predicted_winner"),
            "win_probability": result.get("matchup", {}).get("win_probability"),
            "result": result
        }
        
        # Store in cache with timestamp as key
        timestamp_key = datetime.now().timestamp()
        self.cache.set(timestamp_key, entry)
        
        # Also store by team pair for easy lookup
        team_key = f"teams:{sport}:{':'.join(sorted([team1.lower(), team2.lower()]))}"
        existing = self.cache.get(team_key, default=[])
        existing.append(entry_id)
        self.cache.set(team_key, existing)
        
        logger.info(f"Added comparison to history: {team1} vs {team2}")
        return entry_id
    
    def get_history(self, limit: int = 50, team1: Optional[str] = None, team2: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get comparison history
        
        Args:
            limit: Maximum number of entries to return
            team1: Optional filter by team1
            team2: Optional filter by team2
            
        Returns:
            List of history entries, sorted by most recent first
        """
        all_entries = []
        
        # Get all entries from cache
        for key in self.cache:
            if isinstance(key, (int, float)):  # Timestamp keys
                entry = self.cache.get(key)
                if entry and isinstance(entry, dict):
                    # Apply filters
                    if team1 and team1.lower() not in [entry.get("team1", "").lower(), entry.get("team2", "").lower()]:
                        continue
                    if team2 and team2.lower() not in [entry.get("team1", "").lower(), entry.get("team2", "").lower()]:
                        continue
                    all_entries.append(entry)
        
        # Sort by timestamp (most recent first)
        all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return all_entries[:limit]
    
    def get_comparison(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific comparison by ID
        
        Args:
            entry_id: History entry ID
            
        Returns:
            History entry or None if not found
        """
        for key in self.cache:
            if isinstance(key, (int, float)):
                entry = self.cache.get(key)
                if entry and isinstance(entry, dict) and entry.get("id") == entry_id:
                    return entry
        return None
    
    def clear_history(self) -> int:
        """
        Clear all history
        
        Returns:
            Number of entries cleared
        """
        count = len(list(self.cache))
        self.cache.clear()
        logger.info(f"Cleared {count} history entries")
        return count
