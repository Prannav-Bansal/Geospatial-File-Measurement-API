"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.config import UPLOAD_DIR
from app.routers.files import router as files_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Initializing database...")
    await init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)
    logger.info("Application started successfully.")
    yield
    # Shutdown
    logger.info("Application shutting down.")


app = FastAPI(
    title="Geospatial File Measurement API",
    description=(
        "Upload geospatial files (Shapefile .zip or .kml), "
        "extract features, and calculate measurements (area, length) "
        "with automatic CRS transformation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount router
app.include_router(files_router)


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "Geospatial File Measurement API",
        "status": "running",
        "docs": "/docs",
    }
