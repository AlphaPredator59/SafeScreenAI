"""Tests for the production PipelineRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.database import get_session_factory
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Video
from app.services.moderation import (
    PipelineExecutionError,
    PipelineRunResult,
    PipelineRunner,
)


def create_dummy_video(session: Session, storage_path: str, status: VideoStatus = VideoStatus.UPLOADED) -> Video:
    vid = Video(
        id=f"test_vid_{uuid4().hex[:8]}",
        filename="test_video.mp4",
        storage_path=storage_path,
        duration=2.0,
        file_size=1024,
        width=1280,
        height=720,
        fps=30.0,
        status=status,
    )
    session.add(vid)
    session.commit()
    session.refresh(vid)
    return vid


def test_pipeline_runner_mock_success(tmp_path: Path):
    """Test full execution of PipelineRunner in mock AI mode."""
    # Create a small valid test video in tmp_path or find existing test video
    root_dir = Path(__file__).resolve().parents[2]
    test_videos = list((root_dir / "Test Videos").glob("*.mp4"))
    assert test_videos, "At least one test video should be available"
    real_video_path = test_videos[0]

    session_factory = get_session_factory()
    with session_factory() as session:
        video = create_dummy_video(session, str(real_video_path.resolve()), VideoStatus.UPLOADED)
        video_id = video.id

        settings = Settings(
            ai_mode="mock",
            ai_device="cpu",
            frame_sampling_interval_seconds=1.0,
            storage_path=tmp_path / "storage",
        )

        runner = PipelineRunner(session=session, settings=settings)
        result: PipelineRunResult = runner.run(video_id=video_id)

        assert result.video_id == video_id
        assert result.decision in (ModerationDecision.APPROVED, ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert result.total_duration > 0.0
        assert "frame_processing" in result.stage_durations
        assert "persistence_reporting" in result.stage_durations

        # Verify DB status is COMPLETED
        updated = session.get(Video, video_id)
        assert updated is not None
        assert updated.status == VideoStatus.COMPLETED


def test_pipeline_runner_missing_video_file_fails_gracefully(tmp_path: Path):
    """Test that a non-existent video file results in FAILED state and PipelineExecutionError."""
    session_factory = get_session_factory()
    with session_factory() as session:
        fake_path = str(tmp_path / "non_existent.mp4")
        video = create_dummy_video(session, fake_path, VideoStatus.UPLOADED)
        video_id = video.id

        settings = Settings(
            ai_mode="mock",
            ai_device="cpu",
            storage_path=tmp_path / "storage",
        )

        runner = PipelineRunner(session=session, settings=settings)
        with pytest.raises(PipelineExecutionError) as exc_info:
            runner.run(video_id=video_id)

        assert "non_existent.mp4" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

        # Verify database status was set to FAILED
        updated = session.get(Video, video_id)
        assert updated is not None
        assert updated.status == VideoStatus.FAILED


def test_pipeline_runner_stage_callback(tmp_path: Path):
    """Test that stage_callback is called during execution."""
    root_dir = Path(__file__).resolve().parents[2]
    test_videos = list((root_dir / "Test Videos").glob("*.mp4"))
    real_video_path = test_videos[0]

    stages_called = []

    def callback(stage_name, data):
        stages_called.append(stage_name)

    session_factory = get_session_factory()
    with session_factory() as session:
        video = create_dummy_video(session, str(real_video_path.resolve()), VideoStatus.UPLOADED)
        settings = Settings(
            ai_mode="mock",
            ai_device="cpu",
            frame_sampling_interval_seconds=1.0,
            storage_path=tmp_path / "storage",
        )
        runner = PipelineRunner(session=session, settings=settings)
        runner.run(video_id=video.id, stage_callback=callback)

    assert "frame_processing" in stages_called
    assert "audio_extraction" in stages_called
    assert "vision_analysis" in stages_called
    assert "transcription" in stages_called
    assert "text_moderation" in stages_called
    assert "context_analysis" in stages_called
    assert "moderation_engine" in stages_called
    assert "persistence_reporting" in stages_called
