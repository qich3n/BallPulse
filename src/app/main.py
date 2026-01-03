import logging
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routes import health, compare

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="BallPulse", version="1.0.0")

# Include routers
app.include_router(health.router)
app.include_router(compare.router)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # Directory might not exist, that's okay
    pass

@app.get("/")
async def read_root():
    """Serve the frontend"""
    try:
        return FileResponse("static/index.html")
    except FileNotFoundError:
        return {"message": "Frontend not found. API is available at /docs"}

@app.on_event("startup")
async def startup_event():
    logger.info("BallPulse application started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("BallPulse application shutting down")

