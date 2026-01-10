#!/usr/bin/env python3
"""Utility script to clear the cache"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app.services.cache_service import CacheService

def clear_cache():
    """Clear all cached data"""
    cache_service = CacheService()
    count = cache_service.clear()
    print(f"✓ Cleared {count} cache entries")
    print("Cache has been cleared. Try your comparison again!")

if __name__ == "__main__":
    clear_cache()
