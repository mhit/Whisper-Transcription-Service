"""
Main FastAPI application.
Whisper Transcription Service with Web UI and REST API.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import init_dependencies, shutdown_dependencies
from app.api.routes import admin, health, jobs, web
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Whisper Transcription Service...")
    settings = get_settings()

    logger.info(f"Whisper model: {settings.whisper_model}")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Job retention: {settings.job_retention_days} days")

    await init_dependencies()
    logger.info("Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Whisper Transcription Service...")
    await shutdown_dependencies()
    logger.info("Service stopped")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Whisper Transcription Service",
        description="Video/Audio transcription service with Japanese optimization",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for API access
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # API routes
    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(admin.router, prefix="/api/admin")

    # Web UI routes
    app.include_router(web.router)

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
