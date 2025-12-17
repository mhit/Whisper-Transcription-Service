"""
Output formatters for transcription results.
Converts Whisper output to JSON, TXT, SRT, and Markdown formats.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def format_timestamp(seconds: float) -> str:
    """
    Format seconds to SRT timestamp format (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_simple(seconds: float) -> str:
    """
    Format seconds to simple timestamp format (HH:MM:SS).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class OutputFormatter:
    """
    Formats Whisper transcription results into multiple output formats.

    Supported formats:
    - JSON: Full data with timestamps and segments
    - TXT: Plain text without timestamps
    - SRT: SubRip subtitle format
    - Markdown: Formatted report with timestamps
    """

    def __init__(self, output_dir: Path):
        """
        Initialize formatter.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format_all(
        self,
        transcription: dict[str, Any],
        job_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Generate all output formats.

        Args:
            transcription: Whisper transcription result
            job_id: Job ID for file naming
            metadata: Optional metadata (title, duration, etc.)

        Returns:
            Dict mapping format name to file path
        """
        metadata = metadata or {}
        paths = {}

        # JSON
        json_path = self.output_dir / f"{job_id}.json"
        self._write_json(transcription, metadata, json_path)
        paths["json"] = str(json_path)

        # TXT
        txt_path = self.output_dir / f"{job_id}.txt"
        self._write_txt(transcription, txt_path)
        paths["txt"] = str(txt_path)

        # SRT
        srt_path = self.output_dir / f"{job_id}.srt"
        self._write_srt(transcription, srt_path)
        paths["srt"] = str(srt_path)

        # Markdown
        md_path = self.output_dir / f"{job_id}.md"
        self._write_markdown(transcription, metadata, md_path)
        paths["md"] = str(md_path)

        return paths

    def _write_json(
        self,
        transcription: dict,
        metadata: dict,
        output_path: Path,
    ) -> None:
        """Write JSON format output."""
        output = {
            "metadata": {
                "created_at": datetime.utcnow().isoformat(),
                **metadata,
            },
            "text": transcription.get("text", ""),
            "segments": [
                {
                    "id": i,
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", "").strip(),
                }
                for i, seg in enumerate(transcription.get("segments", []))
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def _write_txt(self, transcription: dict, output_path: Path) -> None:
        """Write plain text format output."""
        text = transcription.get("text", "")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

    def _write_srt(self, transcription: dict, output_path: Path) -> None:
        """Write SRT subtitle format output."""
        segments = transcription.get("segments", [])

        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = format_timestamp(seg.get("start", 0))
                end = format_timestamp(seg.get("end", 0))
                text = seg.get("text", "").strip()

                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")

    def _write_markdown(
        self,
        transcription: dict,
        metadata: dict,
        output_path: Path,
    ) -> None:
        """Write Markdown format output."""
        title = metadata.get("title", "Transcription")
        duration = metadata.get("duration", 0)
        segments = transcription.get("segments", [])

        with open(output_path, "w", encoding="utf-8") as f:
            # Header
            f.write(f"# {title}\n\n")
            f.write(f"**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            if duration:
                f.write(f"**Duration**: {format_timestamp_simple(duration)}\n")
            f.write("\n---\n\n")

            # Full text
            f.write("## Full Transcript\n\n")
            f.write(transcription.get("text", ""))
            f.write("\n\n---\n\n")

            # Timestamped segments
            f.write("## Timestamped Segments\n\n")
            for seg in segments:
                timestamp = format_timestamp_simple(seg.get("start", 0))
                text = seg.get("text", "").strip()
                f.write(f"**[{timestamp}]** {text}\n\n")


def get_formatter(output_dir: Path) -> OutputFormatter:
    """
    Get an OutputFormatter instance.

    Args:
        output_dir: Output directory path

    Returns:
        OutputFormatter instance
    """
    return OutputFormatter(output_dir)
