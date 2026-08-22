"""Shared, vendor-neutral contracts exchanged by AI services."""

from dataclasses import dataclass, field
from typing import Mapping


class AIServiceError(RuntimeError):
    """Base error exposed by AI adapters without leaking vendor errors."""


def _confidence(value: float) -> float:
    if not 0 <= value <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return value


@dataclass(frozen=True)
class TimestampedFrame:
    frame_id: str
    timestamp: float
    storage_path: str

    def __post_init__(self) -> None:
        if self.timestamp < 0: raise ValueError("timestamp must be non-negative")


@dataclass(frozen=True)
class VisualDetection:
    category: str
    confidence: float
    timestamp: float
    evidence_reference: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _confidence(self.confidence)
        if self.timestamp < 0: raise ValueError("timestamp must be non-negative")


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start: raise ValueError("invalid transcript timestamps")


@dataclass(frozen=True)
class TextModerationSignal:
    category: str
    confidence: float
    start_timestamp: float
    end_timestamp: float
    source_text: str

    def __post_init__(self) -> None:
        _confidence(self.confidence)
        if self.start_timestamp < 0 or self.end_timestamp < self.start_timestamp: raise ValueError("invalid signal timestamps")


@dataclass(frozen=True)
class ContextualInterpretation:
    category: str
    confidence: float
    reasoning: str
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None: _confidence(self.confidence)
