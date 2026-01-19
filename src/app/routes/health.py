import logging
from fastapi import APIRouter, Request
from ..services.rate_limiter import limiter, RATE_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
@limiter.limit(RATE_LIMITS["health"])
async def health_check(request: Request):
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "healthy"}

