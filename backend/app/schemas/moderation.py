"""Public schemas for moderation results, findings, evidence, and report delivery."""

from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ModerationDecision, RiskLevel


class EvidenceItemResponse(BaseModel):
    """Sanitized, traceable evidence unit supporting a moderation finding."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    timestamp: float
    content: str | None = None
    reference: str | None = None


class FindingResponse(BaseModel):
    """A policy-relevant finding associated with a moderation assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    confidence: float
    start_timestamp: float
    end_timestamp: float | None = None
    explanation: str | None = None
    evidence_references: list[str] = Field(default_factory=list)


class TranscriptSegmentResponse(BaseModel):
    """A timestamped transcript segment from spoken dialogue."""

    model_config = ConfigDict(from_attributes=True)

    start_timestamp: float
    end_timestamp: float
    text: str


class ModerationReportResponse(BaseModel):
    """Structured, explainable platform moderation report for a video."""

    model_config = ConfigDict(from_attributes=True)

    video_id: str
    filename: str
    created_at: datetime
    decision: ModerationDecision
    risk_level: RiskLevel
    risk_score: float
    overall_confidence: float
    detected_categories: list[str]
    explanation: str
    findings: list[FindingResponse] = Field(default_factory=list)
    evidence: list[EvidenceItemResponse] = Field(default_factory=list)
    transcripts: list[TranscriptSegmentResponse] = Field(default_factory=list)


class EvidenceListResponse(BaseModel):
    """Public evidence collection for an analyzed video."""

    model_config = ConfigDict(from_attributes=True)

    video_id: str
    total_count: int
    evidence: list[EvidenceItemResponse] = Field(default_factory=list)
