"""Deterministic unit tests for the ModerationEngine service."""

import pytest

from app.db.enums import ModerationDecision, RiskLevel
from app.services.ai.contracts import (
    ContextualInterpretation,
    TextModerationSignal,
    TranscriptSegment,
    VisualDetection,
)
from app.services.moderation.config import ModerationConfig
from app.services.moderation.contracts import EvidenceItem, ModerationResult
from app.services.moderation.engine import ModerationEngine


@pytest.fixture
def default_engine() -> ModerationEngine:
    return ModerationEngine()


def test_benign_cooking_context(default_engine: ModerationEngine) -> None:
    """1. Benign cooking context: knife + cooking context + no threat -> LOW / APPROVED (risk=0.0)."""
    detections = [
        VisualDetection(category="knife", confidence=0.92, timestamp=2.5, evidence_reference="frame_0005"),
        VisualDetection(category="person", confidence=0.88, timestamp=2.5, evidence_reference="frame_0005"),
        VisualDetection(category="broccoli", confidence=0.75, timestamp=2.5, evidence_reference="frame_0005"),
    ]
    transcripts = [
        TranscriptSegment(start=1.0, end=4.0, text="Chop the onions finely for the recipe."),
    ]
    signals: list[TextModerationSignal] = []
    context = ContextualInterpretation(
        category="cooking",
        confidence=0.95,
        reasoning="Person preparing culinary ingredients with a kitchen knife.",
        evidence_references=("frame_0005",),
    )

    result = default_engine.evaluate(
        detections=detections,
        transcripts=transcripts,
        text_signals=signals,
        context=context,
    )

    assert result.decision == ModerationDecision.APPROVED
    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 0.0
    assert len(result.detected_categories) == 0  # No policy violations flagged
    assert len(result.supporting_evidence) == 4  # All raw evidence preserved
    assert "mitigating" in result.explanation.lower() or "benign" in result.explanation.lower()


def test_harmless_objects_do_not_become_moderation_categories(default_engine: ModerationEngine) -> None:
    """Harmless everyday objects (bowl, broccoli, fork, person, spoon) produce 0 risk and no policy categories."""
    detections = [
        VisualDetection(category="person", confidence=0.90, timestamp=1.0, evidence_reference="frame_0001"),
        VisualDetection(category="bowl", confidence=0.85, timestamp=1.0, evidence_reference="frame_0001"),
        VisualDetection(category="broccoli", confidence=0.70, timestamp=1.0, evidence_reference="frame_0001"),
        VisualDetection(category="spoon", confidence=0.60, timestamp=1.0, evidence_reference="frame_0001"),
    ]

    result = default_engine.evaluate(detections=detections)

    assert result.decision == ModerationDecision.APPROVED
    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 0.0
    assert len(result.detected_categories) == 0


def test_threatening_knife_scenario(default_engine: ModerationEngine) -> None:
    """2. Threatening knife scenario: knife + threat text + threatening context -> CRITICAL / REJECTED."""
    detections = [
        VisualDetection(category="knife", confidence=0.95, timestamp=10.0, evidence_reference="frame_0020"),
    ]
    transcripts = [
        TranscriptSegment(start=9.5, end=11.0, text="I will hurt you with this."),
    ]
    signals = [
        TextModerationSignal(
            category="threats",
            confidence=0.92,
            start_timestamp=9.5,
            end_timestamp=11.0,
            source_text="I will hurt you with this.",
        ),
    ]
    context = ContextualInterpretation(
        category="threatening",
        confidence=0.90,
        reasoning="Individual aggressively brandishing a knife during an altercation.",
        evidence_references=("frame_0020",),
    )

    result = default_engine.evaluate(
        detections=detections,
        transcripts=transcripts,
        text_signals=signals,
        context=context,
    )

    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
    assert result.risk_score >= 0.85
    assert result.decision == ModerationDecision.REJECTED
    assert "weapons" in result.detected_categories
    assert "threats" in result.detected_categories


def test_toxic_language_without_physical_violence(default_engine: ModerationEngine) -> None:
    """3. Toxic language without physical violence -> appropriate medium risk."""
    detections: list[VisualDetection] = []
    transcripts = [
        TranscriptSegment(start=0.0, end=3.0, text="You are totally stupid and awful."),
    ]
    signals = [
        TextModerationSignal(
            category="toxic_language",
            confidence=0.80,
            start_timestamp=0.0,
            end_timestamp=3.0,
            source_text="You are totally stupid and awful.",
        ),
    ]
    context = ContextualInterpretation(
        category="harassment",
        confidence=0.65,
        reasoning="Verbal insult during a conversation.",
        evidence_references=(),
    )

    result = default_engine.evaluate(
        detections=detections,
        transcripts=transcripts,
        text_signals=signals,
        context=context,
    )

    assert result.risk_level == RiskLevel.MEDIUM
    assert result.decision == ModerationDecision.REVIEW_REQUIRED
    assert 0.30 <= result.risk_score < 0.60


def test_weapon_detection_without_harmful_context(default_engine: ModerationEngine) -> None:
    """4. Weapon detection without context resolution -> REVIEW_REQUIRED due to ambiguity."""
    detections = [
        VisualDetection(category="gun", confidence=0.85, timestamp=5.0, evidence_reference="frame_0010"),
    ]
    transcripts: list[TranscriptSegment] = []
    signals: list[TextModerationSignal] = []

    result = default_engine.evaluate(
        detections=detections,
        transcripts=transcripts,
        text_signals=signals,
        context=None,
    )

    assert result.decision == ModerationDecision.REVIEW_REQUIRED
    assert result.risk_score >= 0.40
    assert "weapons" in result.detected_categories


def test_knife_without_context_requires_review(default_engine: ModerationEngine) -> None:
    """Knife detection without context is treated as unverified blade requiring review."""
    detections = [
        VisualDetection(category="knife", confidence=0.80, timestamp=3.0, evidence_reference="frame_0006"),
    ]

    result = default_engine.evaluate(detections=detections, context=None)

    assert result.decision == ModerationDecision.REVIEW_REQUIRED
    assert "weapons" in result.detected_categories


def test_conflicting_evidence(default_engine: ModerationEngine) -> None:
    """5. Conflicting evidence: high toxic speech vs explicit benign context -> REVIEW_REQUIRED."""
    detections: list[VisualDetection] = []
    signals = [
        TextModerationSignal(
            category="threats",
            confidence=0.85,
            start_timestamp=1.0,
            end_timestamp=3.0,
            source_text="Threatening words detected",
        ),
    ]
    context = ContextualInterpretation(
        category="cooking",
        confidence=0.85,
        reasoning="Peaceful cooking tutorial in progress.",
        evidence_references=(),
    )

    result = default_engine.evaluate(
        detections=detections,
        text_signals=signals,
        context=context,
    )

    assert result.decision == ModerationDecision.REVIEW_REQUIRED


def test_insufficient_evidence_safe_fallback(default_engine: ModerationEngine) -> None:
    """6. Empty/insufficient inputs -> safe default (APPROVED / LOW)."""
    result = default_engine.evaluate(
        detections=(),
        transcripts=(),
        text_signals=(),
        context=None,
    )

    assert result.decision == ModerationDecision.APPROVED
    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 0.0
    assert result.overall_confidence == 1.0
    assert len(result.supporting_evidence) == 0
    assert "0 visual detection(s)" in result.explanation


def test_multiple_supporting_signals_corroboration(default_engine: ModerationEngine) -> None:
    """7. Multiple supporting signals (visual + text) amplify risk via cross-modal corroboration."""
    detections = [
        VisualDetection(category="violence", confidence=0.80, timestamp=4.0, evidence_reference="frame_0008"),
    ]
    signals = [
        TextModerationSignal(
            category="threats",
            confidence=0.80,
            start_timestamp=3.8,
            end_timestamp=5.2,
            source_text="Attack now!",
        ),
    ]
    context = ContextualInterpretation(
        category="violence",
        confidence=0.85,
        reasoning="Physical fight depicted.",
        evidence_references=("frame_0008",),
    )

    result = default_engine.evaluate(
        detections=detections,
        text_signals=signals,
        context=context,
    )

    assert result.risk_score >= 0.85
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.decision == ModerationDecision.REJECTED


def test_high_severity_category_child_safety(default_engine: ModerationEngine) -> None:
    """8. Critical safety category (child_safety) with high confidence triggers immediate critical score."""
    signals = [
        TextModerationSignal(
            category="child_safety",
            confidence=0.85,
            start_timestamp=2.0,
            end_timestamp=4.0,
            source_text="child safety concern phrase",
        ),
    ]

    result = default_engine.evaluate(text_signals=signals)

    assert result.risk_level == RiskLevel.CRITICAL
    assert result.decision == ModerationDecision.REJECTED
    assert result.risk_score >= 0.95


def test_low_confidence_detections_filtered(default_engine: ModerationEngine) -> None:
    """9. Low-confidence detections below min threshold (0.30) are ignored."""
    detections = [
        VisualDetection(category="knife", confidence=0.20, timestamp=1.0, evidence_reference="frame_0001"),
    ]
    signals = [
        TextModerationSignal(
            category="threats",
            confidence=0.15,
            start_timestamp=1.0,
            end_timestamp=2.0,
            source_text="maybe unclear noise",
        ),
    ]

    result = default_engine.evaluate(detections=detections, text_signals=signals)

    assert result.risk_score == 0.0
    assert result.risk_level == RiskLevel.LOW
    assert result.decision == ModerationDecision.APPROVED
    assert len(result.supporting_evidence) == 0


def test_threshold_boundary_values() -> None:
    """10. Test configurable threshold boundary edges precisely."""
    custom_config = ModerationConfig(
        low_risk_threshold=0.25,
        medium_risk_threshold=0.50,
        high_risk_threshold=0.80,
        auto_reject_threshold=0.80,
        review_threshold=0.35,
    )
    engine = ModerationEngine(config=custom_config)

    # Test risk level helpers directly
    assert engine._determine_risk_level(0.24) == RiskLevel.LOW
    assert engine._determine_risk_level(0.25) == RiskLevel.MEDIUM
    assert engine._determine_risk_level(0.49) == RiskLevel.MEDIUM
    assert engine._determine_risk_level(0.50) == RiskLevel.HIGH
    assert engine._determine_risk_level(0.79) == RiskLevel.HIGH
    assert engine._determine_risk_level(0.80) == RiskLevel.CRITICAL

    # Test decision helpers directly
    assert engine._determine_decision(0.34, has_conflicting_signals=False) == ModerationDecision.APPROVED
    assert engine._determine_decision(0.35, has_conflicting_signals=False) == ModerationDecision.REVIEW_REQUIRED
    assert engine._determine_decision(0.79, has_conflicting_signals=False) == ModerationDecision.REVIEW_REQUIRED
    assert engine._determine_decision(0.80, has_conflicting_signals=False) == ModerationDecision.REJECTED


def test_evidence_references_remain_intact(default_engine: ModerationEngine) -> None:
    """11. Evidence references and timestamps are preserved in supporting_evidence items."""
    detections = [
        VisualDetection(category="knife", confidence=0.85, timestamp=7.25, evidence_reference="frame_0029"),
    ]
    signals = [
        TextModerationSignal(
            category="insult",
            confidence=0.75,
            start_timestamp=7.0,
            end_timestamp=8.5,
            source_text="You fool!",
        ),
    ]
    context = ContextualInterpretation(
        category="cooking",
        confidence=0.90,
        reasoning="Kitchen cooking show with playful banter.",
        evidence_references=("frame_0029", "seg_0003"),
    )

    result = default_engine.evaluate(
        detections=detections,
        text_signals=signals,
        context=context,
    )

    ev_modalities = {e.modality: e for e in result.supporting_evidence}
    assert "visual" in ev_modalities
    assert ev_modalities["visual"].reference == "frame_0029"
    assert ev_modalities["visual"].timestamp == 7.25

    assert "text_signal" in ev_modalities
    assert ev_modalities["text_signal"].timestamp == 7.0

    assert "context" in ev_modalities
    assert "frame_0029" in ev_modalities["context"].reference


def test_explanation_grounded_in_supplied_evidence(default_engine: ModerationEngine) -> None:
    """12. Explanation contains actual detected categories, reasoning, and policy metrics."""
    detections = [
        VisualDetection(category="knife", confidence=0.90, timestamp=3.0, evidence_reference="frame_0006"),
    ]
    context = ContextualInterpretation(
        category="cooking",
        confidence=0.92,
        reasoning="Culinary demonstration slicing bread.",
        evidence_references=("frame_0006",),
    )

    result = default_engine.evaluate(detections=detections, context=context)

    assert "knife" in result.explanation
    assert "cooking" in result.explanation
    assert "Culinary demonstration slicing bread" in result.explanation
    assert "APPROVED" in result.explanation
    assert "Risk score calculated" in result.explanation


def test_invalid_contract_values_raise_validation_errors() -> None:
    """13. Contracts enforce boundaries on initialization."""
    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        EvidenceItem(modality="visual", category="test", confidence=1.5, reference="ref")

    with pytest.raises(ValueError, match="timestamp must be non-negative"):
        EvidenceItem(modality="visual", category="test", confidence=0.5, reference="ref", timestamp=-1.0)

    with pytest.raises(ValueError, match="risk_score must be between 0.0 and 1.0"):
        ModerationResult(
            decision=ModerationDecision.APPROVED,
            risk_level=RiskLevel.LOW,
            risk_score=1.5,
            overall_confidence=0.8,
            detected_categories=(),
            supporting_evidence=(),
            explanation="test",
        )


def test_context_mapping_threatening_interaction_slap_scenario(default_engine: ModerationEngine) -> None:
    """14. Contextual interpretation 'threatening interaction' (e.g. slap test) flags 'threats' and produces HIGH/REVIEW_REQUIRED."""
    detections = [
        VisualDetection(category="person", confidence=0.90, timestamp=1.0, evidence_reference="frame_0001"),
        VisualDetection(category="person", confidence=0.88, timestamp=2.0, evidence_reference="frame_0002"),
    ]
    context = ContextualInterpretation(
        category="threatening interaction",
        confidence=0.90,
        reasoning="A person being slapped during an aggressive altercation.",
        evidence_references=("frame_0001", "frame_0002"),
    )

    result = default_engine.evaluate(
        detections=detections,
        transcripts=(),
        text_signals=(),
        context=context,
    )

    assert "threats" in result.detected_categories
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
    assert result.risk_score >= 0.60
    assert result.overall_confidence > 0.80
    assert "threatening interaction" in result.explanation


def test_context_mapping_physical_assault(default_engine: ModerationEngine) -> None:
    """15. Contextual interpretation 'physical assault' maps to 'violence' category and produces elevated risk."""
    detections = [
        VisualDetection(category="person", confidence=0.85, timestamp=1.5, evidence_reference="frame_0003"),
    ]
    context = ContextualInterpretation(
        category="physical assault",
        confidence=0.90,
        reasoning="Physical striking observed between two subjects.",
        evidence_references=("frame_0003",),
    )

    result = default_engine.evaluate(
        detections=detections,
        context=context,
    )

    assert "violence" in result.detected_categories
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
    assert result.risk_score >= 0.60


def test_context_mapping_violent_confrontation(default_engine: ModerationEngine) -> None:
    """16. Contextual interpretation 'violent confrontation' maps to 'violence' category."""
    context = ContextualInterpretation(
        category="violent confrontation",
        confidence=0.90,
        reasoning="Physical combat between subjects.",
        evidence_references=(),
    )

    result = default_engine.evaluate(context=context)

    assert "violence" in result.detected_categories
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
    assert result.risk_score >= 0.60


def test_context_mapping_assault(default_engine: ModerationEngine) -> None:
    """17. Contextual interpretation 'assault' maps to 'violence' category."""
    context = ContextualInterpretation(
        category="assault",
        confidence=0.88,
        reasoning="Assaultive behavior observed.",
        evidence_references=(),
    )

    result = default_engine.evaluate(context=context)

    assert "violence" in result.detected_categories
    assert result.risk_score >= 0.60


def test_context_mapping_self_harm_critical(default_engine: ModerationEngine) -> None:
    """18. Contextual interpretation 'self-harm situation' triggers critical safety override."""
    context = ContextualInterpretation(
        category="self-harm situation",
        confidence=0.85,
        reasoning="Subject exhibiting self-injurious behavior.",
        evidence_references=(),
    )

    result = default_engine.evaluate(context=context)

    assert "self_harm" in result.detected_categories
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.decision == ModerationDecision.REJECTED
    assert result.risk_score >= 0.95


def test_context_mapping_child_endangerment_critical(default_engine: ModerationEngine) -> None:
    """19. Contextual interpretation 'child endangerment' triggers critical safety override."""
    context = ContextualInterpretation(
        category="child endangerment",
        confidence=0.85,
        reasoning="Minor placed in hazardous situation.",
        evidence_references=(),
    )

    result = default_engine.evaluate(context=context)

    assert "child_safety" in result.detected_categories
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.decision == ModerationDecision.REJECTED
    assert result.risk_score >= 0.95


def test_configurable_custom_context_policy_mapping() -> None:
    """20. ModerationConfig allows configurable custom context-to-policy category mappings."""
    custom_config = ModerationConfig(
        context_policy_mapping={
            "custom dangerous scenario": ("dangerous_behavior", "threats"),
        }
    )
    engine = ModerationEngine(config=custom_config)

    context = ContextualInterpretation(
        category="custom dangerous scenario",
        confidence=0.80,
        reasoning="Custom mapped incident description.",
        evidence_references=(),
    )

    result = engine.evaluate(context=context)

    assert "dangerous_behavior" in result.detected_categories
    assert "threats" in result.detected_categories
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.decision in (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REJECTED)
