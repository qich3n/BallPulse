import logging
import hashlib
import json
from typing import Optional, Any
import diskcache
from ..config import cfg

logger = logging.getLogger(__name__)


class _DiskCacheBackend:
    def __init__(self, cache_dir: str):
        self.cache = diskcache.Cache(cache_dir)

    def get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)

    def set(self, key: str, value: Any, ttl: int) -> bool:
        return bool(self.cache.set(key, value, expire=ttl))

    def delete(self, key: str) -> bool:
        return bool(self.cache.delete(key))

    def clear(self) -> int:
        count = len(self.cache)
        self.cache.clear()
        return count


class _RedisCacheBackend:
    def __init__(self, redis_url: str):
        try:
            from redis import Redis  # type: ignore
        except ImportError as e:
            raise RuntimeError("Redis backend requested but redis package is not installed") from e
        self.redis = Redis.from_url(redis_url)

    def get(self, key: str) -> Optional[Any]:
        raw = self.redis.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Failed to decode redis cache payload for key=%s", key)
            return None

    def set(self, key: str, value: Any, ttl: int) -> bool:
        payload = json.dumps(value, default=self._serialize)
        return bool(self.redis.setex(key, ttl, payload))

    def delete(self, key: str) -> bool:
        return bool(self.redis.delete(key))

    def clear(self) -> int:
        # We intentionally avoid broad redis flush operations here.
        return 0

    @staticmethod
    def _serialize(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        raise TypeError(f"Object of type {type(value)} is not JSON serializable")


class CacheService:
    """Cache service with optional Redis backend and diskcache fallback."""
    
    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 3600, backend: Optional[str] = None):
        """
        Initialize cache service
        
        Args:
            cache_dir: Directory for cache storage
            default_ttl: Default TTL in seconds (default: 1 hour)
            backend: "disk" or "redis". Defaults to config/env-driven selection.
        """
        self.default_ttl = default_ttl
        cache_cfg = cfg.get("cache", {})
        selected_backend = (backend or cache_cfg.get("backend", "disk")).lower()

        if selected_backend == "redis":
            redis_url = cache_cfg.get("redis_url")
            if redis_url:
                try:
                    self.backend = _RedisCacheBackend(redis_url)
                    logger.info("Cache service initialized with redis backend")
                    return
                except (RuntimeError, ValueError, TypeError) as e:
                    logger.warning("Failed to initialize redis cache backend: %s; falling back to diskcache", e)
            else:
                logger.warning("Redis cache backend selected but redis_url missing; falling back to diskcache")

        self.backend = _DiskCacheBackend(cache_dir=cache_dir)
        logger.info("Cache service initialized with diskcache backend cache_dir=%s default_ttl=%ss", cache_dir, default_ttl)
    
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
        value = self.backend.get(key)
        if value is not None:
            logger.info("Cache hit for key: %s", key)
        else:
            logger.info("Cache miss for key: %s", key)
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
        result = self.backend.set(key, value, ttl=ttl)
        logger.info("Cached value for key: %s with TTL: %ss", key, ttl)
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
        result = self.backend.delete(key)
        logger.info("Deleted cache entry for key: %s", key)
        return result
    
    def clear(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        count = self.backend.clear()
        logger.info("Cleared %d cache entries", count)
        return count

