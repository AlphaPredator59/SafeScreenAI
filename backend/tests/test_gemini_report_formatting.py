"""Comprehensive tests for Gemini-powered executive summary and AI justification formatting."""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.database import get_db_session
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Video
from app.main import app
from app.schemas.moderation import (
    AIJustificationResponse,
    EvidenceItemResponse,
    FindingResponse,
    ModerationReportResponse,
    PolicyEventResponse,
    TranscriptSegmentResponse,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult
from app.services.moderation.formatting import GeminiReportFormatter, get_report_formatter
from app.services.moderation.persistence import ModerationPersistenceService
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository


@pytest.fixture
def sample_report() -> ModerationReportResponse:
    """Fixture producing a standard multi-modal moderation report."""
    return ModerationReportResponse(
        video_id="vid_test_gemini_001",
        filename="threat_sample.mp4",
        created_at=datetime.now(timezone.utc),
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.77,
        overall_confidence=0.88,
        detected_categories=["threats"],
        explanation="Evidence Analyzed: 1 visual detection(s); 1 text signal(s); context inferred as 'altercation'. Assessment: Flagged policy categories: ['threats']. Risk score calculated at 0.77 (HIGH). Final moderation outcome is REVIEW_REQUIRED.",
        findings=[
            FindingResponse(
                id="f_001",
                category="threats",
                severity=0.77,
                confidence=0.88,
                summary="Flagged 1 event(s) for 'threats' policy with peak confidence 0.88.",
                start_timestamp=1.5,
                end_timestamp=3.0,
                explanation="Threatening gesture with object",
                evidence_references=["frame_001.jpg"],
                events=[
                    PolicyEventResponse(
                        id="ev_001",
                        start_time=1.5,
                        end_time=3.0,
                        confidence=0.88,
                        evidence_ids=["frame_001.jpg"],
                        evidence_types=["visual"],
                        description="Threatening physical stance",
                    )
                ],
            )
        ],
        evidence=[
            EvidenceItemResponse(
                id="ev_item_1",
                type="visual",
                timestamp=1.5,
                content="Visual detection of knife",
                reference="frame_001.jpg",
            ),
            EvidenceItemResponse(
                id="ev_item_2",
                type="context",
                timestamp=1.5,
                content="Hostile confrontation between two individuals",
                reference="context_window_1",
            ),
        ],
        transcripts=[
            TranscriptSegmentResponse(
                start_timestamp=1.0,
                end_timestamp=2.8,
                text="Put that down right now",
            )
        ],
    )


# -----------------------------------------------------------------------------
# Test 1 & 2 & 3: Successful Gemini Response Formatting
# -----------------------------------------------------------------------------
def test_successful_gemini_response_formatting(sample_report: ModerationReportResponse):
    """Test 1-3: Successful Gemini API formatting produces valid Executive Summary and all AI Justification sections."""
    gemini_payload = {
        "executive_summary": (
            "The moderation pipeline identified a potentially hostile altercation involving a knife and verbal confrontation. "
            "Visual evidence indicates a threatening interaction between 1.5s and 3.0s, accompanied by urgent dialogue. "
            "Because intent and risk depend heavily on the surrounding scene, the content has been assigned high risk and flagged for human review."
        ),
        "ai_justification": {
            "visual_evidence": [
                "Visual detection of knife prop at 1.50s in frame_001.jpg",
                "Threatening physical stance identified between 1.5s and 3.0s",
            ],
            "audio_text_evidence": [
                "Spoken dialogue transcribed: \"Put that down right now\" (1.0s - 2.8s)"
            ],
            "contextual_analysis": "The context analyzer interpreted the scene as a hostile confrontation rather than a culinary or benign environment.",
            "policy_rationale": [
                "Category 'threats' was flagged due to concurrent weapon display and confrontational verbal cues (peak confidence: 0.88)."
            ],
            "uncertainty": [
                "Available video footage is brief and does not fully establish real-world intent versus theatrical reenactment."
            ],
        },
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(gemini_payload)}]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    settings = Settings(gemini_api_key="test_api_key_valid")
    formatter = GeminiReportFormatter(settings=settings, http_client=mock_client)

    summary, justification = formatter.format_report(sample_report)

    # 1. Executive Summary checks
    assert len(summary) > 20
    assert "altercation" in summary or "knife" in summary
    assert "human review" in summary

    # 2. All 5 AI Justification sections populated
    assert len(justification.visual_evidence) == 2
    assert "knife" in justification.visual_evidence[0]
    assert len(justification.audio_text_evidence) == 1
    assert "Put that down" in justification.audio_text_evidence[0]
    assert "hostile confrontation" in justification.contextual_analysis
    assert len(justification.policy_rationale) == 1
    assert "threats" in justification.policy_rationale[0]
    assert len(justification.uncertainty) == 1
    assert justification.is_fallback is False


# -----------------------------------------------------------------------------
# Test 4: Strict Preservation of Authoritative Pipeline Metrics
# -----------------------------------------------------------------------------
def test_strict_preservation_of_authoritative_pipeline_metrics(sample_report: ModerationReportResponse):
    """Test 4: Original decision, risk_score, risk_level, confidence, and categories remain strictly unchanged."""
    orig_decision = sample_report.decision
    orig_risk_score = sample_report.risk_score
    orig_risk_level = sample_report.risk_level
    orig_confidence = sample_report.overall_confidence
    orig_categories = list(sample_report.detected_categories)

    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=None))
    summary, justification = formatter.format_report(sample_report)

    # Attach to report
    sample_report.executive_summary = summary
    sample_report.ai_justification = justification

    assert sample_report.decision == orig_decision
    assert sample_report.risk_score == orig_risk_score
    assert sample_report.risk_level == orig_risk_level
    assert sample_report.overall_confidence == orig_confidence
    assert sample_report.detected_categories == orig_categories


# -----------------------------------------------------------------------------
# Test 5: Missing Transcript Data
# -----------------------------------------------------------------------------
def test_missing_transcript_data_handled_gracefully(sample_report: ModerationReportResponse):
    """Test 5: Content with missing audio transcripts is gracefully formatted without hallucinating dialogue."""
    silent_report = sample_report.model_copy(update={"transcripts": []})

    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=None))
    summary, justification = formatter.format_report(silent_report)

    assert justification.is_fallback is True
    assert any("silent" in u.lower() or "unavailable" in u.lower() for u in justification.uncertainty)
    assert any("No spoken audio dialogue" in a for a in justification.audio_text_evidence)


# -----------------------------------------------------------------------------
# Test 6: Empty Visual Detections
# -----------------------------------------------------------------------------
def test_empty_visual_detections_handled_gracefully():
    """Test 6: Content with no visual violations or detections formats gracefully."""
    audio_only_report = ModerationReportResponse(
        video_id="vid_audio_only",
        filename="audio_only.mp4",
        created_at=datetime.now(timezone.utc),
        decision=ModerationDecision.APPROVED,
        risk_level=RiskLevel.LOW,
        risk_score=0.10,
        overall_confidence=0.95,
        detected_categories=[],
        explanation="No visual or textual flags.",
        findings=[],
        evidence=[],
        transcripts=[
            TranscriptSegmentResponse(start_timestamp=0.0, end_timestamp=2.0, text="Good morning everyone.")
        ],
    )

    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=None))
    summary, justification = formatter.format_report(audio_only_report)

    assert "approved" in summary.lower()
    assert any("No hazardous or policy-violating visual objects" in v for v in justification.visual_evidence)
    assert any("Good morning" in a for a in justification.audio_text_evidence)
    assert justification.is_fallback is True


# -----------------------------------------------------------------------------
# Test 7: Missing Contextual Analysis
# -----------------------------------------------------------------------------
def test_missing_contextual_analysis_handled_gracefully(sample_report: ModerationReportResponse):
    """Test 7: Reports without contextual evidence produce graceful explanation without crashing."""
    no_ctx_report = sample_report.model_copy(
        update={
            "evidence": [ev for ev in sample_report.evidence if ev.type != "context"],
            "explanation": "Visual detection only.",
        }
    )

    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=None))
    _, justification = formatter.format_report(no_ctx_report)

    assert len(justification.contextual_analysis) > 0
    assert "Scene context was evaluated" in justification.contextual_analysis


# -----------------------------------------------------------------------------
# Test 8: Malformed Gemini JSON Triggers Deterministic Fallback
# -----------------------------------------------------------------------------
def test_malformed_gemini_json_triggers_deterministic_fallback(sample_report: ModerationReportResponse):
    """Test 8: Malformed JSON from Gemini safely triggers fallback with diagnostic logging."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "THIS IS NOT JSON {{{ broken"}]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    formatter = GeminiReportFormatter(
        settings=Settings(gemini_api_key="mock_key"),
        http_client=mock_client,
    )

    summary, justification = formatter.format_report(sample_report)

    # Must cleanly fall back
    assert justification.is_fallback is True
    assert len(summary) > 20
    assert "threats" in summary.lower()


# -----------------------------------------------------------------------------
# Test 9: Gemini Timeout or Network Failure Triggers Deterministic Fallback
# -----------------------------------------------------------------------------
def test_gemini_timeout_or_network_failure_triggers_fallback(sample_report: ModerationReportResponse):
    """Test 9: Network timeout or connection errors smoothly fallback to deterministic summary."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out after 30s")

    formatter = GeminiReportFormatter(
        settings=Settings(gemini_api_key="mock_key"),
        http_client=mock_client,
    )

    summary, justification = formatter.format_report(sample_report)

    assert justification.is_fallback is True
    assert len(summary) > 20
    assert len(justification.visual_evidence) >= 1
    assert len(justification.policy_rationale) >= 1


# -----------------------------------------------------------------------------
# Test 10: Deterministic Fallback Generation Structure
# -----------------------------------------------------------------------------
def test_deterministic_fallback_generation_structure(sample_report: ModerationReportResponse):
    """Test 10: Deterministic fallback adheres strictly to required sections and style."""
    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=None))
    summary, justification = formatter.format_report(sample_report)

    # 2-4 sentences
    sentences = [s.strip() for s in summary.split(".") if s.strip()]
    assert 2 <= len(sentences) <= 4

    # Explains decision and risk
    assert "0.77" in summary or "HIGH" in summary
    assert "human review" in summary.lower()

    # All five subsections present
    assert isinstance(justification.visual_evidence, list) and len(justification.visual_evidence) > 0
    assert isinstance(justification.audio_text_evidence, list) and len(justification.audio_text_evidence) > 0
    assert isinstance(justification.contextual_analysis, str) and len(justification.contextual_analysis) > 0
    assert isinstance(justification.policy_rationale, list) and len(justification.policy_rationale) > 0
    assert isinstance(justification.uncertainty, list) and len(justification.uncertainty) > 0
    assert justification.is_fallback is True


# -----------------------------------------------------------------------------
# Test 11: Contradictory Decision or Hallucinated Categories in Gemini Output
# -----------------------------------------------------------------------------
def test_gemini_hallucinated_policy_or_contradiction_rejected(sample_report: ModerationReportResponse):
    """Test 11: If Gemini output contradicts the decision (e.g. claiming REJECTED when REVIEW_REQUIRED), it is rejected."""
    bad_payload = {
        "executive_summary": "The content has been rejected and definitively banned due to severe violations.",
        "ai_justification": {
            "visual_evidence": ["Knife detected"],
            "audio_text_evidence": ["Verbal threat"],
            "contextual_analysis": "Hostile",
            "policy_rationale": ["Banned"],
            "uncertainty": [],
        },
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(bad_payload)}]}}
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    formatter = GeminiReportFormatter(
        settings=Settings(gemini_api_key="mock_key"),
        http_client=mock_client,
    )

    # Sample report has decision = REVIEW_REQUIRED, but Gemini returned 'content has been rejected'
    # Validator must reject it and trigger fallback
    summary, justification = formatter.format_report(sample_report)

    assert justification.is_fallback is True
    assert "human review" in summary.lower()
    assert "definitively banned" not in summary


# -----------------------------------------------------------------------------
# Test 12: API Response Compatibility & Persistence Integration
# -----------------------------------------------------------------------------
def test_moderation_route_returns_executive_summary_and_justification(db_session: Session):
    """Test 12: GET /api/v1/videos/{video_id}/moderation returns executive_summary and ai_justification."""
    video = Video(
        id="vid_route_test_fmt",
        filename="test_video.mp4",
        storage_path="storage/videos/test_video.mp4",
        duration=10.0,
        file_size=1024 * 1024,
        width=1280,
        height=720,
        fps=30.0,
        status=VideoStatus.COMPLETED,
    )
    db_session.add(video)
    db_session.commit()

    repo = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repo)

    result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.765,
        overall_confidence=0.88,
        detected_categories=("threats",),
        supporting_evidence=(
            EvidenceItem(
                modality="visual",
                category="threats",
                confidence=0.88,
                reference="frame_0001.jpg",
                timestamp=2.0,
                description="Visual detection of knife",
            ),
        ),
        explanation="Flagged threats with high confidence.",
    )
    persistence.persist_moderation_run(video_id=video.id, result=result)

    app.dependency_overrides[get_db_session] = lambda: db_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/videos/{video.id}/moderation")
            assert response.status_code == 200
            data = response.json()

            # Existing fields preserved
            assert data["video_id"] == video.id
            assert data["decision"] == "REVIEW_REQUIRED"
            assert data["risk_score"] == 0.765
            assert data["risk_level"] == "HIGH"
            assert data["detected_categories"] == ["threats"]
            assert "explanation" in data

            # New fields present and properly structured
            assert "executive_summary" in data
            assert len(data["executive_summary"]) > 20
            assert "ai_justification" in data
            justification = data["ai_justification"]
            assert "visual_evidence" in justification
            assert "audio_text_evidence" in justification
            assert "contextual_analysis" in justification
            assert "policy_rationale" in justification
            assert "uncertainty" in justification
            assert isinstance(justification["is_fallback"], bool)
    finally:
        app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# Test 13: Caching Behavior
# -----------------------------------------------------------------------------
def test_formatter_cache_avoids_repeated_gemini_calls(sample_report: ModerationReportResponse):
    """Test 13: Repeat calls for the same report are returned from cache without repeated API requests."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "executive_summary": "Cached executive summary test.",
                                    "ai_justification": {
                                        "visual_evidence": ["Visual"],
                                        "audio_text_evidence": [],
                                        "contextual_analysis": "Context",
                                        "policy_rationale": ["threats policy"],
                                        "uncertainty": [],
                                    },
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_client.post.return_value = mock_response

    formatter = GeminiReportFormatter(
        settings=Settings(gemini_api_key="mock_key"),
        http_client=mock_client,
    )

    # First call
    s1, j1 = formatter.format_report(sample_report)
    assert s1 == "Cached executive summary test."
    assert mock_client.post.call_count == 1

    # Second call for same report
    s2, j2 = formatter.format_report(sample_report)
    assert s2 == s1
    assert mock_client.post.call_count == 1  # Not called again!
