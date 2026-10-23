"""Regression test suite for the cooking video false-positive fix.

Validates that:
1. A benign cooking video containing knives, flames, chopping, and ordinary narration is APPROVED (risk=0.0).
2. Benign narration receiving a high ToxicBERT score does NOT cause critical physical danger or weapon flags.
3. Genuinely threatening text remains detectable and escalates weapons.
4. Genuine dangerous visual content (e.g. firearms) remains detectable even in cooking context.
5. Repeated frame detections across time do not artificially inflate risk to CRITICAL.
6. A brief genuine dangerous event in a long video remains detectable without dilution.
7. Qwen contextual findings propagate correctly (benign mitigates, hostile aggravates, failed requires review).
8. Gemini formatting preserves authoritative moderation results without altering scores or decisions.
"""

import pytest
from unittest.mock import MagicMock

from app.db.enums import ModerationDecision, RiskLevel
from app.services.ai.contracts import (
    ContextualInterpretation,
    ContextWindowInterpretation,
    TextModerationSignal,
    TranscriptSegment,
    VisualDetection,
)
from app.services.moderation.config import ModerationConfig
from app.services.moderation.contracts import ModerationResult, PolicyFinding, PolicyEvent
from app.services.moderation.engine import ModerationEngine
from app.services.moderation.formatting import GeminiReportFormatter


@pytest.fixture
def engine() -> ModerationEngine:
    return ModerationEngine()


def test_1_benign_cooking_video_with_knives_and_chopping(engine: ModerationEngine) -> None:
    """1. Benign cooking video containing knives, flames, chopping, and ordinary narration -> APPROVED / LOW (risk=0.0)."""
    detections = [
        VisualDetection(category="knife", confidence=0.88, timestamp=12.0, evidence_reference="frame_0012"),
        VisualDetection(category="knife", confidence=0.92, timestamp=13.0, evidence_reference="frame_0013"),
        VisualDetection(category="scissors", confidence=0.75, timestamp=55.0, evidence_reference="frame_0055"),
        VisualDetection(category="bowl", confidence=0.80, timestamp=60.0, evidence_reference="frame_0060"),
        VisualDetection(category="broccoli", confidence=0.70, timestamp=65.0, evidence_reference="frame_0065"),
    ]
    transcripts = [
        TranscriptSegment(start=10.0, end=15.0, text="Use a sharp chef's knife to chop the vegetables."),
        TranscriptSegment(start=50.0, end=55.0, text="Simmer the sauce over medium heat until thickened."),
    ]
    context = ContextualInterpretation(
        category="Cooking Tutorial",
        confidence=0.95,
        reasoning="Chef preparing a recipe in a home kitchen demonstration.",
        evidence_references=("frame_0012", "frame_0055"),
    )

    result = engine.evaluate(
        detections=detections,
        transcripts=transcripts,
        text_signals=(),
        context=context,
    )

    assert result.decision == ModerationDecision.APPROVED
    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 0.0
    assert len(result.detected_categories) == 0
    assert "weapons" not in result.detected_categories
    assert "mitigating" in result.explanation.lower()


def test_2_benign_narration_with_high_toxicbert_score_not_critical_danger(engine: ModerationEngine) -> None:
    """2. Benign narration receiving a high ToxicBERT score is not treated as proof of critical physical danger."""
    # 25 knife and scissors detections across a cooking video (mirroring Shepherd's Pie)
    detections = [
        VisualDetection(category="knife", confidence=0.67, timestamp=float(t), evidence_reference=f"frame_{t:04d}")
        for t in (12, 13, 53, 68, 69, 71, 72, 73, 105, 106, 142, 165, 192, 226, 227, 228, 276, 281, 286, 295, 307)
    ]
    # ToxicBERT false positive on culinary text ("chop your veggies" = 0.84)
    signals = [
        TextModerationSignal(
            category="toxic",
            confidence=0.8387,
            start_timestamp=65.0,
            end_timestamp=68.0,
            source_text="Instead, save yourself the time and chop your veggies up nice and small.",
        ),
    ]
    context = ContextualInterpretation(
        category="Cooking Tutorial",
        confidence=0.95,
        reasoning="Demonstration of traditional shepherd's pie recipe preparation.",
        evidence_references=("frame_0012",),
    )

    result = engine.evaluate(
        detections=detections,
        text_signals=signals,
        context=context,
    )

    # Must NOT be classified as CRITICAL danger
    assert result.risk_level != RiskLevel.CRITICAL
    assert result.risk_score < 0.60
    assert result.decision != ModerationDecision.REJECTED

    # Knives must remain mitigated as cooking tools — NO WEAPONS POLICY VIOLATION
    assert "weapons" not in result.detected_categories
    # Only the text moderation flag should be present
    assert "toxic" in result.detected_categories


def test_3_genuinely_threatening_text_remains_detectable(engine: ModerationEngine) -> None:
    """3. Genuinely threatening text ('I will hurt you') escalates dual-use knives to weapons."""
    detections = [
        VisualDetection(category="knife", confidence=0.85, timestamp=15.0, evidence_reference="frame_0015"),
    ]
    signals = [
        TextModerationSignal(
            category="threats",
            confidence=0.92,
            start_timestamp=14.0,
            end_timestamp=16.0,
            source_text="I will hurt you with this knife.",
        ),
    ]
    context = ContextualInterpretation(
        category="Cooking Tutorial",
        confidence=0.85,
        reasoning="Kitchen setting but dialogue contains an overt threat.",
        evidence_references=("frame_0015",),
    )

    result = engine.evaluate(
        detections=detections,
        text_signals=signals,
        context=context,
    )

    # Credible threat text overrides benign setting: knife treated as weapon
    assert "weapons" in result.detected_categories
    assert "threats" in result.detected_categories
    assert result.risk_score >= 0.70
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)


def test_4_genuine_dangerous_visual_content_remains_detectable(engine: ModerationEngine) -> None:
    """4. Genuine dangerous visual content (explicit weapon) remains detectable even in cooking context."""
    detections = [
        VisualDetection(category="gun", confidence=0.88, timestamp=45.0, evidence_reference="frame_0045"),
        VisualDetection(category="knife", confidence=0.75, timestamp=46.0, evidence_reference="frame_0046"),
    ]
    context = ContextualInterpretation(
        category="Cooking Tutorial",
        confidence=0.90,
        reasoning="Kitchen video but firearm is visible on the counter.",
        evidence_references=("frame_0045",),
    )

    result = engine.evaluate(
        detections=detections,
        context=context,
    )

    # Explicit firearm is NOT dual-use and cannot be mitigated by culinary context
    assert "weapons" in result.detected_categories
    assert result.risk_score >= 0.60
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_5_repeated_detections_across_frames_do_not_inflate_risk(engine: ModerationEngine) -> None:
    """5. 50 repeated detections of an object across consecutive frames do not artificially inflate risk to CRITICAL."""
    # 50 consecutive frames of a knife in an unverified/unknown context
    detections = [
        VisualDetection(category="knife", confidence=0.75, timestamp=float(i), evidence_reference=f"frame_{i:04d}")
        for i in range(50)
    ]

    result = engine.evaluate(detections=detections, context=None)

    # The 50 continuous frames should coalesce into one temporal event, NOT accumulate 50 separate penalties
    assert result.risk_level != RiskLevel.CRITICAL
    # Single unverified knife event at severity 0.70 * 0.75 conf = 0.525 risk
    assert result.risk_score < 0.65
    assert result.decision == ModerationDecision.REVIEW_REQUIRED


def test_6_brief_dangerous_event_in_long_video_remains_detectable(engine: ModerationEngine) -> None:
    """6. A brief genuine dangerous event in a long video remains detectable at peak severity."""
    # Long video (600 seconds) with lots of harmless detections and one brief 1.0s firearm appearance
    detections = [
        VisualDetection(category="person", confidence=0.90, timestamp=float(t), evidence_reference=f"frame_{t:04d}")
        for t in range(0, 600, 30)
    ]
    detections.append(
        VisualDetection(category="gun", confidence=0.92, timestamp=300.0, evidence_reference="frame_0300")
    )

    result = engine.evaluate(detections=detections, context=None)

    # Peak severity must NOT be diluted by the surrounding clean frames
    assert "weapons" in result.detected_categories
    # Weapon severity 0.70 * 0.92 = 0.644
    assert result.risk_score >= 0.60
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_7_qwen_contextual_findings_propagation(engine: ModerationEngine) -> None:
    """7. Correct propagation of Qwen contextual findings into final risk aggregation."""
    # 7a. Benign context mitigates dual-use
    res_benign = engine.evaluate(
        detections=[VisualDetection(category="knife", confidence=0.85, timestamp=1.0, evidence_reference="ref_001")],
        context=ContextualInterpretation(category="culinary", confidence=0.90, reasoning="Cooking show.", evidence_references=("ref_001",)),
    )
    assert res_benign.risk_score == 0.0
    assert len(res_benign.detected_categories) == 0

    # 7b. Hostile context aggravates dual-use and maps to policy categories
    res_hostile = engine.evaluate(
        detections=[VisualDetection(category="knife", confidence=0.85, timestamp=1.0, evidence_reference="ref_002")],
        context=ContextualInterpretation(category="violent altercation", confidence=0.90, reasoning="Knife fight.", evidence_references=("ref_002",)),
    )
    assert "weapons" in res_hostile.detected_categories
    assert "violence" in res_hostile.detected_categories
    assert res_hostile.risk_score >= 0.85

    # 7c. Failed window context prevents mitigation and flags conflicting signals
    failed_win = ContextWindowInterpretation(start_timestamp=0.0, end_timestamp=30.0, category="unknown", confidence=0.0, reasoning="Error", status="failed")
    res_failed = engine.evaluate(
        detections=[VisualDetection(category="knife", confidence=0.85, timestamp=1.0, evidence_reference="ref1")],
        context=ContextualInterpretation(category="cooking", confidence=0.90, reasoning="Cooking", evidence_references=("ref1",), window_interpretations=(failed_win,)),
    )
    assert res_failed.decision == ModerationDecision.REVIEW_REQUIRED


def test_8_gemini_formatting_preserves_authoritative_results() -> None:
    """8. Gemini formatting preserves authoritative moderation results (decision, score, categories)."""
    from datetime import datetime, timezone
    from app.core.config import Settings
    from app.schemas.moderation import ModerationReportResponse

    report = ModerationReportResponse(
        video_id="vid_test_123",
        filename="cooking_video.mp4",
        created_at=datetime.now(timezone.utc),
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        risk_score=0.42,
        overall_confidence=0.51,
        detected_categories=["toxic"],
        explanation="Authoritative explanation.",
        findings=[],
        evidence=[],
        transcripts=[],
    )

    formatter = GeminiReportFormatter(settings=Settings(gemini_api_key=""))
    summary, justification = formatter.format_report(report)

    # Formatter must provide summary/justification while report authoritative metrics remain untouched
    assert summary
    assert isinstance(justification.visual_evidence, list)
    assert report.decision == ModerationDecision.REVIEW_REQUIRED
    assert report.risk_score == 0.42
    assert report.risk_level == RiskLevel.MEDIUM
    assert report.detected_categories == ["toxic"]
    assert report.overall_confidence == 0.51
