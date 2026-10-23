"""Unit tests verifying event-level timestamps, genuine confidence preservation, and evidence attribution."""

from sqlalchemy.orm import Session
import pytest

from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Detection, Evidence, Video
from app.services.moderation.contracts import EvidenceItem, ModerationResult, PolicyEvent, PolicyFinding
from app.services.moderation.persistence import ModerationPersistenceService
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository
from app.services.moderation.temporal_grouping import (
    build_policy_findings,
    cluster_evidence_into_events,
    get_category_supporting_evidence,
)


def create_test_video(db_session: Session, video_id: str, duration: float = 275.0) -> Video:
    """Helper to insert a test video record."""
    video = Video(
        id=video_id,
        filename="test_video.mp4",
        storage_path=f"storage/videos/{video_id}.mp4",
        duration=duration,
        file_size=10 * 1024 * 1024,
        width=1920,
        height=1080,
        fps=30.0,
        status=VideoStatus.PROCESSING,
    )
    db_session.add(video)
    db_session.commit()
    return video


def test_events_at_separated_intervals_do_not_become_full_video_duration(db_session: Session) -> None:
    """Requirement 1: Events at 20-40s and 80-110s must NOT collapse to 0 -> video_duration."""
    video = create_test_video(db_session, "vid_interval_test_01", duration=275.0)
    repository = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repository)
    reporting = ModerationReportService(repository)

    # Evidence items at 20-40s and 80-110s
    evidence = (
        EvidenceItem(
            modality="context",
            category="threatening altercation",
            confidence=0.95,
            reference="ctx_win_20_40",
            timestamp=20.0,
            end_timestamp=40.0,
            description="Threatening altercation at 20-40s",
        ),
        EvidenceItem(
            modality="context",
            category="threatening altercation",
            confidence=0.88,
            reference="ctx_win_80_110",
            timestamp=80.0,
            end_timestamp=110.0,
            description="Threatening altercation at 80-110s",
        ),
    )

    findings = build_policy_findings(
        detected_categories=["threats"],
        evidence_items=evidence,
    )

    assert len(findings) == 1
    threat_finding = findings[0]
    assert threat_finding.category == "threats"
    assert len(threat_finding.events) == 2

    ev1, ev2 = threat_finding.events
    assert ev1.start_time == 20.0
    assert ev1.end_time == 40.0
    assert ev1.confidence == 0.95

    assert ev2.start_time == 80.0
    assert ev2.end_time == 110.0
    assert ev2.confidence == 0.88

    # Persist and retrieve report
    mod_result = ModerationResult(
        decision=ModerationDecision.REJECTED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.85,
        overall_confidence=0.91,
        detected_categories=("threats",),
        supporting_evidence=evidence,
        explanation="Threats detected in discrete intervals.",
        findings=tuple(findings),
    )

    persistence.persist_moderation_run(video_id=video.id, result=mod_result)
    report = reporting.get_moderation_report(video.id)

    assert report is not None
    assert len(report.findings) == 1
    rep_finding = report.findings[0]

    # Crucial assertions:
    # 1. Does NOT start at 0.0 or end at 275.0
    assert rep_finding.start_timestamp == 20.0
    assert rep_finding.end_timestamp == 110.0
    assert rep_finding.start_timestamp > 0.0
    assert rep_finding.end_timestamp < 275.0

    # 2. Contains the 2 discrete events with their exact intervals
    assert len(rep_finding.events) == 2
    assert rep_finding.events[0].start_time == 20.0
    assert rep_finding.events[0].end_time == 40.0
    assert rep_finding.events[0].confidence == 0.95

    assert rep_finding.events[1].start_time == 80.0
    assert rep_finding.events[1].end_time == 110.0
    assert rep_finding.events[1].confidence == 0.88


def test_separate_findings_have_different_event_timestamps(db_session: Session) -> None:
    """Requirement 2: Separate policy findings (e.g. Threats vs Toxic) must have different event timestamps."""
    video = create_test_video(db_session, "vid_separate_cats_01", duration=300.0)
    repository = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repository)
    reporting = ModerationReportService(repository)

    evidence = (
        EvidenceItem(
            modality="context",
            category="threatening interaction",
            confidence=0.95,
            reference="ctx_threat_50_95",
            timestamp=50.0,
            end_timestamp=95.0,
            description="Threatening dialogue and context",
        ),
        EvidenceItem(
            modality="text_signal",
            category="toxic",
            confidence=0.67,
            reference="text_sig_250_255",
            timestamp=250.86,
            end_timestamp=255.0,
            description="Toxic text signal",
        ),
    )

    findings = build_policy_findings(
        detected_categories=["threats", "toxic"],
        evidence_items=evidence,
    )

    assert len(findings) == 2
    threats_finding = next(f for f in findings if f.category == "threats")
    toxic_finding = next(f for f in findings if f.category == "toxic")

    assert len(threats_finding.events) == 1
    assert threats_finding.events[0].start_time == 50.0
    assert threats_finding.events[0].end_time == 95.0

    assert len(toxic_finding.events) == 1
    assert toxic_finding.events[0].start_time == 250.86
    assert toxic_finding.events[0].end_time == 255.0

    # Timestamps are strictly disjoint and different
    assert threats_finding.events[0].end_time < toxic_finding.events[0].start_time

    # Persist and verify in report
    mod_result = ModerationResult(
        decision=ModerationDecision.REJECTED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.85,
        overall_confidence=0.68,
        detected_categories=("threats", "toxic"),
        supporting_evidence=evidence,
        explanation="Multi-policy findings.",
        findings=tuple(findings),
    )

    persistence.persist_moderation_run(video_id=video.id, result=mod_result)
    report = reporting.get_moderation_report(video.id)

    assert report is not None
    rep_threats = next(f for f in report.findings if f.category == "threats")
    rep_toxic = next(f for f in report.findings if f.category == "toxic")

    assert rep_threats.start_timestamp == 50.0
    assert rep_threats.end_timestamp == 95.0

    assert rep_toxic.start_timestamp == 250.86
    assert rep_toxic.end_timestamp == 255.0


def test_confidence_values_such_as_095_and_067_are_preserved(db_session: Session) -> None:
    """Requirement 3: Confidence values must NOT become 100% / 1.0."""
    video = create_test_video(db_session, "vid_conf_test_01", duration=300.0)
    repository = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repository)
    reporting = ModerationReportService(repository)

    evidence = (
        EvidenceItem(
            modality="context",
            category="threatening altercation",
            confidence=0.95,
            reference="ref_threat",
            timestamp=50.0,
            end_timestamp=95.0,
        ),
        EvidenceItem(
            modality="text_signal",
            category="toxic",
            confidence=0.67,
            reference="ref_toxic",
            timestamp=250.0,
            end_timestamp=255.0,
        ),
        # Harmless object with high detector confidence should NOT inflate policy confidence
        EvidenceItem(
            modality="visual",
            category="person",
            confidence=0.999,
            reference="frame_0001",
            timestamp=5.0,
        ),
    )

    findings = build_policy_findings(
        detected_categories=["threats", "toxic"],
        evidence_items=evidence,
    )

    mod_result = ModerationResult(
        decision=ModerationDecision.REJECTED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.85,
        overall_confidence=0.68,
        detected_categories=("threats", "toxic"),
        supporting_evidence=evidence,
        explanation="Testing confidence preservation.",
        findings=tuple(findings),
    )

    persistence.persist_moderation_run(video_id=video.id, result=mod_result)
    report = reporting.get_moderation_report(video.id)

    assert report is not None
    rep_threats = next(f for f in report.findings if f.category == "threats")
    rep_toxic = next(f for f in report.findings if f.category == "toxic")

    # Confidences must be preserved precisely, NOT 1.0
    assert rep_threats.confidence == 0.95
    assert rep_threats.events[0].confidence == 0.95

    assert rep_toxic.confidence == 0.67
    assert rep_toxic.events[0].confidence == 0.67


def test_evidence_ids_associated_only_with_correct_finding(db_session: Session) -> None:
    """Requirement 4: Evidence IDs must be attached only to the findings/events they actually support."""
    video = create_test_video(db_session, "vid_evidence_assoc_01", duration=300.0)
    repository = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repository)
    reporting = ModerationReportService(repository)

    threat_ev = EvidenceItem(
        modality="context",
        category="threatening interaction",
        confidence=0.95,
        reference="evidence_threat_01",
        timestamp=50.0,
        end_timestamp=95.0,
        description="Threat context item",
    )
    toxic_ev = EvidenceItem(
        modality="text_signal",
        category="toxic",
        confidence=0.67,
        reference="evidence_toxic_01",
        timestamp=250.0,
        end_timestamp=255.0,
        description="Toxic text item",
    )
    irrelevant_vis = EvidenceItem(
        modality="visual",
        category="person",
        confidence=0.98,
        reference="evidence_person_01",
        timestamp=10.0,
        description="Unrelated visual person",
    )

    evidence = (threat_ev, toxic_ev, irrelevant_vis)
    findings = build_policy_findings(
        detected_categories=["threats", "toxic"],
        evidence_items=evidence,
    )

    mod_result = ModerationResult(
        decision=ModerationDecision.REJECTED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.85,
        overall_confidence=0.68,
        detected_categories=("threats", "toxic"),
        supporting_evidence=evidence,
        explanation="Testing evidence association.",
        findings=tuple(findings),
    )

    persistence.persist_moderation_run(video_id=video.id, result=mod_result)
    report = reporting.get_moderation_report(video.id)

    assert report is not None
    rep_threats = next(f for f in report.findings if f.category == "threats")
    rep_toxic = next(f for f in report.findings if f.category == "toxic")

    # Threats finding has ONLY threat evidence
    assert len(rep_threats.evidence_references) == 1
    assert "evidence_threat_01" in rep_threats.evidence_references
    assert "evidence_toxic_01" not in rep_threats.evidence_references
    assert "evidence_person_01" not in rep_threats.evidence_references

    # Toxic finding has ONLY toxic evidence
    assert len(rep_toxic.evidence_references) == 1
    assert "evidence_toxic_01" in rep_toxic.evidence_references
    assert "evidence_threat_01" not in rep_toxic.evidence_references
    assert "evidence_person_01" not in rep_toxic.evidence_references

    # Evidence counts differ (not both 886!)
    assert len(rep_threats.evidence_references) == 1
    assert len(rep_toxic.evidence_references) == 1
