"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SafeScreen AI"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/safescreen"
    storage_path: Path = Field(default=Path("storage"))
    max_upload_size_bytes: int = 500 * 1024 * 1024
    max_video_duration_seconds: int = 30 * 60
    frame_sampling_interval_seconds: float = 1.0
    frame_image_format: str = "jpg"
    frame_image_quality: int = 85
    audio_output_format: str = "wav"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
