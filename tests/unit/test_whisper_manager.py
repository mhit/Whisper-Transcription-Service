"""
Unit tests for Whisper Manager module.
TDD: Tests written before implementation.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestWhisperManager:
    """Tests for WhisperManager class."""

    @pytest_asyncio.fixture
    async def manager(self):
        """Create a WhisperManager instance for testing."""
        from app.core.whisper_manager import WhisperManager

        manager = WhisperManager(
            model_name="base",  # Use base model for faster tests
            unload_timeout_minutes=1,
        )
        yield manager
        # Cleanup
        if manager.is_loaded:
            await manager.unload_model()

    @pytest.mark.asyncio
    async def test_initial_state(self, manager):
        """Manager should start with model not loaded."""
        assert not manager.is_loaded
        assert manager.model is None

    @pytest.mark.asyncio
    async def test_load_model(self, manager):
        """Should load Whisper model on demand."""
        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_load.return_value = mock_model

            await manager.load_model()

            assert manager.is_loaded
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_model(self, manager):
        """Should unload model and free memory."""
        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_load.return_value = mock_model

            await manager.load_model()
            await manager.unload_model()

            assert not manager.is_loaded
            assert manager.model is None

    @pytest.mark.asyncio
    async def test_transcribe_loads_model_if_needed(self, manager):
        """Transcribe should auto-load model if not loaded."""
        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "テスト音声",
                "segments": [],
            }
            mock_load.return_value = mock_model

            result = await manager.transcribe("test.wav")

            mock_load.assert_called_once()
            assert "text" in result

    @pytest.mark.asyncio
    async def test_transcribe_japanese_settings(self, manager):
        """Transcribe should use Japanese-optimized settings."""
        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "テスト",
                "segments": [],
            }
            mock_load.return_value = mock_model

            await manager.transcribe("test.wav")

            # Verify Japanese settings were used
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["language"] == "ja"
            assert call_kwargs["condition_on_previous_text"] is False
            assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_auto_unload_timer(self, manager):
        """Model should auto-unload after idle timeout."""
        manager.unload_timeout_minutes = 0.01  # Very short for testing

        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_load.return_value = mock_model

            await manager.load_model()
            manager.start_unload_timer()

            # Wait for auto-unload
            await asyncio.sleep(1)

            assert not manager.is_loaded

    @pytest.mark.asyncio
    async def test_cancel_unload_timer_on_new_job(self, manager):
        """Unload timer should be cancelled when new job starts."""
        manager.unload_timeout_minutes = 1

        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {"text": "", "segments": []}
            mock_load.return_value = mock_model

            await manager.load_model()
            manager.start_unload_timer()

            # New transcription should cancel timer
            await manager.transcribe("test.wav")

            # Model should still be loaded
            assert manager.is_loaded

    @pytest.mark.asyncio
    async def test_get_status(self, manager):
        """Should return current manager status."""
        status = manager.get_status()

        assert "is_loaded" in status
        assert "model_name" in status
        assert "last_used" in status

    @pytest.mark.asyncio
    async def test_progress_callback(self, manager):
        """Should call progress callback during transcription."""
        progress_values = []

        def on_progress(value: int):
            progress_values.append(value)

        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "テスト",
                "segments": [{"start": 0, "end": 1, "text": "テスト"}],
            }
            mock_load.return_value = mock_model

            await manager.transcribe("test.wav", progress_callback=on_progress)

            # Progress should have been reported
            assert len(progress_values) > 0


class TestWhisperSettings:
    """Tests for Whisper configuration settings."""

    def test_default_settings(self):
        """Should have correct default Japanese settings."""
        from app.core.whisper_manager import WHISPER_SETTINGS

        assert WHISPER_SETTINGS["language"] == "ja"
        assert WHISPER_SETTINGS["temperature"] == 0.0
        assert WHISPER_SETTINGS["beam_size"] == 5
        assert WHISPER_SETTINGS["best_of"] == 5
        assert WHISPER_SETTINGS["condition_on_previous_text"] is False
        assert WHISPER_SETTINGS["no_speech_threshold"] == 0.6
