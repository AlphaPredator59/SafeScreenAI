"""Domain contracts and result objects for the moderation engine."""

from dataclasses import dataclass, field
from typing import Sequence

from app.db.enums import ModerationDecision, RiskLevel


def _validate_score(value: float, name: str = "score") -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")
    return value


@dataclass(frozen=True)
class EvidenceItem:
    """Traceable, immutable evidence unit supporting a moderation finding."""

    modality: str  # "visual", "transcript", "text_signal", "context"
    category: str
    confidence: float
    reference: str
    timestamp: float | None = None
    end_timestamp: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        _validate_score(self.confidence, "confidence")
        if self.timestamp is not None and self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")
        if self.end_timestamp is not None and self.end_timestamp < 0:
            raise ValueError("end_timestamp must be non-negative")
        if self.timestamp is not None and self.end_timestamp is not None and self.end_timestamp < self.timestamp:
            raise ValueError("end_timestamp must be greater than or equal to timestamp")


@dataclass(frozen=True)
class PolicyEvent:
    """A discrete temporal interval representing an occurrence of a policy violation."""

    start_time: float
    end_time: float
    confidence: float
    evidence_ids: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _validate_score(self.confidence, "confidence")
        if self.start_time < 0:
            raise ValueError("start_time must be non-negative")
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")


@dataclass(frozen=True)
class PolicyFinding:
    """A policy-relevant finding containing one or more discrete policy events."""

    category: str
    severity: float
    confidence: float
    summary: str
    events: tuple[PolicyEvent, ...] = ()

    def __post_init__(self) -> None:
        _validate_score(self.severity, "severity")
        _validate_score(self.confidence, "confidence")


@dataclass(frozen=True)
class ModerationResult:
    """Final, explainable moderation assessment produced by the ModerationEngine."""

    decision: ModerationDecision
    risk_level: RiskLevel
    risk_score: float
    overall_confidence: float
    detected_categories: tuple[str, ...]
    supporting_evidence: tuple[EvidenceItem, ...]
    explanation: str
    findings: tuple[PolicyFinding, ...] = ()

    def __post_init__(self) -> None:
        _validate_score(self.risk_score, "risk_score")
        _validate_score(self.overall_confidence, "overall_confidence")
        if not isinstance(self.decision, ModerationDecision):
            raise TypeError(f"decision must be ModerationDecision enum, got {type(self.decision)}")
        if not isinstance(self.risk_level, RiskLevel):
            raise TypeError(f"risk_level must be RiskLevel enum, got {type(self.risk_level)}")
