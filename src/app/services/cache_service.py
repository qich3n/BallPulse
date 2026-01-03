import logging
import hashlib
import json
from typing import Optional, Any
import diskcache

logger = logging.getLogger(__name__)


class CacheService:
    """Cache service using diskcache with TTL support"""
    
    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 3600):
        """
        Initialize cache service
        
        Args:
            cache_dir: Directory for cache storage
            default_ttl: Default TTL in seconds (default: 1 hour)
        """
        self.cache = diskcache.Cache(cache_dir)
        self.default_ttl = default_ttl
        logger.info(f"Cache service initialized with cache_dir={cache_dir}, default_ttl={default_ttl}s")
    
    def _generate_key(self, sport: str, team1: str, team2: str, date: Optional[str] = None) -> str:
        """
        Generate cache key from sport, team1, team2, and date
        
        Args:
            sport: Sport type
            team1: First team name
            team2: Second team name
            date: Optional date string
            
        Returns:
            Cache key string
        """
        # Normalize team names (sort to ensure consistent key regardless of order)
        teams = sorted([team1.lower(), team2.lower()])
        key_data = {
            "sport": sport.lower(),
            "team1": teams[0],
            "team2": teams[1],
            "date": date.lower() if date else None
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"compare:{key_hash}"
    
    def get(self, sport: str, team1: str, team2: str, date: Optional[str] = None) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            sport: Sport type
            team1: First team name
            team2: Second team name
            date: Optional date string
            
        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(sport, team1, team2, date)
        value = self.cache.get(key)
        if value is not None:
            logger.info(f"Cache hit for key: {key}")
        else:
            logger.info(f"Cache miss for key: {key}")
        return value
    
    def set(self, sport: str, team1: str, team2: str, value: Any, 
            date: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with TTL
        
        Args:
            sport: Sport type
            team1: First team name
            team2: Second team name
            value: Value to cache
            date: Optional date string
            ttl: Time to live in seconds (uses default_ttl if None)
            
        Returns:
            True if successfully cached
        """
        key = self._generate_key(sport, team1, team2, date)
        ttl = ttl if ttl is not None else self.default_ttl
        result = self.cache.set(key, value, expire=ttl)
        logger.info(f"Cached value for key: {key} with TTL: {ttl}s")
        return result
    
    def delete(self, sport: str, team1: str, team2: str, date: Optional[str] = None) -> bool:
        """
        Delete value from cache
        
        Args:
            sport: Sport type
            team1: First team name
            team2: Second team name
            date: Optional date string
            
        Returns:
            True if deleted, False if not found
        """
        key = self._generate_key(sport, team1, team2, date)
        result = self.cache.delete(key)
        logger.info(f"Deleted cache entry for key: {key}")
        return result
    
    def clear(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {count} cache entries")
        return count

