"""Controlled values persisted by the moderation domain."""

from enum import Enum


class VideoStatus(str, Enum):
    """Lifecycle states for an uploaded video."""

    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModerationDecision(str, Enum):
    """Platform-level outcomes of a moderation assessment."""

    APPROVED = "APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class RiskLevel(str, Enum):
    """Severity bands assigned by the moderation engine."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
