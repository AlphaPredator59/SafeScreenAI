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
    ai_mode: str = "mock"
    ai_device: str = "cpu"
    vision_model_name: str = "yolov8n.pt"
    vision_confidence_threshold: float = 0.25
    transcription_model_name: str = "tiny"
    transcription_language: str | None = None
    text_moderation_model_name: str = "unitary/toxic-bert"
    text_moderation_confidence_threshold: float = 0.5
    context_model_name: str = "qwen2.5vl:7b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    context_timeout_seconds: float = 120.0
    context_window_seconds: float = 30.0
    context_window_overlap_seconds: float = 5.0
    max_context_windows: int = 15
    max_context_frames_per_window: int = 3
    max_detections_per_window: int = 20
    max_transcript_tokens_per_window: int = 400
    context_num_ctx: int = 8192
    context_max_input_tokens: int = 6000
    context_allow_partial_failures: bool = True
    moderation_low_risk_threshold: float = 0.30
    moderation_medium_risk_threshold: float = 0.60
    moderation_high_risk_threshold: float = 0.85
    moderation_auto_reject_threshold: float = 0.85
    moderation_review_threshold: float = 0.40
    moderation_min_signal_confidence: float = 0.30


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
