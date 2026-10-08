"""Factory functions for instantiating configured AI service adapters."""

from app.core.config import Settings, get_settings
from app.services.ai.context import QwenContextAnalyzer
from app.services.ai.interfaces import ContextAnalyzer, TextModerator, Transcriber, VisionAnalyzer
from app.services.ai.mocks import MockContextAnalyzer, MockTextModerator, MockTranscriber, MockVisionAnalyzer
from app.services.ai.text_moderation import TransformerTextModerator
from app.services.ai.transcription import WhisperTranscriber
from app.services.ai.vision import YoloVisionAnalyzer


def get_vision_analyzer(settings: Settings | None = None) -> VisionAnalyzer:
    """Resolve the configured VisionAnalyzer implementation."""
    resolved_settings = settings or get_settings()
    if resolved_settings.ai_mode.lower() == "real":
        return YoloVisionAnalyzer(
            model_name_or_path=resolved_settings.vision_model_name,
            device=resolved_settings.ai_device,
            confidence_threshold=resolved_settings.vision_confidence_threshold,
        )
    return MockVisionAnalyzer()


def get_transcriber(settings: Settings | None = None) -> Transcriber:
    """Resolve the configured Transcriber implementation."""
    resolved_settings = settings or get_settings()
    if resolved_settings.ai_mode.lower() == "real":
        return WhisperTranscriber(
            model_name=resolved_settings.transcription_model_name,
            device=resolved_settings.ai_device,
            language=resolved_settings.transcription_language,
        )
    return MockTranscriber()


def get_text_moderator(settings: Settings | None = None) -> TextModerator:
    """Resolve the configured TextModerator implementation."""
    resolved_settings = settings or get_settings()
    if resolved_settings.ai_mode.lower() == "real":
        return TransformerTextModerator(
            model_name=resolved_settings.text_moderation_model_name,
            device=resolved_settings.ai_device,
            confidence_threshold=resolved_settings.text_moderation_confidence_threshold,
        )
    return MockTextModerator()


def get_context_analyzer(settings: Settings | None = None) -> ContextAnalyzer:
    """Resolve the configured ContextAnalyzer implementation."""
    resolved_settings = settings or get_settings()
    if resolved_settings.ai_mode.lower() == "real":
        return QwenContextAnalyzer(
            model_name=resolved_settings.context_model_name,
            base_url=resolved_settings.ollama_base_url,
            timeout_seconds=resolved_settings.context_timeout_seconds,
            max_frames=resolved_settings.max_context_frames_per_window,
            num_ctx=resolved_settings.context_num_ctx,
            max_input_tokens=resolved_settings.context_max_input_tokens,
            window_seconds=resolved_settings.context_window_seconds,
            overlap_seconds=resolved_settings.context_window_overlap_seconds,
            max_windows=resolved_settings.max_context_windows,
            max_detections_per_window=resolved_settings.max_detections_per_window,
            max_transcript_tokens_per_window=resolved_settings.max_transcript_tokens_per_window,
            allow_partial_failures=resolved_settings.context_allow_partial_failures,
        )
    return MockContextAnalyzer()
