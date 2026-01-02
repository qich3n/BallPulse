import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])

class CompareRequest(BaseModel):
    """Request model for compare endpoint"""
    pass

class CompareResponse(BaseModel):
    """Response model for compare endpoint"""
    status: str

@router.post("")
async def compare(request: CompareRequest):
    """Compare endpoint (stub)"""
    logger.info("Compare endpoint called")
    return CompareResponse(status="ok")

