"""
Whisper model management with GPU memory optimization.
Handles on-demand loading, automatic unloading, and Japanese-optimized transcription.
"""
import asyncio
import gc
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import torch

logger = logging.getLogger(__name__)

# Japanese-optimized Whisper settings (from legacy system)
WHISPER_SETTINGS = {
    "language": "ja",
    "task": "transcribe",
    "temperature": 0.0,
    "beam_size": 5,
    "best_of": 5,
    "patience": 1.0,
    "condition_on_previous_text": False,  # Prevent hallucinations in long audio
    "compression_ratio_threshold": 2.4,
    "logprob_threshold": -1.0,
    "no_speech_threshold": 0.6,
    "word_timestamps": False,
    "initial_prompt": None,
    "suppress_tokens": [-1],
    "without_timestamps": False,
}


class WhisperManager:
    """
    Manages Whisper model lifecycle with GPU memory optimization.

    Features:
    - On-demand model loading
    - Automatic unloading after idle period
    - Japanese-optimized transcription settings
    - Progress tracking
    """

    def __init__(
        self,
        model_name: str = "large-v3",
        unload_timeout_minutes: int = 5,
        device: Optional[str] = None,
    ):
        """
        Initialize Whisper manager.

        Args:
            model_name: Whisper model to use (e.g., "large-v3", "base")
            unload_timeout_minutes: Minutes of idle time before unloading model
            device: Device to use ("cuda" or "cpu"), auto-detected if None
        """
        self.model_name = model_name
        self.unload_timeout_minutes = unload_timeout_minutes
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model: Optional[Any] = None
        self._last_used: Optional[datetime] = None
        self._unload_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self.model is not None

    @property
    def last_used(self) -> Optional[datetime]:
        """Get timestamp of last model usage."""
        return self._last_used

    async def load_model(self) -> None:
        """Load Whisper model into memory."""
        async with self._lock:
            if self.is_loaded:
                logger.debug("Model already loaded")
                return

            logger.info(f"Loading Whisper model: {self.model_name}")

            # Run model loading in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                self._load_model_sync,
            )

            self._last_used = datetime.utcnow()
            logger.info(f"Whisper model loaded on {self.device}")

    def _load_model_sync(self) -> Any:
        """Synchronous model loading (runs in executor)."""
        import whisper

        return whisper.load_model(self.model_name, device=self.device)

    async def unload_model(self) -> None:
        """Unload model and free GPU memory."""
        async with self._lock:
            if not self.is_loaded:
                logger.debug("Model not loaded, nothing to unload")
                return

            logger.info("Unloading Whisper model")

            # Cancel any pending unload timer
            self._cancel_unload_timer()

            # Clear model reference
            self.model = None

            # Force garbage collection
            gc.collect()

            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            self._last_used = None
            logger.info("Whisper model unloaded, GPU memory freed")

    async def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        task: str = "transcribe",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> dict:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_path: Path to audio file (WAV format recommended)
            language: Language code (e.g., "ja", "en"). None for auto-detect.
            initial_prompt: Optional prompt to guide transcription
            task: "transcribe" or "translate" (translate to English)
            progress_callback: Optional callback for progress updates (0-100)

        Returns:
            Transcription result dict with 'text', 'segments', 'language', 'duration'
        """
        # Cancel any pending unload
        self._cancel_unload_timer()

        # Ensure model is loaded
        if not self.is_loaded:
            await self.load_model()

        self._last_used = datetime.utcnow()

        # Report initial progress
        if progress_callback:
            progress_callback(0)

        # Build settings with overrides
        settings = WHISPER_SETTINGS.copy()
        if language:
            settings["language"] = language
        if initial_prompt:
            settings["initial_prompt"] = initial_prompt
        settings["task"] = task

        # Run transcription in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            str(audio_path),
            settings,
        )

        # Report completion
        if progress_callback:
            progress_callback(100)

        self._last_used = datetime.utcnow()
        return result

    def _transcribe_sync(self, audio_path: str, settings: dict) -> dict:
        """Synchronous transcription (runs in executor)."""
        result = self.model.transcribe(audio_path, **settings)
        # Ensure we return duration for OpenAI-compatible API
        if "duration" not in result and "segments" in result and result["segments"]:
            last_segment = result["segments"][-1]
            result["duration"] = last_segment.get("end", 0.0)
        return result

    def start_unload_timer(self) -> None:
        """Start timer to unload model after idle period."""
        self._cancel_unload_timer()

        async def unload_after_timeout():
            try:
                timeout_seconds = self.unload_timeout_minutes * 60
                await asyncio.sleep(timeout_seconds)
                await self.unload_model()
            except asyncio.CancelledError:
                pass

        self._unload_task = asyncio.create_task(unload_after_timeout())
        logger.debug(f"Unload timer started: {self.unload_timeout_minutes} minutes")

    def _cancel_unload_timer(self) -> None:
        """Cancel any pending unload timer."""
        if self._unload_task and not self._unload_task.done():
            self._unload_task.cancel()
            logger.debug("Unload timer cancelled")

    def get_status(self) -> dict:
        """
        Get current manager status.

        Returns:
            Status dict with model state information
        """
        gpu_info = None
        if torch.cuda.is_available():
            gpu_info = {
                "name": torch.cuda.get_device_name(0),
                "memory_allocated": torch.cuda.memory_allocated(0),
                "memory_reserved": torch.cuda.memory_reserved(0),
            }

        return {
            "is_loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "last_used": self._last_used.isoformat() if self._last_used else None,
            "unload_timeout_minutes": self.unload_timeout_minutes,
            "gpu_info": gpu_info,
        }


# Singleton instance for the application
_manager_instance: Optional[WhisperManager] = None


def get_whisper_manager() -> WhisperManager:
    """Get or create the global WhisperManager instance."""
    global _manager_instance
    if _manager_instance is None:
        from app.config import get_settings

        settings = get_settings()
        _manager_instance = WhisperManager(
            model_name=settings.whisper_model,
            unload_timeout_minutes=settings.model_unload_minutes,
        )
    return _manager_instance
