"""
Health check endpoint.
"""
from fastapi import APIRouter

from app.api.dependencies import get_processor
from app.core.whisper_manager import get_whisper_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        Health status with Whisper and queue info
    """
    whisper_manager = get_whisper_manager()
    processor = get_processor()

    return {
        "status": "healthy",
        "whisper": whisper_manager.get_status(),
        "queue": processor.get_queue_status(),
    }
