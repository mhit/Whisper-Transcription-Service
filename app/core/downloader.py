"""
Video downloader using yt-dlp with optimized settings for large files.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default yt-dlp options optimized for large file downloads
DEFAULT_YDL_OPTIONS = {
    "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "merge_output_format": "mp4",
    "http_chunk_size": 1024 * 1024,  # 1MB chunks
    "concurrent_fragment_downloads": 4,  # 4 parallel downloads
    "retries": 10,
    "fragment_retries": 10,
    "continuedl": True,
    "noprogress": False,
    "quiet": True,
    "no_warnings": False,
    "extract_flat": False,
}


class Downloader:
    """
    Video downloader with yt-dlp backend.

    Features:
    - Supports YouTube, Vimeo, and hundreds of other sites
    - Optimized for large files with chunked downloads
    - Progress tracking
    - Automatic format selection
    """

    def __init__(
        self,
        output_dir: Path,
        max_filesize_mb: int = 10240,
    ):
        """
        Initialize downloader.

        Args:
            output_dir: Directory for downloaded files
            max_filesize_mb: Maximum file size in MB (default 10GB)
        """
        self.output_dir = Path(output_dir)
        self.max_filesize_mb = max_filesize_mb
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid and potentially downloadable.

        Args:
            url: URL to validate

        Returns:
            True if URL appears valid
        """
        if not url or not isinstance(url, str):
            return False

        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    async def get_video_info(self, url: str) -> dict[str, Any]:
        """
        Extract video information without downloading.

        Args:
            url: Video URL

        Returns:
            Video metadata dict
        """
        import yt_dlp

        ydl_opts = {
            **DEFAULT_YDL_OPTIONS,
            "skip_download": True,
            "quiet": True,
        }

        loop = asyncio.get_event_loop()

        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        return await loop.run_in_executor(None, extract_info)

    async def download(
        self,
        url: str,
        job_id: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> dict[str, Any]:
        """
        Download video from URL.

        Args:
            url: Video URL
            job_id: Job ID for file naming
            progress_callback: Optional callback for progress updates (0-100)

        Returns:
            Result dict with 'path', 'title', 'duration' or 'error'
        """
        import yt_dlp

        output_template = str(self.output_dir / f"{job_id}.%(ext)s")

        # Progress hook for yt-dlp
        last_progress = [0]

        def progress_hook(d):
            if d["status"] == "downloading":
                if "total_bytes" in d and d["total_bytes"] > 0:
                    percent = int(d["downloaded_bytes"] / d["total_bytes"] * 100)
                elif "total_bytes_estimate" in d and d["total_bytes_estimate"] > 0:
                    percent = int(
                        d["downloaded_bytes"] / d["total_bytes_estimate"] * 100
                    )
                else:
                    percent = last_progress[0]

                if percent != last_progress[0] and progress_callback:
                    progress_callback(percent)
                    last_progress[0] = percent

            elif d["status"] == "finished":
                if progress_callback:
                    progress_callback(100)

        ydl_opts = {
            **DEFAULT_YDL_OPTIONS,
            "outtmpl": output_template,
            "progress_hooks": [progress_hook],
        }

        loop = asyncio.get_event_loop()

        def do_download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        return {"error": "Failed to extract video info"}

                    # Find the downloaded file
                    filename = ydl.prepare_filename(info)
                    output_path = Path(filename)

                    # Handle merged format
                    if not output_path.exists():
                        mp4_path = output_path.with_suffix(".mp4")
                        if mp4_path.exists():
                            output_path = mp4_path

                    return {
                        "path": str(output_path),
                        "title": info.get("title", "Unknown"),
                        "duration": info.get("duration", 0),
                        "uploader": info.get("uploader", "Unknown"),
                        "filesize": output_path.stat().st_size if output_path.exists() else 0,
                    }

            except Exception as e:
                logger.error(f"Download failed: {e}")
                return {"error": str(e)}

        return await loop.run_in_executor(None, do_download)

    def sanitize_filename(self, filename: str, max_length: int = 200) -> str:
        """
        Sanitize filename for safe filesystem usage.

        Args:
            filename: Original filename
            max_length: Maximum filename length

        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Replace spaces with underscores
        sanitized = sanitized.replace(" ", "_")
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized
