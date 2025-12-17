"""
Configuration management for Whisper Transcription Service.
"""
import secrets
import string
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False

    # Authentication
    admin_password: str = "changeme"
    api_key: Optional[str] = None

    # Cloudflare Tunnel
    cloudflare_tunnel_token: Optional[str] = None

    # Data Management
    data_dir: Path = Path("/app/data")
    job_retention_days: int = 7
    max_upload_size_mb: int = 10240  # 10GB

    # GPU/Model Management
    model_unload_minutes: int = 5
    whisper_model: str = "large-v3"

    # Whisper Settings (Japanese optimized)
    whisper_language: str = "ja"
    whisper_temperature: float = 0.0
    whisper_beam_size: int = 5
    whisper_best_of: int = 5
    whisper_patience: float = 1.0
    whisper_condition_on_previous_text: bool = False  # Prevent hallucinations
    whisper_compression_ratio_threshold: float = 2.4
    whisper_logprob_threshold: float = -1.0
    whisper_no_speech_threshold: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def generate_job_id() -> str:
    """
    Generate a short, human-readable job ID.
    Format: JOB-XXXXXX (6 alphanumeric characters)

    Returns:
        str: Generated job ID (e.g., "JOB-A1B2C3")
    """
    chars = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(6))
    return f"JOB-{random_part}"


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
