"""Moderation engine package and domain exports."""

from app.services.moderation.config import (
    DEFAULT_CONTEXT_POLICY_MAPPING,
    DEFAULT_POLICY_SEVERITIES,
    ModerationConfig,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult, PolicyEvent, PolicyFinding
from app.services.moderation.engine import ModerationEngine
from app.services.moderation.formatting import GeminiReportFormatter, get_report_formatter
from app.services.moderation.persistence import ModerationPersistenceError, ModerationPersistenceService
from app.services.moderation.pipeline_runner import (
    PipelineExecutionError,
    PipelineRunResult,
    PipelineRunner,
)
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository, ModerationRepositoryError
from app.services.moderation.temporal_grouping import (
    build_policy_findings,
    cluster_evidence_into_events,
    get_category_supporting_evidence,
)

__all__ = [
    "EvidenceItem",
    "ModerationResult",
    "PolicyEvent",
    "PolicyFinding",
    "ModerationConfig",
    "ModerationEngine",
    "DEFAULT_CONTEXT_POLICY_MAPPING",
    "DEFAULT_POLICY_SEVERITIES",
    "ModerationRepository",
    "ModerationRepositoryError",
    "ModerationPersistenceService",
    "ModerationPersistenceError",
    "ModerationReportService",
    "GeminiReportFormatter",
    "get_report_formatter",
    "PipelineRunner",
    "PipelineRunResult",
    "PipelineExecutionError",
    "build_policy_findings",
    "cluster_evidence_into_events",
    "get_category_supporting_evidence",
]
