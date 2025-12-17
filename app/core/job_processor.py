"""
Job processor that orchestrates the transcription pipeline.
Handles: Download -> Extract Audio -> Transcribe -> Format
"""
import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.config import get_settings
from app.db.database import JobDatabase
from app.models.job import ErrorInfo, Job, JobStage, JobStatus

from .audio_extractor import AudioExtractor
from .downloader import Downloader
from .formatter import OutputFormatter
from .whisper_manager import get_whisper_manager

logger = logging.getLogger(__name__)


class JobProcessor:
    """
    Orchestrates the complete transcription pipeline.

    Pipeline stages:
    1. Download (if URL provided)
    2. Extract audio (convert to Whisper format)
    3. Transcribe (using Whisper)
    4. Format (generate all output formats)

    Features:
    - Async job queue
    - Progress tracking
    - Webhook notifications
    - Automatic cleanup of intermediate files
    """

    def __init__(self, db: JobDatabase, data_dir: Path):
        """
        Initialize job processor.

        Args:
            db: Database instance for job persistence
            data_dir: Base directory for job data
        """
        self.db = db
        self.data_dir = Path(data_dir)
        self.jobs_dir = self.data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing = False
        self._current_job: Optional[str] = None

    async def start(self) -> None:
        """Start the job processing loop."""
        self._processing = True
        asyncio.create_task(self._process_loop())
        logger.info("Job processor started")

    async def stop(self) -> None:
        """Stop the job processing loop."""
        self._processing = False
        logger.info("Job processor stopped")

    async def submit_job(self, job: Job) -> None:
        """
        Submit a new job for processing.

        Args:
            job: Job to process
        """
        # Create job directory
        job_dir = self.jobs_dir / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "input").mkdir(exist_ok=True)
        (job_dir / "output").mkdir(exist_ok=True)
        (job_dir / "logs").mkdir(exist_ok=True)

        # Set expiration
        settings = get_settings()
        job.expires_at = datetime.utcnow() + timedelta(days=settings.job_retention_days)

        # Save to database
        await self.db.create_job(job)

        # Add to queue
        await self._queue.put(job.job_id)
        logger.info(f"Job {job.job_id} submitted to queue")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._processing:
            try:
                # Wait for next job with timeout
                try:
                    job_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                self._current_job = job_id
                await self._process_job(job_id)
                self._current_job = None

            except Exception as e:
                logger.exception(f"Error in process loop: {e}")

    async def _process_job(self, job_id: str) -> None:
        """
        Process a single job through the pipeline.

        Args:
            job_id: Job ID to process
        """
        job = await self.db.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job_dir = self.jobs_dir / job_id
        whisper_manager = get_whisper_manager()

        try:
            job.started_at = datetime.utcnow()

            # Stage 1: Download (if URL provided)
            if job.url:
                await self._update_stage(job, JobStage.DOWNLOADING)
                result = await self._download(job, job_dir)
                if "error" in result:
                    await self._fail_job(job, "download_error", result["error"])
                    return
                job.input_path = result["path"]
                job.duration_seconds = result.get("duration", 0)

            # Stage 2: Extract audio
            await self._update_stage(job, JobStage.EXTRACTING)
            result = await self._extract_audio(job, job_dir)
            if "error" in result:
                await self._fail_job(job, "extraction_error", result["error"])
                return
            job.audio_path = result["path"]

            # Stage 3: Transcribe
            await self._update_stage(job, JobStage.TRANSCRIBING)
            result = await self._transcribe(job, job_dir)
            if "error" in result:
                await self._fail_job(job, "transcription_error", result["error"])
                return
            transcription = result["transcription"]

            # Stage 4: Format outputs
            await self._update_stage(job, JobStage.FORMATTING)
            paths = await self._format_outputs(job, job_dir, transcription)
            job.output_json = paths["json"]
            job.output_txt = paths["txt"]
            job.output_srt = paths["srt"]
            job.output_md = paths["md"]

            # Complete
            await self._complete_job(job)

            # Start unload timer for Whisper model
            whisper_manager.start_unload_timer()

        except Exception as e:
            logger.exception(f"Job {job_id} failed with exception: {e}")
            await self._fail_job(job, "processing_error", str(e))

        finally:
            # Cleanup intermediate files
            await self._cleanup_intermediate(job_dir)

    async def _download(self, job: Job, job_dir: Path) -> dict:
        """Download video from URL."""
        downloader = Downloader(output_dir=job_dir / "input")

        def on_progress(value: int):
            asyncio.create_task(self._update_progress(job, value))

        return await downloader.download(
            job.url,
            job.job_id,
            progress_callback=on_progress,
        )

    async def _extract_audio(self, job: Job, job_dir: Path) -> dict:
        """Extract audio from video."""
        extractor = AudioExtractor(output_dir=job_dir / "input")

        input_path = job.input_path or job.filename
        if not input_path:
            return {"error": "No input file specified"}

        def on_progress(value: int):
            asyncio.create_task(self._update_progress(job, value))

        return await extractor.extract(
            input_path,
            job.job_id,
            progress_callback=on_progress,
        )

    async def _transcribe(self, job: Job, job_dir: Path) -> dict:
        """Transcribe audio using Whisper."""
        whisper_manager = get_whisper_manager()

        if not job.audio_path:
            return {"error": "No audio file to transcribe"}

        def on_progress(value: int):
            asyncio.create_task(self._update_progress(job, value))

        try:
            transcription = await whisper_manager.transcribe(
                job.audio_path,
                progress_callback=on_progress,
            )
            return {"transcription": transcription}
        except Exception as e:
            return {"error": str(e)}

    async def _format_outputs(
        self,
        job: Job,
        job_dir: Path,
        transcription: dict,
    ) -> dict[str, str]:
        """Format transcription into all output formats."""
        formatter = OutputFormatter(output_dir=job_dir / "output")

        metadata = {
            "job_id": job.job_id,
            "url": job.url,
            "duration": job.duration_seconds,
        }

        return formatter.format_all(transcription, job.job_id, metadata)

    async def _update_stage(self, job: Job, stage: JobStage) -> None:
        """Update job stage and reset progress."""
        job.stage = stage
        job.status = JobStatus(stage.value)
        job.progress = 0
        await self.db.update_job(job)
        logger.info(f"Job {job.job_id} stage: {stage.value}")

    async def _update_progress(self, job: Job, progress: int) -> None:
        """Update job progress."""
        job.progress = progress
        await self.db.update_job(job)

    async def _complete_job(self, job: Job) -> None:
        """Mark job as completed."""
        job.status = JobStatus.COMPLETED
        job.stage = JobStage.COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()
        await self.db.update_job(job)
        logger.info(f"Job {job.job_id} completed")

        # Send webhook if configured
        if job.webhook_url:
            await self._send_webhook(job)

    async def _fail_job(self, job: Job, error_type: str, message: str) -> None:
        """Mark job as failed."""
        job.status = JobStatus.FAILED
        job.stage = JobStage.FAILED
        job.failed_at = datetime.utcnow()
        job.error = ErrorInfo(type=error_type, message=message)
        await self.db.update_job(job)
        logger.error(f"Job {job.job_id} failed: {error_type} - {message}")

        # Send webhook if configured
        if job.webhook_url:
            await self._send_webhook(job)

    async def _send_webhook(self, job: Job) -> None:
        """Send webhook notification."""
        if not job.webhook_url:
            return

        payload = {
            "event": f"job.{job.status.value}",
            "job_id": job.job_id,
            "status": job.status.value,
        }

        if job.status == JobStatus.COMPLETED:
            payload["download_urls"] = {
                "json": f"/api/jobs/{job.job_id}/download?format=json",
                "txt": f"/api/jobs/{job.job_id}/download?format=txt",
                "srt": f"/api/jobs/{job.job_id}/download?format=srt",
                "md": f"/api/jobs/{job.job_id}/download?format=md",
            }

        if job.error:
            payload["error"] = job.error.model_dump()

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    job.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
            logger.info(f"Webhook sent for job {job.job_id}")
        except Exception as e:
            logger.error(f"Webhook failed for job {job.job_id}: {e}")

    async def _cleanup_intermediate(self, job_dir: Path) -> None:
        """Remove intermediate files (audio WAV)."""
        input_dir = job_dir / "input"
        for wav_file in input_dir.glob("*.wav"):
            try:
                wav_file.unlink()
                logger.debug(f"Removed intermediate file: {wav_file}")
            except Exception as e:
                logger.warning(f"Failed to remove {wav_file}: {e}")

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job and all its data.

        Args:
            job_id: Job ID to delete

        Returns:
            True if deleted successfully
        """
        job_dir = self.jobs_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

        await self.db.delete_job(job_id)
        logger.info(f"Job {job_id} deleted")
        return True

    async def cleanup_expired_jobs(self) -> int:
        """
        Delete all expired jobs.

        Returns:
            Number of jobs deleted
        """
        expired = await self.db.get_expired_jobs()
        for job in expired:
            await self.delete_job(job.job_id)
        return len(expired)

    def get_queue_status(self) -> dict:
        """Get current queue status."""
        return {
            "queue_size": self._queue.qsize(),
            "current_job": self._current_job,
            "processing": self._processing,
        }
