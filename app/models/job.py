"""
Job model definitions for Whisper Transcription Service.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStage(str, Enum):
    """Current processing stage."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorInfo(BaseModel):
    """Error information for failed jobs."""

    type: str
    message: str
    details: Optional[str] = None


class JobCreate(BaseModel):
    """Request model for creating a new job."""

    url: Optional[str] = None
    webhook_url: Optional[str] = None


class JobResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    status: JobStatus
    stage: JobStage
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    expires_at: datetime
    duration_seconds: Optional[int] = None
    error: Optional[ErrorInfo] = None
    download_urls: Optional[dict[str, str]] = None


class Job(BaseModel):
    """Internal job model with all fields."""

    job_id: str
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress: int = 0

    # Input
    url: Optional[str] = None
    filename: Optional[str] = None
    webhook_url: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Results
    duration_seconds: Optional[int] = None
    error: Optional[ErrorInfo] = None

    # Paths (relative to job directory)
    input_path: Optional[str] = None
    audio_path: Optional[str] = None
    output_json: Optional[str] = None
    output_txt: Optional[str] = None
    output_srt: Optional[str] = None
    output_md: Optional[str] = None
    log_path: Optional[str] = None

    def to_response(self, base_url: str = "") -> JobResponse:
        """Convert to API response model."""
        download_urls = None
        if self.status == JobStatus.COMPLETED:
            download_urls = {
                "json": f"{base_url}/api/jobs/{self.job_id}/download?format=json",
                "txt": f"{base_url}/api/jobs/{self.job_id}/download?format=txt",
                "srt": f"{base_url}/api/jobs/{self.job_id}/download?format=srt",
                "md": f"{base_url}/api/jobs/{self.job_id}/download?format=md",
            }

        return JobResponse(
            job_id=self.job_id,
            status=self.status,
            stage=self.stage,
            progress=self.progress,
            created_at=self.created_at,
            completed_at=self.completed_at,
            failed_at=self.failed_at,
            expires_at=self.expires_at or self.created_at,
            duration_seconds=self.duration_seconds,
            error=self.error,
            download_urls=download_urls,
        )
