"""
Audio extraction from video files using FFmpeg.
Optimized for Whisper input format (16kHz mono WAV).
"""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Whisper optimal audio format
WHISPER_AUDIO_FORMAT = {
    "sample_rate": 16000,  # 16kHz
    "channels": 1,  # Mono
    "codec": "pcm_s16le",  # 16-bit PCM
}


class AudioExtractor:
    """
    Extract audio from video files in Whisper-optimized format.

    Features:
    - Extracts to 16kHz mono WAV (optimal for Whisper)
    - Progress tracking
    - Error handling with detailed messages
    """

    def __init__(self, output_dir: Path):
        """
        Initialize audio extractor.

        Args:
            output_dir: Directory for extracted audio files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def extract(
        self,
        video_path: str | Path,
        job_id: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> dict:
        """
        Extract audio from video file.

        Args:
            video_path: Path to video file
            job_id: Job ID for output naming
            progress_callback: Optional progress callback (0-100)

        Returns:
            Result dict with 'path', 'duration' or 'error'
        """
        video_path = Path(video_path)
        output_path = self.output_dir / f"{job_id}.wav"

        if not video_path.exists():
            return {"error": f"Video file not found: {video_path}"}

        # Report start
        if progress_callback:
            progress_callback(0)

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", WHISPER_AUDIO_FORMAT["codec"],
            "-ar", str(WHISPER_AUDIO_FORMAT["sample_rate"]),
            "-ac", str(WHISPER_AUDIO_FORMAT["channels"]),
            "-y",  # Overwrite output
            str(output_path),
        ]

        loop = asyncio.get_event_loop()

        def run_ffmpeg():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return None  # No error
            except subprocess.CalledProcessError as e:
                return f"FFmpeg error: {e.stderr}"
            except FileNotFoundError:
                return "FFmpeg not found. Please install FFmpeg."
            except Exception as e:
                return str(e)

        error = await loop.run_in_executor(None, run_ffmpeg)

        if error:
            logger.error(f"Audio extraction failed: {error}")
            return {"error": error}

        # Get audio duration
        duration = await self._get_duration(output_path)

        # Report completion
        if progress_callback:
            progress_callback(100)

        return {
            "path": str(output_path),
            "duration": duration,
            "size": output_path.stat().st_size,
        }

    async def _get_duration(self, audio_path: Path) -> float:
        """
        Get audio duration in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]

        loop = asyncio.get_event_loop()

        def get_duration():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return float(result.stdout.strip())
            except Exception:
                return 0.0

        return await loop.run_in_executor(None, get_duration)

    @staticmethod
    def check_ffmpeg_available() -> bool:
        """
        Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is available
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
