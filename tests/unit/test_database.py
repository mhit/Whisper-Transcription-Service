"""
Unit tests for database module.
TDD: Tests written before implementation.
"""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from app.config import generate_job_id
from app.models.job import Job, JobStatus, JobStage


class TestGenerateJobId:
    """Tests for job ID generation."""

    def test_generate_job_id_format(self):
        """Job ID should follow JOB-XXXXXX format."""
        job_id = generate_job_id()
        assert job_id.startswith("JOB-")
        assert len(job_id) == 10  # JOB- + 6 chars

    def test_generate_job_id_unique(self):
        """Generated job IDs should be unique."""
        ids = {generate_job_id() for _ in range(100)}
        assert len(ids) == 100  # All should be unique

    def test_generate_job_id_alphanumeric(self):
        """Job ID suffix should be alphanumeric uppercase."""
        job_id = generate_job_id()
        suffix = job_id[4:]  # Remove "JOB-"
        assert suffix.isalnum()
        assert suffix.isupper() or suffix.isdigit()


class TestJobModel:
    """Tests for Job model."""

    def test_job_default_values(self):
        """Job should have correct default values."""
        job = Job(job_id="JOB-TEST01")
        assert job.status == JobStatus.QUEUED
        assert job.stage == JobStage.QUEUED
        assert job.progress == 0
        assert job.url is None
        assert job.error is None

    def test_job_to_response(self):
        """Job should convert to response correctly."""
        job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.COMPLETED,
            stage=JobStage.COMPLETED,
            progress=100,
        )
        response = job.to_response(base_url="http://localhost:8000")
        assert response.job_id == "JOB-TEST01"
        assert response.status == JobStatus.COMPLETED
        assert response.download_urls is not None
        assert "json" in response.download_urls

    def test_job_to_response_no_download_urls_when_not_completed(self):
        """Download URLs should be None when job is not completed."""
        job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.TRANSCRIBING,
            stage=JobStage.TRANSCRIBING,
            progress=50,
        )
        response = job.to_response()
        assert response.download_urls is None


# Database tests will be added after JobDatabase implementation
class TestJobDatabase:
    """Tests for JobDatabase class."""

    @pytest_asyncio.fixture
    async def db(self, tmp_path: Path):
        """Create a temporary database for testing."""
        from app.db.database import JobDatabase

        db_path = tmp_path / "test.db"
        database = JobDatabase(db_path)
        await database.initialize()
        yield database
        await database.close()

    @pytest.mark.asyncio
    async def test_create_job(self, db):
        """Should create a new job in the database."""
        job_id = generate_job_id()
        job = Job(job_id=job_id, url="https://example.com/video.mp4")

        await db.create_job(job)
        retrieved = await db.get_job(job_id)

        assert retrieved is not None
        assert retrieved.job_id == job_id
        assert retrieved.url == "https://example.com/video.mp4"

    @pytest.mark.asyncio
    async def test_update_job_status(self, db):
        """Should update job status."""
        job_id = generate_job_id()
        job = Job(job_id=job_id)
        await db.create_job(job)

        job.status = JobStatus.TRANSCRIBING
        job.stage = JobStage.TRANSCRIBING
        job.progress = 50
        await db.update_job(job)

        retrieved = await db.get_job(job_id)
        assert retrieved.status == JobStatus.TRANSCRIBING
        assert retrieved.progress == 50

    @pytest.mark.asyncio
    async def test_delete_job(self, db):
        """Should delete a job from the database."""
        job_id = generate_job_id()
        job = Job(job_id=job_id)
        await db.create_job(job)

        await db.delete_job(job_id)
        retrieved = await db.get_job(job_id)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, db):
        """Should list all jobs."""
        for i in range(5):
            job = Job(job_id=f"JOB-TEST0{i}")
            await db.create_job(job)

        jobs = await db.list_jobs()
        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, db):
        """Should filter jobs by status."""
        for i in range(3):
            job = Job(job_id=f"JOB-COMP0{i}", status=JobStatus.COMPLETED)
            await db.create_job(job)

        for i in range(2):
            job = Job(job_id=f"JOB-FAIL0{i}", status=JobStatus.FAILED)
            await db.create_job(job)

        completed = await db.list_jobs(status=JobStatus.COMPLETED)
        failed = await db.list_jobs(status=JobStatus.FAILED)

        assert len(completed) == 3
        assert len(failed) == 2

    @pytest.mark.asyncio
    async def test_get_expired_jobs(self, db):
        """Should return expired jobs."""
        # Create an expired job
        expired_job = Job(
            job_id="JOB-EXPIRD",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        await db.create_job(expired_job)

        # Create a non-expired job
        valid_job = Job(
            job_id="JOB-VALID1",
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        await db.create_job(valid_job)

        expired = await db.get_expired_jobs()
        assert len(expired) == 1
        assert expired[0].job_id == "JOB-EXPIRD"

    @pytest.mark.asyncio
    async def test_get_queued_jobs(self, db):
        """Should return queued jobs in order."""
        for i in range(3):
            job = Job(job_id=f"JOB-QUEUE{i}", status=JobStatus.QUEUED)
            await db.create_job(job)
            await asyncio.sleep(0.01)  # Ensure different timestamps

        queued = await db.get_queued_jobs()
        assert len(queued) == 3
        # Should be in FIFO order (oldest first)
        assert queued[0].job_id == "JOB-QUEUE0"
