"""Tests for moderation-domain persistence behavior."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db import database
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Detection, Evidence, ModerationResult, TranscriptSegment, Video


def build_video() -> Video:
    """Create a valid video object for tests."""
    return Video(
        filename="sample.mp4",
        storage_path="storage/sample.mp4",
        duration=10.5,
        file_size=1024,
        width=1920,
        height=1080,
        fps=30.0,
    )


def test_enum_values_match_persisted_domain_values() -> None:
    """Controlled enums use the values defined in the project specification."""
    assert [status.value for status in VideoStatus] == [
        "UPLOADED", "QUEUED", "PROCESSING", "ANALYZING", "COMPLETED", "FAILED"
    ]
    assert [decision.value for decision in ModerationDecision] == ["APPROVED", "REVIEW_REQUIRED", "REJECTED"]
    assert [risk.value for risk in RiskLevel] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_relationships_persist_and_cascade_from_video(db_session: Session) -> None:
    """Video-owned domain objects are saved and removed as one aggregate."""
    video = build_video()
    result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        overall_confidence=0.87,
    )
    detection = Detection(category="violence", confidence=0.81, start_timestamp=4.0, end_timestamp=7.5)
    detection.evidence_items.append(Evidence(type="frame", timestamp=4.0, storage_path="storage/frame.jpg"))
    result.detections.append(detection)
    video.moderation_results.append(result)
    video.transcript_segments.append(TranscriptSegment(start_timestamp=4.0, end_timestamp=5.0, text="Stop."))

    db_session.add(video)
    db_session.commit()

    assert len(video.moderation_results) == 1
    assert len(result.detections) == 1
    assert len(detection.evidence_items) == 1
    assert len(video.transcript_segments) == 1

    db_session.delete(video)
    db_session.commit()

    assert db_session.query(ModerationResult).count() == 0
    assert db_session.query(Detection).count() == 0
    assert db_session.query(Evidence).count() == 0
    assert db_session.query(TranscriptSegment).count() == 0


def test_confidence_constraint_rejects_invalid_values(db_session: Session) -> None:
    """Database-level confidence checks prevent invalid persisted data."""
    video = build_video()
    db_session.add(video)
    db_session.commit()

    db_session.add(
        ModerationResult(
            video_id=video.id,
            decision=ModerationDecision.APPROVED,
            risk_level=RiskLevel.LOW,
            overall_confidence=1.1,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_session_dependency_closes_session(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """The dependency reliably closes sessions after the caller is finished."""
    class RecordingSession(Session):
        was_closed = False

        def close(self) -> None:
            self.was_closed = True
            super().close()

    factory = sessionmaker(bind=db_session.get_bind(), class_=RecordingSession)
    monkeypatch.setattr(database, "get_session_factory", lambda: factory)

    dependency = database.get_db_session()
    session = next(dependency)
    dependency.close()

    assert isinstance(session, RecordingSession)
    assert session.was_closed is True
