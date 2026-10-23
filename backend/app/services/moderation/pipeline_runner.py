"""Production orchestration runner for the SafeScreen AI multi-modal moderation pipeline."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import logging
from pathlib import Path
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Video
from app.services.ai.contracts import (
    AIServiceError,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)
from app.services.ai.factory import (
    get_context_analyzer,
    get_text_moderator,
    get_transcriber,
    get_vision_analyzer,
)
from app.services.moderation.config import ModerationConfig
from app.services.moderation.contracts import ModerationResult
from app.services.moderation.engine import ModerationEngine
from app.services.moderation.persistence import ModerationPersistenceService
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository
from app.services.video.metadata import VideoMetadata, VideoMetadataService
from app.services.video.processing import (
    AudioArtifact,
    AudioProcessingService,
    FrameArtifact,
    FrameProcessingService,
    ProcessingError,
)
from app.services.video.repository import VideoRepository
from app.services.video.storage import LocalStorageService

logger = logging.getLogger("safescreen.pipeline")


class PipelineExecutionError(Exception):
    """Raised when pipeline execution fails unrecoverably."""

    def __init__(
        self,
        message: str,
        stage: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.original_error = original_error


@dataclass
class PipelineRunResult:
    """Complete structured output and telemetry for a pipeline execution."""

    video_id: str
    decision: ModerationDecision
    risk_level: RiskLevel
    risk_score: float
    overall_confidence: float
    moderation_result: ModerationResult
    report: Any  # ModerationReportResponse
    detections: list[VisualDetection] = field(default_factory=list)
    transcripts: list[TranscriptSegment] = field(default_factory=list)
    text_signals: list[TextModerationSignal] = field(default_factory=list)
    context: ContextualInterpretation | None = None
    frame_count: int = 0
    audio_extracted: bool = False
    stage_durations: dict[str, float] = field(default_factory=dict)
    total_duration: float = 0.0


StageCallback = Callable[[str, dict[str, Any]], None]


class PipelineRunner:
    """Production orchestrator executing the full multi-modal moderation pipeline.

    Orchestrates:
      1. Storage & Video record resolution
      2. Deterministic frame sampling (OpenCV)
      3. Audio track extraction (FFprobe / FFmpeg)
      4. YOLO vision analysis (Visual safety & object detection)
      5. Whisper transcription (Speech-to-text)
      6. Toxic-BERT text moderation (Toxic speech classification)
      7. Qwen 2.5-VL contextual analysis (Multi-modal temporal reasoning)
      8. ModerationEngine (Policy evaluation & calibrated risk scoring)
      9. ModerationPersistenceService (PostgreSQL persistence & COMPLETED status)
     10. ModerationReportService (Structured explainable report generation)
    """

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        storage: LocalStorageService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()

        # Resolve storage directory
        resolved_storage_path = Path(self.settings.storage_path)
        if not resolved_storage_path.is_absolute():
            # If storage_path is relative, resolve from current directory or root
            if resolved_storage_path.exists():
                resolved_storage_path = resolved_storage_path.resolve()
            else:
                root = Path(__file__).resolve().parents[4]
                resolved_storage_path = (root / resolved_storage_path).resolve()

        self.storage = storage or LocalStorageService(root_path=resolved_storage_path)
        self.repository = ModerationRepository(session)
        self.persistence_service = ModerationPersistenceService(self.repository)
        self.report_service = ModerationReportService(self.repository)

    def _resolve_video_file_path(self, video: Video) -> Path:
        """Resolve the on-disk video file path, checking common locations if relative."""
        raw_path = Path(video.storage_path)
        if raw_path.is_absolute() and raw_path.exists():
            return raw_path

        candidates = [
            raw_path,
            self.storage.root_path / raw_path,
            self.storage.root_path / "videos" / raw_path,
            self.storage.root_path / "videos" / raw_path.name,
            Path.cwd() / raw_path,
        ]
        for cand in candidates:
            if cand.exists():
                return cand.resolve()

        raise FileNotFoundError(
            f"Video file '{video.filename}' not found at storage path: {video.storage_path}"
        )

    def run(
        self,
        video_id: str,
        stage_callback: StageCallback | None = None,
    ) -> PipelineRunResult:
        """Execute the complete moderation pipeline for a registered video ID.

        Transitions:
          - Validates video exists and is accessible
          - Advances video status to ANALYZING during multi-modal AI execution
          - Atomically commits results and COMPLETED status via ModerationPersistenceService
          - On unhandled failure, rolls back and marks video status as FAILED before re-raising
        """
        overall_start = time.perf_counter()
        stage_durations: dict[str, float] = {}
        current_stage = "Initialization"

        logger.info("Starting pipeline execution for video '%s'", video_id)

        try:
            # 1. Fetch video record
            video = self.session.get(Video, video_id)
            if video is None:
                raise PipelineExecutionError(f"Video '{video_id}' not found in database.", stage=current_stage)

            # Resolve file path
            resolved_path = self._resolve_video_file_path(video)
            video.storage_path = str(resolved_path)

            def notify_stage(name: str, **kwargs: Any) -> None:
                if stage_callback:
                    stage_callback(name, kwargs)

            # -------------------------------------------------------------
            # Stage 1: Frame Processing
            # -------------------------------------------------------------
            current_stage = "Frame Processing"
            s_start = time.perf_counter()
            frame_service = FrameProcessingService(
                storage=self.storage,
                interval_seconds=self.settings.frame_sampling_interval_seconds,
                image_format=self.settings.frame_image_format,
                quality=self.settings.frame_image_quality,
            )
            frame_artifacts = frame_service.extract(video)
            timestamped_frames = [
                TimestampedFrame(
                    frame_id=fa.frame_id,
                    timestamp=fa.timestamp,
                    storage_path=str(fa.storage_path.resolve()),
                )
                for fa in frame_artifacts
            ]
            s_dur = time.perf_counter() - s_start
            stage_durations["frame_processing"] = s_dur
            notify_stage(
                "frame_processing",
                duration=s_dur,
                frame_count=len(timestamped_frames),
                frames=timestamped_frames,
            )
            logger.debug("Extracted %d frames in %.2fs", len(timestamped_frames), s_dur)

            # -------------------------------------------------------------
            # Stage 2: Audio Extraction
            # -------------------------------------------------------------
            current_stage = "Audio Extraction"
            s_start = time.perf_counter()
            audio_service = AudioProcessingService(
                storage=self.storage,
                output_format=self.settings.audio_output_format,
            )
            audio_artifact = audio_service.extract(video)
            s_dur = time.perf_counter() - s_start
            stage_durations["audio_extraction"] = s_dur
            notify_stage(
                "audio_extraction",
                duration=s_dur,
                audio_available=audio_artifact.audio_available,
                artifact=audio_artifact,
            )
            logger.debug("Audio extracted (available=%s) in %.2fs", audio_artifact.audio_available, s_dur)

            # -------------------------------------------------------------
            # Stage 3: Advance State to ANALYZING
            # -------------------------------------------------------------
            video.status = VideoStatus.ANALYZING
            self.session.commit()
            self.session.refresh(video)

            # -------------------------------------------------------------
            # Stage 4: Vision Analysis (YOLO)
            # -------------------------------------------------------------
            current_stage = "Vision Analysis"
            s_start = time.perf_counter()
            vision_analyzer = get_vision_analyzer(self.settings)
            detections = vision_analyzer.analyze(timestamped_frames)
            s_dur = time.perf_counter() - s_start
            stage_durations["vision_analysis"] = s_dur
            notify_stage(
                "vision_analysis",
                duration=s_dur,
                detections=detections,
            )
            logger.debug("Vision analysis found %d detections in %.2fs", len(detections), s_dur)

            # -------------------------------------------------------------
            # Stage 5: Speech Transcription (Whisper)
            # -------------------------------------------------------------
            current_stage = "Transcription"
            s_start = time.perf_counter()
            transcriber = get_transcriber(self.settings)
            transcripts = transcriber.transcribe(audio_artifact)
            s_dur = time.perf_counter() - s_start
            stage_durations["transcription"] = s_dur
            notify_stage(
                "transcription",
                duration=s_dur,
                transcripts=transcripts,
            )
            logger.debug("Transcription produced %d segments in %.2fs", len(transcripts), s_dur)

            # -------------------------------------------------------------
            # Stage 6: Text Moderation (Toxic-BERT)
            # -------------------------------------------------------------
            current_stage = "Text Moderation"
            s_start = time.perf_counter()
            text_moderator = get_text_moderator(self.settings)
            text_signals = text_moderator.moderate(transcripts)
            s_dur = time.perf_counter() - s_start
            stage_durations["text_moderation"] = s_dur
            notify_stage(
                "text_moderation",
                duration=s_dur,
                signals=text_signals,
            )
            logger.debug("Text moderation produced %d signals in %.2fs", len(text_signals), s_dur)

            # -------------------------------------------------------------
            # Stage 7: Context Analysis (Qwen 2.5-VL)
            # -------------------------------------------------------------
            current_stage = "Context Analysis"
            s_start = time.perf_counter()
            context_analyzer = get_context_analyzer(self.settings)
            interpretation = context_analyzer.analyze(
                detections=detections,
                transcripts=transcripts,
                signals=text_signals,
                frames=timestamped_frames,
            )
            s_dur = time.perf_counter() - s_start
            stage_durations["context_analysis"] = s_dur
            notify_stage(
                "context_analysis",
                duration=s_dur,
                interpretation=interpretation,
            )
            logger.debug(
                "Context analysis category '%s' (conf=%.2f) in %.2fs",
                interpretation.category if interpretation else "None",
                interpretation.confidence if interpretation else 0.0,
                s_dur,
            )

            # -------------------------------------------------------------
            # Stage 8: Moderation Engine (Decision Synthesis)
            # -------------------------------------------------------------
            current_stage = "Moderation Engine"
            s_start = time.perf_counter()
            mod_config = ModerationConfig(
                low_risk_threshold=self.settings.moderation_low_risk_threshold,
                medium_risk_threshold=self.settings.moderation_medium_risk_threshold,
                high_risk_threshold=self.settings.moderation_high_risk_threshold,
                auto_reject_threshold=self.settings.moderation_auto_reject_threshold,
                review_threshold=self.settings.moderation_review_threshold,
                min_signal_confidence=self.settings.moderation_min_signal_confidence,
            )
            engine = ModerationEngine(config=mod_config)
            moderation_result = engine.evaluate(
                detections=detections,
                transcripts=transcripts,
                text_signals=text_signals,
                context=interpretation,
            )
            s_dur = time.perf_counter() - s_start
            stage_durations["moderation_engine"] = s_dur
            notify_stage(
                "moderation_engine",
                duration=s_dur,
                result=moderation_result,
            )
            logger.debug(
                "Moderation decision '%s', risk '%s' (%.2f) in %.4fs",
                moderation_result.decision.value,
                moderation_result.risk_level.value,
                moderation_result.risk_score,
                s_dur,
            )

            # -------------------------------------------------------------
            # Stage 9: Persistence (Advances status to COMPLETED & commits)
            # -------------------------------------------------------------
            current_stage = "Persistence"
            s_start = time.perf_counter()
            self.persistence_service.persist_moderation_run(
                video_id=video.id,
                result=moderation_result,
                transcripts=transcripts,
                detections=detections,
                text_signals=text_signals,
                context=interpretation,
            )
            report = self.report_service.get_moderation_report(video.id)
            s_dur = time.perf_counter() - s_start
            stage_durations["persistence_reporting"] = s_dur
            notify_stage(
                "persistence_reporting",
                duration=s_dur,
                report=report,
            )

            total_duration = time.perf_counter() - overall_start
            logger.info(
                "Pipeline completed for video '%s' in %.2fs -> %s (risk=%.2f)",
                video.id,
                total_duration,
                moderation_result.decision.value,
                moderation_result.risk_score,
            )

            return PipelineRunResult(
                video_id=video.id,
                decision=moderation_result.decision,
                risk_level=moderation_result.risk_level,
                risk_score=moderation_result.risk_score,
                overall_confidence=moderation_result.overall_confidence,
                moderation_result=moderation_result,
                report=report,
                detections=detections,
                transcripts=transcripts,
                text_signals=text_signals,
                context=interpretation,
                frame_count=len(timestamped_frames),
                audio_extracted=audio_artifact.audio_available,
                stage_durations=stage_durations,
                total_duration=total_duration,
            )

        except Exception as exc:
            total_duration = time.perf_counter() - overall_start
            logger.error(
                "Pipeline failed for video '%s' during '%s' after %.2fs: %s",
                video_id,
                current_stage,
                total_duration,
                exc,
            )
            # Roll back dirty transactional state
            try:
                self.session.rollback()
            except Exception:
                pass

            # Update database status to FAILED
            try:
                failed_video = self.session.get(Video, video_id)
                if failed_video is not None:
                    failed_video.status = VideoStatus.FAILED
                    self.session.commit()
            except Exception as db_exc:
                logger.error("Failed to commit FAILED status for video '%s': %s", video_id, db_exc)
                try:
                    self.session.rollback()
                except Exception:
                    pass

            raise PipelineExecutionError(
                f"Pipeline execution failed for video '{video_id}' at stage '{current_stage}': {exc}",
                stage=current_stage,
                original_error=exc,
            ) from exc

    def register_and_run(
        self,
        video_path: Path,
        video_id: str | None = None,
        stage_callback: StageCallback | None = None,
    ) -> PipelineRunResult:
        """Helper for test scripts and evaluation runners to register an ad-hoc video and execute the pipeline."""
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        metadata_service = VideoMetadataService()
        metadata = metadata_service.extract(video_path)

        vid_id = video_id or f"test_{video_path.stem.lower().replace(' ', '_')}"
        vid_repo = VideoRepository(self.session)
        existing = vid_repo.get(vid_id)

        if existing is None:
            new_video = Video(
                id=vid_id,
                filename=video_path.name,
                storage_path=str(video_path.resolve()),
                duration=metadata.duration,
                file_size=video_path.stat().st_size,
                width=metadata.width,
                height=metadata.height,
                fps=metadata.fps,
                status=VideoStatus.PROCESSING,
            )
            vid_repo.add(new_video)
        else:
            existing.filename = video_path.name
            existing.storage_path = str(video_path.resolve())
            existing.duration = metadata.duration
            existing.file_size = video_path.stat().st_size
            existing.width = metadata.width
            existing.height = metadata.height
            existing.fps = metadata.fps
            existing.status = VideoStatus.PROCESSING
            self.session.commit()

        return self.run(video_id=vid_id, stage_callback=stage_callback)
