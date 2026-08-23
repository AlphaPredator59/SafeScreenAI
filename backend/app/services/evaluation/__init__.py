"""Evaluation package exports for SafeScreen AI."""

from app.services.evaluation.dataset import (
    EvaluationDataset,
    EvaluationSample,
    GroundTruth,
    ModalityAvailability,
)
from app.services.evaluation.metrics import (
    BinaryMetrics,
    CategoryMetric,
    ConfusionMatrix,
    ContextMetrics,
    ErrorAnalysisItem,
    EvaluationSummaryMetrics,
    LatencyMetrics,
    LatencyStat,
    ModelDisagreement,
    calculate_binary_metrics,
    calculate_latency_stat,
    is_unsafe,
    match_context_category,
)
from app.services.evaluation.report import EvaluationReportGenerator
from app.services.evaluation.runner import EvaluationRunner, SampleEvaluationResult

__all__ = [
    "EvaluationDataset",
    "EvaluationSample",
    "GroundTruth",
    "ModalityAvailability",
    "BinaryMetrics",
    "CategoryMetric",
    "ConfusionMatrix",
    "ContextMetrics",
    "LatencyMetrics",
    "LatencyStat",
    "ModelDisagreement",
    "ErrorAnalysisItem",
    "EvaluationSummaryMetrics",
    "calculate_binary_metrics",
    "calculate_latency_stat",
    "is_unsafe",
    "match_context_category",
    "EvaluationRunner",
    "SampleEvaluationResult",
    "EvaluationReportGenerator",
]
