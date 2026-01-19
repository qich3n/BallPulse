"""
Health Check Routes

Provides health check endpoints for monitoring application status.
Includes basic health check and detailed health check with dependency status.
"""

import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, Field
import httpx

from ..services.rate_limiter import limiter, RATE_LIMITS
from ..services.cache_service import CacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time
APP_START_TIME = time.time()


class DependencyStatus(BaseModel):
    """Status of a single dependency"""
    name: str
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    latency_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    message: Optional[str] = Field(None, description="Additional status information")


class SystemInfo(BaseModel):
    """System information"""
    python_version: str
    platform: str
    memory_usage_mb: Optional[float] = None
    uptime_seconds: float


class DetailedHealthResponse(BaseModel):
    """Detailed health check response"""
    status: str = Field(..., description="Overall status: 'healthy', 'degraded', or 'unhealthy'")
    timestamp: str
    version: str = "1.0.0"
    uptime_seconds: float
    dependencies: Dict[str, DependencyStatus]
    system: SystemInfo


def get_memory_usage_mb() -> Optional[float]:
    """Get current memory usage in MB"""
    try:
        import resource
        # Get memory usage in bytes, convert to MB
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # On macOS, ru_maxrss is in bytes; on Linux, it's in KB
        if sys.platform == 'darwin':
            return usage / (1024 * 1024)  # bytes to MB
        else:
            return usage / 1024  # KB to MB
    except Exception:
        return None


async def check_cache_health() -> DependencyStatus:
    """Check cache service health"""
    start_time = time.time()
    try:
        cache = CacheService()
        # Try a simple set/get operation
        test_key = "__health_check_test__"
        cache.cache.set(test_key, "test_value", expire=10)
        result = cache.cache.get(test_key)
        cache.cache.delete(test_key)
        
        latency = (time.time() - start_time) * 1000
        
        if result == "test_value":
            return DependencyStatus(
                name="cache",
                status="healthy",
                latency_ms=round(latency, 2),
                message="Cache read/write operational"
            )
        else:
            return DependencyStatus(
                name="cache",
                status="degraded",
                latency_ms=round(latency, 2),
                message="Cache returned unexpected value"
            )
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return DependencyStatus(
            name="cache",
            status="unhealthy",
            latency_ms=round(latency, 2),
            message=f"Cache error: {str(e)}"
        )


async def check_reddit_api_health() -> DependencyStatus:
    """Check Reddit API availability"""
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://www.reddit.com/r/nba.json?limit=1",
                headers={"User-Agent": "BallPulse/1.0 HealthCheck"}
            )
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return DependencyStatus(
                    name="reddit_api",
                    status="healthy",
                    latency_ms=round(latency, 2),
                    message="Reddit API accessible"
                )
            elif response.status_code == 429:
                return DependencyStatus(
                    name="reddit_api",
                    status="degraded",
                    latency_ms=round(latency, 2),
                    message="Reddit API rate limited"
                )
            else:
                return DependencyStatus(
                    name="reddit_api",
                    status="degraded",
                    latency_ms=round(latency, 2),
                    message=f"Reddit API returned status {response.status_code}"
                )
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        return DependencyStatus(
            name="reddit_api",
            status="degraded",
            latency_ms=round(latency, 2),
            message="Reddit API timeout"
        )
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return DependencyStatus(
            name="reddit_api",
            status="unhealthy",
            latency_ms=round(latency, 2),
            message=f"Reddit API error: {str(e)}"
        )


async def check_nba_api_health() -> DependencyStatus:
    """Check NBA API availability (basic connectivity check)"""
    start_time = time.time()
    try:
        # Just check if we can import and access the teams list
        from nba_api.stats.static import teams
        nba_teams = teams.get_teams()
        latency = (time.time() - start_time) * 1000
        
        if nba_teams and len(nba_teams) == 30:
            return DependencyStatus(
                name="nba_api",
                status="healthy",
                latency_ms=round(latency, 2),
                message=f"NBA API accessible ({len(nba_teams)} teams loaded)"
            )
        else:
            return DependencyStatus(
                name="nba_api",
                status="degraded",
                latency_ms=round(latency, 2),
                message=f"NBA API returned unexpected team count: {len(nba_teams) if nba_teams else 0}"
            )
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return DependencyStatus(
            name="nba_api",
            status="unhealthy",
            latency_ms=round(latency, 2),
            message=f"NBA API error: {str(e)}"
        )


@router.get("")
@limiter.limit(RATE_LIMITS["health"])
async def health_check(request: Request):
    """
    Basic health check endpoint.
    Returns simple healthy status for load balancers and quick checks.
    """
    logger.debug("Basic health check requested")
    return {"status": "healthy"}


@router.get("/detailed", response_model=DetailedHealthResponse)
@limiter.limit(RATE_LIMITS["health"])
async def detailed_health_check(
    request: Request,
    check_external: bool = Query(
        default=False,
        description="Whether to check external APIs (Reddit, NBA). Slower but more comprehensive."
    )
) -> DetailedHealthResponse:
    """
    Detailed health check with dependency status.
    
    Checks:
    - Cache service connectivity
    - External APIs (optional, controlled by check_external parameter)
    - System information (memory, uptime)
    
    Use `check_external=true` for comprehensive checks, but note it will be slower.
    """
    logger.info("Detailed health check requested (check_external=%s)", check_external)
    
    dependencies: Dict[str, DependencyStatus] = {}
    
    # Always check cache
    cache_status = await check_cache_health()
    dependencies["cache"] = cache_status
    
    # Optionally check external APIs
    if check_external:
        reddit_status = await check_reddit_api_health()
        dependencies["reddit_api"] = reddit_status
        
        nba_status = await check_nba_api_health()
        dependencies["nba_api"] = nba_status
    
    # Determine overall status
    statuses = [dep.status for dep in dependencies.values()]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
    
    # System info
    uptime = time.time() - APP_START_TIME
    memory_mb = get_memory_usage_mb()
    
    system_info = SystemInfo(
        python_version=sys.version.split()[0],
        platform=sys.platform,
        memory_usage_mb=round(memory_mb, 2) if memory_mb else None,
        uptime_seconds=round(uptime, 2)
    )
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="1.0.0",
        uptime_seconds=round(uptime, 2),
        dependencies=dependencies,
        system=system_info
    )


@router.get("/ready")
@limiter.limit(RATE_LIMITS["health"])
async def readiness_check(request: Request):
    """
    Readiness probe for Kubernetes/container orchestration.
    Returns 200 if the application is ready to serve traffic.
    """
    # Check if critical dependencies are available
    cache_status = await check_cache_health()
    
    if cache_status.status == "unhealthy":
        return {"status": "not_ready", "reason": "Cache unavailable"}
    
    return {"status": "ready"}


@router.get("/live")
@limiter.limit(RATE_LIMITS["health"])
async def liveness_check(request: Request):
    """
    Liveness probe for Kubernetes/container orchestration.
    Returns 200 if the application process is alive.
    """
    return {"status": "alive", "uptime_seconds": round(time.time() - APP_START_TIME, 2)}

