"""
Rate Limiter Service

Provides rate limiting functionality for API endpoints using slowapi.
Protects against abuse and ensures fair usage of the API.
"""

import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.
    Handles both direct connections and proxied requests.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address string
    """
    # Check for forwarded header (when behind a proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()
    
    # Check for real IP header (common with nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct connection IP
    return get_remote_address(request)


# Initialize the limiter with client IP as the key
limiter = Limiter(key_func=get_client_ip)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    
    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception
        
    Returns:
        JSON response with error details
    """
    logger.warning(
        f"Rate limit exceeded for IP: {get_client_ip(request)}, "
        f"endpoint: {request.url.path}, limit: {exc.detail}"
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"Too many requests. {exc.detail}",
            "retry_after": "Please wait before making more requests"
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(exc.detail)
        }
    )


# Rate limit configurations for different endpoint types
RATE_LIMITS = {
    "default": "60/minute",      # Default: 60 requests per minute
    "compare": "10/minute",       # Compare endpoint: 10 per minute (expensive operation)
    "health": "120/minute",       # Health checks: more lenient
    "teams": "30/minute",         # Team data: moderate
    "history": "30/minute",       # History: moderate
}


def get_rate_limit(endpoint_type: str) -> str:
    """
    Get rate limit string for an endpoint type.
    
    Args:
        endpoint_type: Type of endpoint (compare, health, teams, etc.)
        
    Returns:
        Rate limit string (e.g., "10/minute")
    """
    return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])
