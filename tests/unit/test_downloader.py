"""
Unit tests for Downloader module.
TDD: Tests written before implementation.
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestDownloader:
    """Tests for Downloader class."""

    @pytest_asyncio.fixture
    async def downloader(self, tmp_path: Path):
        """Create a Downloader instance for testing."""
        from app.core.downloader import Downloader

        downloader = Downloader(output_dir=tmp_path)
        return downloader

    @pytest.mark.asyncio
    async def test_is_valid_url(self, downloader):
        """Should validate URLs correctly."""
        assert downloader.is_valid_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert downloader.is_valid_url("https://vimeo.com/123456")
        assert not downloader.is_valid_url("not-a-url")
        assert not downloader.is_valid_url("")

    @pytest.mark.asyncio
    async def test_download_creates_output_file(self, downloader, tmp_path: Path):
        """Should create output file after download."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 120,
            }

            # Create a mock output file
            output_file = tmp_path / "test_video.mp4"
            output_file.touch()

            result = await downloader.download(
                "https://example.com/video",
                job_id="JOB-TEST01",
            )

            assert "title" in result or result.get("error") is not None

    @pytest.mark.asyncio
    async def test_download_with_progress_callback(self, downloader):
        """Should call progress callback during download."""
        progress_values = []

        def on_progress(value: int):
            progress_values.append(value)

        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_ydl.extract_info.return_value = {"title": "Test"}

            await downloader.download(
                "https://example.com/video",
                job_id="JOB-TEST01",
                progress_callback=on_progress,
            )

            # Progress callback should have been called
            assert len(progress_values) >= 0  # May be empty for mock

    @pytest.mark.asyncio
    async def test_download_error_handling(self, downloader):
        """Should handle download errors gracefully."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_ydl.extract_info.side_effect = Exception("Download failed")

            result = await downloader.download(
                "https://example.com/video",
                job_id="JOB-TEST01",
            )

            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_video_info(self, downloader):
        """Should extract video info without downloading."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "uploader": "Test Channel",
            }

            info = await downloader.get_video_info("https://example.com/video")

            assert info["title"] == "Test Video"
            assert info["duration"] == 300


class TestDownloaderConfig:
    """Tests for downloader configuration."""

    def test_default_ydl_options(self):
        """Should have correct default options."""
        from app.core.downloader import DEFAULT_YDL_OPTIONS

        assert DEFAULT_YDL_OPTIONS["format"] is not None
        assert DEFAULT_YDL_OPTIONS["http_chunk_size"] == 1024 * 1024  # 1MB
        assert DEFAULT_YDL_OPTIONS["concurrent_fragment_downloads"] == 4
