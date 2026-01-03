import logging
from fastapi import FastAPI
from .routes import health, compare

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="BallPulse", version="1.0.0")

# Include routers
app.include_router(health.router)
app.include_router(compare.router)

@app.on_event("startup")
async def startup_event():
    logger.info("BallPulse application started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("BallPulse application shutting down")

