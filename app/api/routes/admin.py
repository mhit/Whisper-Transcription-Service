"""
Admin API endpoints.
Requires admin password authentication.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.api.dependencies import get_db, get_processor
from app.config import get_settings
from app.core.whisper_manager import get_whisper_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def verify_admin_password(password: Optional[str]) -> None:
    """
    Verify admin password.

    Args:
        password: Password from header

    Raises:
        HTTPException: If password is invalid
    """
    settings = get_settings()

    if not password or password != settings.admin_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin password",
        )


@router.get("/stats")
async def get_stats(
    x_admin_password: Optional[str] = Header(None),
) -> dict:
    """
    Get system statistics.

    Args:
        x_admin_password: Admin password header

    Returns:
        System statistics
    """
    verify_admin_password(x_admin_password)

    db = get_db()
    processor = get_processor()
    whisper_manager = get_whisper_manager()

    jobs = await db.list_jobs(limit=1000)

    # Count by status
    status_counts = {}
    for job in jobs:
        status = job.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_jobs": len(jobs),
        "status_counts": status_counts,
        "queue": processor.get_queue_status(),
        "whisper": whisper_manager.get_status(),
    }


@router.post("/cleanup")
async def cleanup_expired(
    x_admin_password: Optional[str] = Header(None),
) -> dict:
    """
    Clean up expired jobs.

    Args:
        x_admin_password: Admin password header

    Returns:
        Number of jobs deleted
    """
    verify_admin_password(x_admin_password)

    processor = get_processor()
    deleted_count = await processor.cleanup_expired_jobs()

    logger.info(f"Cleaned up {deleted_count} expired jobs")

    return {"deleted_count": deleted_count}


@router.post("/model/unload")
async def unload_model(
    x_admin_password: Optional[str] = Header(None),
) -> dict:
    """
    Manually unload Whisper model.

    Args:
        x_admin_password: Admin password header

    Returns:
        Success message
    """
    verify_admin_password(x_admin_password)

    whisper_manager = get_whisper_manager()
    await whisper_manager.unload_model()

    logger.info("Whisper model unloaded via admin API")

    return {"message": "Model unloaded successfully"}


@router.post("/model/load")
async def load_model(
    x_admin_password: Optional[str] = Header(None),
) -> dict:
    """
    Manually load Whisper model.

    Args:
        x_admin_password: Admin password header

    Returns:
        Success message
    """
    verify_admin_password(x_admin_password)

    whisper_manager = get_whisper_manager()
    await whisper_manager.load_model()

    logger.info("Whisper model loaded via admin API")

    return {"message": "Model loaded successfully"}
