"""
Unit tests for REST API routes.
TDD: Tests written before implementation.
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestJobsAPI:
    """Tests for /api/jobs endpoints."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""
        from app.api.routes.jobs import router
        from app.api.routes.health import router as health_router

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.include_router(health_router, prefix="/api")
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_processor(self):
        """Create a mock job processor."""
        processor = AsyncMock()
        processor.submit_job = AsyncMock()
        processor.get_queue_status = MagicMock(return_value={
            "queue_size": 0,
            "current_job": None,
            "processing": True,
        })
        return processor

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = AsyncMock()
        db.get_job = AsyncMock(return_value=None)
        db.list_jobs = AsyncMock(return_value=[])
        db.delete_job = AsyncMock()
        return db

    def test_create_job_with_url(self, client, mock_processor, mock_db):
        """Should create a job from URL."""
        with patch("app.api.routes.jobs.get_processor", return_value=mock_processor):
            with patch("app.api.routes.jobs.get_db", return_value=mock_db):
                response = client.post(
                    "/api/jobs",
                    json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                )

                assert response.status_code == 201
                data = response.json()
                assert "job_id" in data
                assert data["job_id"].startswith("JOB-")
                assert data["status"] == "queued"

    def test_create_job_with_file_upload(self, client, mock_processor, mock_db, tmp_path):
        """Should create a job from file upload."""
        # Create a test file
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake video content")

        with patch("app.api.routes.jobs.get_processor", return_value=mock_processor):
            with patch("app.api.routes.jobs.get_db", return_value=mock_db):
                with open(test_file, "rb") as f:
                    response = client.post(
                        "/api/jobs",
                        files={"file": ("test.mp4", f, "video/mp4")},
                    )

                assert response.status_code == 201
                data = response.json()
                assert "job_id" in data

    def test_create_job_requires_url_or_file(self, client, mock_processor, mock_db):
        """Should reject request without URL or file."""
        with patch("app.api.routes.jobs.get_processor", return_value=mock_processor):
            with patch("app.api.routes.jobs.get_db", return_value=mock_db):
                response = client.post("/api/jobs", json={})

                assert response.status_code == 400
                assert "url" in response.json()["detail"].lower() or "file" in response.json()["detail"].lower()

    def test_get_job_status(self, client, mock_db):
        """Should return job status."""
        from app.models.job import Job, JobStatus, JobStage

        mock_job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.TRANSCRIBING,
            stage=JobStage.TRANSCRIBING,
            progress=50,
        )
        mock_db.get_job = AsyncMock(return_value=mock_job)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            response = client.get("/api/jobs/JOB-TEST01")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "JOB-TEST01"
            assert data["status"] == "transcribing"
            assert data["progress"] == 50

    def test_get_job_not_found(self, client, mock_db):
        """Should return 404 for non-existent job."""
        mock_db.get_job = AsyncMock(return_value=None)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            response = client.get("/api/jobs/JOB-NOTFOUND")

            assert response.status_code == 404

    def test_get_job_download_json(self, client, mock_db, tmp_path):
        """Should return JSON download."""
        from app.models.job import Job, JobStatus, JobStage

        # Create mock output file
        output_file = tmp_path / "JOB-TEST01.json"
        output_file.write_text('{"text": "test transcription"}')

        mock_job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.COMPLETED,
            stage=JobStage.COMPLETED,
            output_json=str(output_file),
        )
        mock_db.get_job = AsyncMock(return_value=mock_job)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            response = client.get("/api/jobs/JOB-TEST01/download?format=json")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

    def test_get_job_download_not_completed(self, client, mock_db):
        """Should reject download for incomplete job."""
        from app.models.job import Job, JobStatus, JobStage

        mock_job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.TRANSCRIBING,
            stage=JobStage.TRANSCRIBING,
        )
        mock_db.get_job = AsyncMock(return_value=mock_job)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            response = client.get("/api/jobs/JOB-TEST01/download?format=json")

            assert response.status_code == 400

    def test_delete_job(self, client, mock_db, mock_processor):
        """Should delete a job."""
        from app.models.job import Job, JobStatus, JobStage

        mock_job = Job(
            job_id="JOB-TEST01",
            status=JobStatus.COMPLETED,
            stage=JobStage.COMPLETED,
        )
        mock_db.get_job = AsyncMock(return_value=mock_job)
        mock_processor.delete_job = AsyncMock(return_value=True)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            with patch("app.api.routes.jobs.get_processor", return_value=mock_processor):
                response = client.delete("/api/jobs/JOB-TEST01")

                assert response.status_code == 204

    def test_list_jobs(self, client, mock_db):
        """Should list jobs with pagination."""
        from app.models.job import Job, JobStatus, JobStage

        mock_jobs = [
            Job(job_id="JOB-TEST01", status=JobStatus.COMPLETED, stage=JobStage.COMPLETED),
            Job(job_id="JOB-TEST02", status=JobStatus.QUEUED, stage=JobStage.QUEUED),
        ]
        mock_db.list_jobs = AsyncMock(return_value=mock_jobs)

        with patch("app.api.routes.jobs.get_db", return_value=mock_db):
            response = client.get("/api/jobs")

            assert response.status_code == 200
            data = response.json()
            assert "jobs" in data
            assert len(data["jobs"]) == 2


class TestHealthAPI:
    """Tests for /api/health endpoint."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""
        from app.api.routes.health import router

        app = FastAPI()
        app.include_router(router, prefix="/api")
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_health_check(self, client):
        """Should return health status."""
        with patch("app.api.routes.health.get_whisper_manager") as mock_manager:
            mock_manager.return_value.is_loaded = False
            mock_manager.return_value.get_status.return_value = {"loaded": False}

            with patch("app.api.routes.health.get_processor") as mock_processor:
                mock_processor.return_value.get_queue_status.return_value = {
                    "queue_size": 0,
                    "current_job": None,
                    "processing": True,
                }

                response = client.get("/api/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert "whisper" in data
                assert "queue" in data


class TestAdminAPI:
    """Tests for /api/admin endpoints."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""
        from app.api.routes.admin import router

        app = FastAPI()
        app.include_router(router, prefix="/api/admin")
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_admin_requires_password(self, client):
        """Should require admin password."""
        response = client.get("/api/admin/stats")

        assert response.status_code == 401

    def test_admin_with_valid_password(self, client):
        """Should allow access with valid password."""
        with patch("app.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_password = "testpassword"

            with patch("app.api.routes.admin.get_db") as mock_db:
                mock_db.return_value.list_jobs = AsyncMock(return_value=[])

                with patch("app.api.routes.admin.get_processor") as mock_processor:
                    mock_processor.return_value.get_queue_status.return_value = {}

                    response = client.get(
                        "/api/admin/stats",
                        headers={"X-Admin-Password": "testpassword"},
                    )

                    assert response.status_code == 200

    def test_admin_with_invalid_password(self, client):
        """Should reject invalid password."""
        with patch("app.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_password = "testpassword"

            response = client.get(
                "/api/admin/stats",
                headers={"X-Admin-Password": "wrongpassword"},
            )

            assert response.status_code == 401

    def test_cleanup_expired_jobs(self, client):
        """Should clean up expired jobs."""
        with patch("app.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_password = "testpassword"

            with patch("app.api.routes.admin.get_processor") as mock_processor:
                mock_processor.return_value.cleanup_expired_jobs = AsyncMock(return_value=5)

                response = client.post(
                    "/api/admin/cleanup",
                    headers={"X-Admin-Password": "testpassword"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["deleted_count"] == 5

    def test_unload_model(self, client):
        """Should unload Whisper model."""
        with patch("app.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_password = "testpassword"

            with patch("app.api.routes.admin.get_whisper_manager") as mock_manager:
                mock_manager.return_value.unload_model = AsyncMock()

                response = client.post(
                    "/api/admin/model/unload",
                    headers={"X-Admin-Password": "testpassword"},
                )

                assert response.status_code == 200
                mock_manager.return_value.unload_model.assert_called_once()
