import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .routes import health, compare, teams, history, matchup, espn, games
from .services.rate_limiter import limiter

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Modern lifespan context manager for startup/shutdown events.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup
    logger.info("BallPulse application starting up...")
    logger.info("Log level: %s", log_level)
    logger.info("BallPulse application started successfully")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("BallPulse application shutting down...")
    logger.info("BallPulse application shutdown complete")


app = FastAPI(
    title="BallPulse",
    version="1.0.0",
    description="AI-powered NBA matchup predictor with sentiment analysis",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(health.router)
app.include_router(compare.router)
app.include_router(teams.router)
app.include_router(history.router)
app.include_router(matchup.router)
app.include_router(espn.router)
app.include_router(games.router)

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


@app.head("/")
async def read_root_head():
    """Handle HEAD requests for the root path (used by uptime monitors / Render health checks)"""
    return Response(status_code=200)

