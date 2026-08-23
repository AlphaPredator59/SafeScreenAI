"""Deterministic unit tests for moderation persistence, rollback, and report generation."""

from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Detection, Evidence, ModerationResult as DBModerationResult, TranscriptSegment as DBTranscriptSegment, Video
from app.services.ai.contracts import (
    ContextualInterpretation,
    TextModerationSignal,
    TranscriptSegment,
    VisualDetection,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult
from app.services.moderation.persistence import ModerationPersistenceError, ModerationPersistenceService
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository, ModerationRepositoryError


def create_test_video(db_session: Session, video_id: str = "vid_test_001") -> Video:
    """Helper to insert a base video record for tests."""
    video = Video(
        id=video_id,
        filename="test_sample.mp4",
        storage_path="storage/videos/test_sample.mp4",
        duration=10.0,
        file_size=1024 * 1024,
        width=1920,
        height=1080,
        fps=30.0,
        status=VideoStatus.PROCESSING,
    )
    db_session.add(video)
    db_session.commit()
    return video


def test_persist_approved_cooking_result_has_zero_policy_violations(db_session: Session) -> None:
    """Cooking scenario: knife in cooking context produces APPROVED/LOW and zero policy violation rows in detections table."""
    video = create_test_video(db_session, "vid_cooking_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.0,
        overall_confidence=0.95,
        detected_categories=(),  # No policy violations
        supporting_evidence=(
            EvidenceItem(modality="visual", category="knife", confidence=0.92, reference="frame_0001", timestamp=1.0, description="Visual detection of knife"),
            EvidenceItem(modality="context", category="Cooking", confidence=0.95, reference="frame_0001", description="Cooking demonstration"),
        ),
        explanation="Verified benign context ('Cooking') confirms objects are non-harmful tools, mitigating risk.",
    )

    persisted = service.persist_moderation_run(
        video_id=video.id,
        result=m8_result,
        transcripts=(),
    )

    assert persisted.video_id == video.id
    assert persisted.decision == ModerationDecision.APPROVED
    assert persisted.risk_level == RiskLevel.LOW
    assert persisted.risk_score == 0.0
    assert persisted.overall_confidence == 0.95
    assert len(persisted.detections) == 0  # Crucial requirement: zero policy violation rows

    # Verify video status advanced to COMPLETED
    reloaded_video = repository.get_video(video.id)
    assert reloaded_video.status == VideoStatus.COMPLETED


def test_persist_slap_review_required_result(db_session: Session) -> None:
    """Slap scenario: threatening interaction persists policy detection 'threats' with linked traceable evidence."""
    video = create_test_video(db_session, "vid_slap_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.765,
        overall_confidence=0.90,
        detected_categories=("threats",),
        supporting_evidence=(
            EvidenceItem(modality="visual", category="person", confidence=0.92, reference="frame_0005", timestamp=2.0, description="Person visual detection"),
            EvidenceItem(modality="context", category="threatening interaction", confidence=0.90, reference="frame_0005", timestamp=2.0, description="Threatening altercation detected"),
        ),
        explanation="Identified threatening interaction reinforced policy risk.",
    )

    transcripts = [
        TranscriptSegment(start=0.0, end=2.0, text="Hey!"),
    ]

    persisted = service.persist_moderation_run(
        video_id=video.id,
        result=m8_result,
        transcripts=transcripts,
    )

    assert persisted.decision == ModerationDecision.REVIEW_REQUIRED
    assert persisted.risk_level == RiskLevel.HIGH
    assert persisted.risk_score == 0.765
    assert len(persisted.detections) == 1
    assert persisted.detections[0].category == "threats"
    assert persisted.detections[0].confidence == 0.92
    assert len(persisted.detections[0].evidence_items) == 2

    # Check transcript rows
    stored_tx = repository.get_transcript_segments_by_video_id(video.id)
    assert len(stored_tx) == 1
    assert stored_tx[0].text == "Hey!"


def test_persist_rejected_result(db_session: Session) -> None:
    """Rejected result: critical safety violation persisted."""
    video = create_test_video(db_session, "vid_rejected_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.REJECTED,
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.95,
        overall_confidence=0.92,
        detected_categories=("child_safety",),
        supporting_evidence=(
            EvidenceItem(modality="text_signal", category="child_safety", confidence=0.92, reference="text_01", timestamp=1.5, description="Child safety flag"),
        ),
        explanation="Immediate policy violation for child safety.",
    )

    persisted = service.persist_moderation_run(video_id=video.id, result=m8_result)
    assert persisted.decision == ModerationDecision.REJECTED
    assert persisted.risk_level == RiskLevel.CRITICAL
    assert persisted.risk_score == 0.95
    assert len(persisted.detections) == 1
    assert persisted.detections[0].category == "child_safety"


def test_raw_yolo_objects_not_persisted_as_policy_violations(db_session: Session) -> None:
    """Harmless detected objects (broccoli, spoon, bowl) are not persisted into detections table."""
    video = create_test_video(db_session, "vid_everyday_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.0,
        overall_confidence=1.0,
        detected_categories=(),
        supporting_evidence=(
            EvidenceItem(modality="visual", category="bowl", confidence=0.88, reference="frame_01", timestamp=1.0),
            EvidenceItem(modality="visual", category="spoon", confidence=0.85, reference="frame_01", timestamp=1.0),
        ),
        explanation="Clean content.",
    )

    service.persist_moderation_run(video_id=video.id, result=m8_result)

    # Detections table must be empty for this result
    assert db_session.query(Detection).count() == 0


def test_no_audio_video_persistence_creates_zero_transcript_rows(db_session: Session) -> None:
    """Video without audio persists 0 transcript rows without error."""
    video = create_test_video(db_session, "vid_silent_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.0,
        overall_confidence=1.0,
        detected_categories=(),
        supporting_evidence=(),
        explanation="Silent video approved.",
    )

    service.persist_moderation_run(video_id=video.id, result=m8_result, transcripts=())

    tx_rows = repository.get_transcript_segments_by_video_id(video.id)
    assert len(tx_rows) == 0


def test_persistence_rollback_on_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """If database save fails, the transaction rolls back cleanly."""
    video = create_test_video(db_session, "vid_fail_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.0,
        overall_confidence=1.0,
        detected_categories=(),
        supporting_evidence=(),
        explanation="Test.",
    )

    # Force an integrity or commit error
    def faulty_commit():
        raise RuntimeError("Database connection dropped")

    monkeypatch.setattr(db_session, "commit", faulty_commit)

    with pytest.raises(ModerationPersistenceError, match="Database connection dropped"):
        service.persist_moderation_run(video_id=video.id, result=m8_result)

    # Verify no moderation results were saved
    assert db_session.query(DBModerationResult).count() == 0


def test_repeated_processing_replaces_old_moderation_tree(db_session: Session) -> None:
    """Re-moderating a video replaces previous moderation results, findings, and transcripts without duplicates."""
    video = create_test_video(db_session, "vid_repeat_01")
    repository = ModerationRepository(db_session)
    service = ModerationPersistenceService(repository)

    # First run: initial review required
    result1 = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.75,
        overall_confidence=0.85,
        detected_categories=("weapons",),
        supporting_evidence=(EvidenceItem(modality="visual", category="knife", confidence=0.85, reference="f1", timestamp=1.0),),
        explanation="Unverified knife.",
    )
    tx1 = [TranscriptSegment(start=0.0, end=2.0, text="Initial dialogue")]
    service.persist_moderation_run(video_id=video.id, result=result1, transcripts=tx1)

    assert db_session.query(DBModerationResult).filter_by(video_id=video.id).count() == 1
    assert db_session.query(Detection).count() == 1
    assert db_session.query(Evidence).count() == 1
    assert db_session.query(DBTranscriptSegment).filter_by(video_id=video.id).count() == 1

    # Second run: re-processed as approved with culinary context
    result2 = ModerationResult(
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.0,
        overall_confidence=0.95,
        detected_categories=(),
        supporting_evidence=(EvidenceItem(modality="context", category="Cooking", confidence=0.95, reference="f1", timestamp=1.0),),
        explanation="Re-evaluated as cooking.",
    )
    tx2 = [TranscriptSegment(start=0.0, end=2.0, text="Updated dialogue")]
    service.persist_moderation_run(video_id=video.id, result=result2, transcripts=tx2)

    # Exactly 1 active moderation result exists, with old detections replaced
    results = db_session.query(DBModerationResult).filter_by(video_id=video.id).all()
    assert len(results) == 1
    assert results[0].decision == ModerationDecision.APPROVED
    assert len(results[0].detections) == 0
    assert db_session.query(Detection).count() == 0

    transcripts = repository.get_transcript_segments_by_video_id(video.id)
    assert len(transcripts) == 1
    assert transcripts[0].text == "Updated dialogue"


def test_report_generation_from_persisted_records(db_session: Session) -> None:
    """ModerationReportService constructs structured public report from persisted DB records."""
    video = create_test_video(db_session, "vid_report_01")
    repository = ModerationRepository(db_session)
    persistence_service = ModerationPersistenceService(repository)
    report_service = ModerationReportService(repository)

    m8_result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.765,
        overall_confidence=0.90,
        detected_categories=("threats",),
        supporting_evidence=(
            EvidenceItem(modality="visual", category="person", confidence=0.90, reference="frame_0001", timestamp=1.5, description="Visual person frame"),
            EvidenceItem(modality="context", category="threatening interaction", confidence=0.90, reference="frame_0001", timestamp=1.5, description="Threatening context"),
        ),
        explanation="Threatening interaction detected.",
    )
    transcripts = [TranscriptSegment(start=1.0, end=3.0, text="Hey!")]

    persistence_service.persist_moderation_run(video_id=video.id, result=m8_result, transcripts=transcripts)

    report = report_service.get_moderation_report(video.id)
    assert report is not None
    assert report.video_id == video.id
    assert report.filename == video.filename
    assert report.decision == ModerationDecision.REVIEW_REQUIRED
    assert report.risk_level == RiskLevel.HIGH
    assert report.risk_score == 0.765
    assert report.overall_confidence == 0.90
    assert report.detected_categories == ["threats"]
    assert len(report.findings) == 1
    assert report.findings[0].category == "threats"
    assert len(report.evidence) == 2
    assert len(report.transcripts) == 1


def test_report_does_not_expose_internal_paths_or_secrets(db_session: Session) -> None:
    """Public report and evidence models do not leak host absolute storage paths."""
    video = create_test_video(db_session, "vid_security_01")
    repository = ModerationRepository(db_session)
    persistence_service = ModerationPersistenceService(repository)
    report_service = ModerationReportService(repository)

    # Reference containing local OS file path
    m8_result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.70,
        overall_confidence=0.85,
        detected_categories=("violence",),
        supporting_evidence=(
            EvidenceItem(
                modality="visual",
                category="violence",
                confidence=0.85,
                reference=r"C:\Users\SecretUser\Project\storage\frames\frame_001.jpg",
                timestamp=1.0,
                description="Evidence",
            ),
        ),
        explanation="Violence detected.",
    )

    persistence_service.persist_moderation_run(video_id=video.id, result=m8_result)
    report = report_service.get_moderation_report(video.id)

    assert report is not None
    for ev in report.evidence:
        assert "C:\\" not in (ev.reference or "")
        assert "SecretUser" not in (ev.reference or "")
        assert ev.reference == "frame_001.jpg"
