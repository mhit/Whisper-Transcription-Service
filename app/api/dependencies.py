"""
API dependencies for dependency injection.
"""
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.core.job_processor import JobProcessor
from app.core.whisper_manager import get_whisper_manager
from app.db.database import JobDatabase

# Global instances
_db: Optional[JobDatabase] = None
_processor: Optional[JobProcessor] = None


async def init_dependencies() -> None:
    """Initialize global dependencies."""
    global _db, _processor

    settings = get_settings()
    data_dir = Path(settings.data_dir)

    # Initialize database
    _db = JobDatabase(data_dir / "jobs.db")
    await _db.init()

    # Initialize processor
    _processor = JobProcessor(_db, data_dir)
    await _processor.start()


async def shutdown_dependencies() -> None:
    """Shutdown global dependencies."""
    global _db, _processor

    if _processor:
        await _processor.stop()
        _processor = None

    if _db:
        await _db.close()
        _db = None


def get_db() -> JobDatabase:
    """Get database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_processor() -> JobProcessor:
    """Get job processor instance."""
    if _processor is None:
        raise RuntimeError("Processor not initialized")
    return _processor
