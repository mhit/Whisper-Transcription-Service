"""
Job management API endpoints.
"""
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import get_db, get_processor
from app.config import generate_job_id, get_settings
from app.models.job import Job, JobResponse, JobStage, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])


@router.post("/jobs", status_code=201)
async def create_job(
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    webhook_url: Optional[str] = Form(None),
) -> dict:
    """
    Create a new transcription job.

    Either url or file must be provided.

    Args:
        url: Video URL to download and transcribe
        file: Video file to upload and transcribe
        webhook_url: Optional webhook URL for notifications

    Returns:
        Job response with job_id and status
    """
    # Validate input
    if not url and not file:
        raise HTTPException(
            status_code=400,
            detail="Either 'url' or 'file' must be provided",
        )

    job_id = generate_job_id()
    settings = get_settings()
    processor = get_processor()

    # Handle file upload
    input_path = None
    if file:
        # Create job directory
        job_dir = Path(settings.data_dir) / "jobs" / job_id / "input"
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file
        file_path = job_dir / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        input_path = str(file_path)

    # Create job
    job = Job(
        job_id=job_id,
        url=url,
        input_path=input_path,
        filename=file.filename if file else None,
        webhook_url=webhook_url,
        status=JobStatus.QUEUED,
        stage=JobStage.QUEUED,
    )

    # Submit to processor
    await processor.submit_job(job)

    logger.info(f"Job {job_id} created")

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job submitted successfully",
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JobResponse:
    """
    Get job status and details.

    Args:
        job_id: Job ID

    Returns:
        Job response with status and progress
    """
    db = get_db()
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_response()


@router.get("/jobs/{job_id}/download")
async def download_job_result(
    job_id: str,
    format: str = Query("json", regex="^(json|txt|srt|md)$"),
) -> FileResponse:
    """
    Download job result in specified format.

    Args:
        job_id: Job ID
        format: Output format (json, txt, srt, md)

    Returns:
        File download response
    """
    db = get_db()
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job.status.value}",
        )

    # Get output path based on format
    output_path = None
    content_type = "application/octet-stream"
    filename = f"{job_id}.{format}"

    if format == "json":
        output_path = job.output_json
        content_type = "application/json"
    elif format == "txt":
        output_path = job.output_txt
        content_type = "text/plain; charset=utf-8"
    elif format == "srt":
        output_path = job.output_srt
        content_type = "text/plain; charset=utf-8"
    elif format == "md":
        output_path = job.output_md
        content_type = "text/markdown; charset=utf-8"

    if not output_path or not Path(output_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"Output file not found for format: {format}",
        )

    return FileResponse(
        path=output_path,
        media_type=content_type,
        filename=filename,
    )


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str) -> None:
    """
    Delete a job and all its data.

    Args:
        job_id: Job ID
    """
    db = get_db()
    processor = get_processor()

    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await processor.delete_job(job_id)
    logger.info(f"Job {job_id} deleted via API")


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
) -> dict:
    """
    List jobs with pagination.

    Args:
        limit: Maximum number of jobs to return
        offset: Offset for pagination
        status: Filter by status

    Returns:
        List of jobs with pagination info
    """
    db = get_db()

    # Get jobs from database
    jobs = await db.list_jobs(limit=limit, offset=offset)

    # Filter by status if provided
    if status:
        jobs = [j for j in jobs if j.status.value == status]

    return {
        "jobs": [job.to_response().model_dump() for job in jobs],
        "total": len(jobs),
        "limit": limit,
        "offset": offset,
    }
