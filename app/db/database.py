"""
SQLite database management for job persistence.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from app.models.job import ErrorInfo, Job, JobStage, JobStatus


class JobDatabase:
    """Async SQLite database for job management."""

    def __init__(self, db_path: Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                url TEXT,
                filename TEXT,
                webhook_url TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                failed_at TEXT,
                expires_at TEXT,
                duration_seconds INTEGER,
                error_json TEXT,
                input_path TEXT,
                audio_path TEXT,
                output_json TEXT,
                output_txt TEXT,
                output_srt TEXT,
                output_md TEXT,
                log_path TEXT
            )
        """)
        await self._connection.commit()

    def _job_to_row(self, job: Job) -> dict:
        """Convert Job model to database row."""
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "stage": job.stage.value,
            "progress": job.progress,
            "url": job.url,
            "filename": job.filename,
            "webhook_url": job.webhook_url,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "failed_at": job.failed_at.isoformat() if job.failed_at else None,
            "expires_at": job.expires_at.isoformat() if job.expires_at else None,
            "duration_seconds": job.duration_seconds,
            "error_json": json.dumps(job.error.model_dump()) if job.error else None,
            "input_path": job.input_path,
            "audio_path": job.audio_path,
            "output_json": job.output_json,
            "output_txt": job.output_txt,
            "output_srt": job.output_srt,
            "output_md": job.output_md,
            "log_path": job.log_path,
        }

    def _row_to_job(self, row: aiosqlite.Row) -> Job:
        """Convert database row to Job model."""
        error = None
        if row["error_json"]:
            error_data = json.loads(row["error_json"])
            error = ErrorInfo(**error_data)

        return Job(
            job_id=row["job_id"],
            status=JobStatus(row["status"]),
            stage=JobStage(row["stage"]),
            progress=row["progress"],
            url=row["url"],
            filename=row["filename"],
            webhook_url=row["webhook_url"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            failed_at=datetime.fromisoformat(row["failed_at"]) if row["failed_at"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            duration_seconds=row["duration_seconds"],
            error=error,
            input_path=row["input_path"],
            audio_path=row["audio_path"],
            output_json=row["output_json"],
            output_txt=row["output_txt"],
            output_srt=row["output_srt"],
            output_md=row["output_md"],
            log_path=row["log_path"],
        )

    async def create_job(self, job: Job) -> None:
        """
        Create a new job in the database.

        Args:
            job: Job model to insert
        """
        row = self._job_to_row(job)
        columns = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())

        await self._connection.execute(
            f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
            row,
        )
        await self._connection.commit()

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job model or None if not found
        """
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    async def update_job(self, job: Job) -> None:
        """
        Update an existing job in the database.

        Args:
            job: Job model with updated values
        """
        row = self._job_to_row(job)
        set_clause = ", ".join(f"{k} = :{k}" for k in row.keys() if k != "job_id")

        await self._connection.execute(
            f"UPDATE jobs SET {set_clause} WHERE job_id = :job_id",
            row,
        )
        await self._connection.commit()

    async def delete_job(self, job_id: str) -> None:
        """
        Delete a job from the database.

        Args:
            job_id: Job ID to delete
        """
        await self._connection.execute(
            "DELETE FROM jobs WHERE job_id = ?",
            (job_id,),
        )
        await self._connection.commit()

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            List of Job models
        """
        query = "SELECT * FROM jobs"
        params: list = []

        if status:
            query += " WHERE status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_expired_jobs(self) -> list[Job]:
        """
        Get all jobs that have expired.

        Returns:
            List of expired Job models
        """
        now = datetime.utcnow().isoformat()
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_queued_jobs(self) -> list[Job]:
        """
        Get all queued jobs in FIFO order.

        Returns:
            List of queued Job models (oldest first)
        """
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
            (JobStatus.QUEUED.value,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_processing_jobs(self) -> list[Job]:
        """
        Get all jobs currently being processed.

        Returns:
            List of in-progress Job models
        """
        processing_statuses = [
            JobStatus.DOWNLOADING.value,
            JobStatus.EXTRACTING.value,
            JobStatus.TRANSCRIBING.value,
            JobStatus.FORMATTING.value,
        ]
        placeholders = ", ".join("?" for _ in processing_statuses)

        async with self._connection.execute(
            f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY started_at ASC",
            processing_statuses,
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """
        Count total jobs with optional status filter.

        Args:
            status: Filter by status (optional)

        Returns:
            Number of jobs
        """
        if status:
            query = "SELECT COUNT(*) FROM jobs WHERE status = ?"
            params = (status.value,)
        else:
            query = "SELECT COUNT(*) FROM jobs"
            params = ()

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0]
