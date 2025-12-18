"""
OpenAI-compatible audio transcription API.

Provides /v1/audio/transcriptions endpoint compatible with OpenAI's API,
allowing use of existing OpenAI SDKs and tools.
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from enum import Enum

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field

from app.api.dependencies import get_whisper_manager
from app.core.whisper_manager import WhisperManager


async def convert_to_wav(input_path: Path, output_path: Path) -> bool:
    """
    Convert audio/video file to WAV format optimized for Whisper.

    Args:
        input_path: Source file path
        output_path: Destination WAV file path

    Returns:
        True if conversion succeeded, False otherwise
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",  # 16kHz (Whisper optimal)
        "-ac", "1",  # Mono
        "-y",  # Overwrite output
        str(output_path),
    ]

    loop = asyncio.get_event_loop()

    def run_ffmpeg():
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    return await loop.run_in_executor(None, run_ffmpeg)


router = APIRouter(prefix="/v1/audio", tags=["OpenAI Compatible"])


class ResponseFormat(str, Enum):
    """Supported response formats."""
    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VTT = "vtt"
    VERBOSE_JSON = "verbose_json"


class TranscriptionWord(BaseModel):
    """Word-level transcription with timestamp."""
    word: str
    start: float
    end: float


class TranscriptionSegment(BaseModel):
    """Segment of transcription with timestamps."""
    id: int
    seek: int = 0
    start: float
    end: float
    text: str
    tokens: list[int] = Field(default_factory=list)
    temperature: float = 0.0
    avg_logprob: float = 0.0
    compression_ratio: float = 0.0
    no_speech_prob: float = 0.0


class TranscriptionResponse(BaseModel):
    """Standard transcription response."""
    text: str


class TranscriptionVerboseResponse(BaseModel):
    """Verbose transcription response with segments."""
    task: str = "transcribe"
    language: str
    duration: float
    text: str
    segments: list[TranscriptionSegment] = Field(default_factory=list)
    words: Optional[list[TranscriptionWord]] = None


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds to SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds to VTT timestamp (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    """Convert segments to SRT format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp_srt(seg["start"])
        end = format_timestamp_srt(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def segments_to_vtt(segments: list[dict]) -> str:
    """Convert segments to VTT format."""
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        start = format_timestamp_vtt(seg["start"])
        end = format_timestamp_vtt(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


@router.post("/transcriptions", response_model=None)
async def create_transcription(
    file: UploadFile = File(..., description="The audio file to transcribe"),
    model: str = Form("whisper-1", description="Model to use (ignored, uses configured model)"),
    language: Optional[str] = Form(None, description="Language code (e.g., 'ja', 'en')"),
    prompt: Optional[str] = Form(None, description="Optional prompt to guide transcription"),
    response_format: ResponseFormat = Form(ResponseFormat.JSON, description="Output format"),
    temperature: float = Form(0.0, ge=0.0, le=1.0, description="Sampling temperature"),
    whisper_manager: WhisperManager = Depends(get_whisper_manager),
):
    """
    Transcribes audio into the input language.

    OpenAI-compatible endpoint: POST /v1/audio/transcriptions

    This endpoint is compatible with the OpenAI Audio API, allowing you to use
    existing OpenAI SDKs and tools with this service.

    ## Example with OpenAI Python SDK:

    ```python
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed"  # or your configured API key
    )

    with open("audio.mp3", "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ja",
            response_format="verbose_json"
        )
    print(transcription.text)
    ```
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".flac", ".ogg"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Extract audio if needed (convert to WAV for Whisper)
        audio_path = tmp_path
        wav_path = tmp_path.with_suffix(".wav")
        if file_ext != ".wav":
            success = await convert_to_wav(tmp_path, wav_path)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to convert audio file. Ensure FFmpeg is installed."
                )
            audio_path = wav_path

        # Transcribe
        result = await whisper_manager.transcribe(
            audio_path,
            language=language or "ja",  # Default to Japanese
            initial_prompt=prompt,
        )

        # Get segments for detailed formats
        segments = result.get("segments", [])
        full_text = result.get("text", "")
        duration = result.get("duration", 0.0)
        detected_language = result.get("language", language or "ja")

        # Format response based on requested format
        if response_format == ResponseFormat.TEXT:
            return PlainTextResponse(content=full_text)

        elif response_format == ResponseFormat.SRT:
            srt_content = segments_to_srt(segments)
            return PlainTextResponse(content=srt_content, media_type="text/plain")

        elif response_format == ResponseFormat.VTT:
            vtt_content = segments_to_vtt(segments)
            return PlainTextResponse(content=vtt_content, media_type="text/vtt")

        elif response_format == ResponseFormat.VERBOSE_JSON:
            # Build verbose response with segments
            verbose_segments = [
                TranscriptionSegment(
                    id=i,
                    seek=0,
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    temperature=temperature,
                    avg_logprob=seg.get("avg_logprob", 0.0),
                    compression_ratio=seg.get("compression_ratio", 0.0),
                    no_speech_prob=seg.get("no_speech_prob", 0.0),
                )
                for i, seg in enumerate(segments)
            ]

            verbose_response = TranscriptionVerboseResponse(
                task="transcribe",
                language=detected_language,
                duration=duration,
                text=full_text,
                segments=verbose_segments,
            )
            return JSONResponse(content=verbose_response.model_dump())

        else:  # JSON (default)
            response = TranscriptionResponse(text=full_text)
            return JSONResponse(content=response.model_dump())

    finally:
        # Cleanup temp files
        tmp_path.unlink(missing_ok=True)
        wav_path = tmp_path.with_suffix(".wav")
        if wav_path.exists():
            wav_path.unlink()


@router.post("/translations", response_model=None)
async def create_translation(
    file: UploadFile = File(..., description="The audio file to translate"),
    model: str = Form("whisper-1", description="Model to use (ignored)"),
    prompt: Optional[str] = Form(None, description="Optional prompt"),
    response_format: ResponseFormat = Form(ResponseFormat.JSON, description="Output format"),
    temperature: float = Form(0.0, ge=0.0, le=1.0, description="Sampling temperature"),
    whisper_manager: WhisperManager = Depends(get_whisper_manager),
):
    """
    Translates audio into English.

    OpenAI-compatible endpoint: POST /v1/audio/translations

    Note: This endpoint translates any language audio to English text.
    """
    # Same implementation as transcriptions but with task="translate"
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".flac", ".ogg"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        audio_path = tmp_path
        wav_path = tmp_path.with_suffix(".wav")
        if file_ext != ".wav":
            success = await convert_to_wav(tmp_path, wav_path)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to convert audio file. Ensure FFmpeg is installed."
                )
            audio_path = wav_path

        # Transcribe with translation task
        result = await whisper_manager.transcribe(
            audio_path,
            language=None,  # Auto-detect source language
            initial_prompt=prompt,
            task="translate",  # Translate to English
        )

        segments = result.get("segments", [])
        full_text = result.get("text", "")
        duration = result.get("duration", 0.0)

        if response_format == ResponseFormat.TEXT:
            return PlainTextResponse(content=full_text)
        elif response_format == ResponseFormat.SRT:
            return PlainTextResponse(content=segments_to_srt(segments))
        elif response_format == ResponseFormat.VTT:
            return PlainTextResponse(content=segments_to_vtt(segments), media_type="text/vtt")
        elif response_format == ResponseFormat.VERBOSE_JSON:
            verbose_segments = [
                TranscriptionSegment(
                    id=i, seek=0, start=seg["start"], end=seg["end"],
                    text=seg["text"], temperature=temperature,
                )
                for i, seg in enumerate(segments)
            ]
            verbose_response = TranscriptionVerboseResponse(
                task="translate", language="en", duration=duration,
                text=full_text, segments=verbose_segments,
            )
            return JSONResponse(content=verbose_response.model_dump())
        else:
            return JSONResponse(content=TranscriptionResponse(text=full_text).model_dump())

    finally:
        tmp_path.unlink(missing_ok=True)
        wav_path = tmp_path.with_suffix(".wav")
        if wav_path.exists():
            wav_path.unlink()


@router.get("/models")
async def list_models():
    """
    List available audio models.

    OpenAI-compatible endpoint for model discovery.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "whisper-1",
                "object": "model",
                "created": 1677532384,
                "owned_by": "openai",
            },
            {
                "id": "whisper-large-v3",
                "object": "model",
                "created": 1677532384,
                "owned_by": "local",
            },
        ]
    }
