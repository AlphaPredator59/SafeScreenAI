"""Evaluation metrics calculation engine for SafeScreen AI benchmark runs."""

from collections import defaultdict
import statistics
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ModerationDecision, RiskLevel


class ConfusionMatrix(BaseModel):
    """Confusion matrix representation with row (expected) and column (predicted) mappings."""

    model_config = ConfigDict(from_attributes=True)

    labels: list[str]
    matrix: dict[str, dict[str, int]] = Field(default_factory=dict)

    @classmethod
    def create(cls, labels: Sequence[str], pairs: Sequence[tuple[str, str]]) -> "ConfusionMatrix":
        """Build a confusion matrix from a collection of (expected, predicted) pairs."""
        matrix: dict[str, dict[str, int]] = {
            exp: {pred: 0 for pred in labels} for exp in labels
        }
        for exp, pred in pairs:
            if exp in matrix and pred in matrix[exp]:
                matrix[exp][pred] += 1
        return cls(labels=list(labels), matrix=matrix)


class BinaryMetrics(BaseModel):
    """Binary evaluation metrics for Safe (Approved) vs Unsafe (Review/Reject)."""

    model_config = ConfigDict(from_attributes=True)

    total: int = 0
    true_positives: int = 0  # Expected Unsafe, Predicted Unsafe
    false_positives: int = 0  # Expected Safe, Predicted Unsafe
    true_negatives: int = 0  # Expected Safe, Predicted Safe
    false_negatives: int = 0  # Expected Unsafe, Predicted Safe
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    review_rate: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0


class CategoryMetric(BaseModel):
    """Per-category classification metric."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    support: int = 0


class ContextMetrics(BaseModel):
    """Contextual classification evaluation."""

    model_config = ConfigDict(from_attributes=True)

    total_evaluated: int = 0
    correct_matches: int = 0
    accuracy: float = 0.0
    disagreement_count: int = 0


class ModelDisagreement(BaseModel):
    """Traceable cross-modal disagreement analysis."""

    model_config = ConfigDict(from_attributes=True)

    sample_id: str
    scenario_name: str
    yolo_categories: list[str] = Field(default_factory=list)
    qwen_context: str
    whisper_text: str = ""
    text_signals: list[str] = Field(default_factory=list)
    policy_findings: list[str] = Field(default_factory=list)
    disagreement_type: str
    description: str
    resolved_by_context: bool
    caused_false_positive: bool
    caused_false_negative: bool


class LatencyStat(BaseModel):
    """Latency distribution summary for a stage."""

    model_config = ConfigDict(from_attributes=True)

    mean_seconds: float = 0.0
    median_seconds: float = 0.0
    min_seconds: float = 0.0
    max_seconds: float = 0.0


class LatencyMetrics(BaseModel):
    """Comprehensive stage and total pipeline latency statistics."""

    model_config = ConfigDict(from_attributes=True)

    total_pipeline: LatencyStat = Field(default_factory=LatencyStat)
    per_stage: dict[str, LatencyStat] = Field(default_factory=dict)
    hardware_device: str = "cpu"
    sample_count: int = 0


class ErrorAnalysisItem(BaseModel):
    """Diagnostic detail for an erroneous prediction."""

    model_config = ConfigDict(from_attributes=True)

    sample_id: str
    scenario_name: str
    expected_decision: str
    predicted_decision: str
    expected_risk: str
    predicted_risk: str
    expected_policy: list[str]
    predicted_policy: list[str]
    likely_responsible_stage: str
    available_modalities: list[str]
    model_disagreement_occurred: bool
    context_policy_mapping_contributed: bool
    failure_reason: str
    possible_mitigation: str


class EvaluationSummaryMetrics(BaseModel):
    """Complete evaluation report data structure."""

    model_config = ConfigDict(from_attributes=True)

    total_dataset_samples: int = 0
    available_samples_count: int = 0
    unavailable_samples_count: int = 0
    evaluated_samples_count: int = 0
    is_statistically_representative: bool = False
    statistical_note: str = (
        "Headline metrics are computed exclusively over available media with verified ground truth. "
        "Results from small sample counts are preliminary diagnostics and not statistically representative."
    )
    decision_metrics: BinaryMetrics = Field(default_factory=BinaryMetrics)
    multiclass_confusion_matrix: ConfusionMatrix = Field(
        default_factory=lambda: ConfusionMatrix(labels=["APPROVED", "REVIEW_REQUIRED", "REJECTED"], matrix={})
    )
    binary_confusion_matrix: ConfusionMatrix = Field(
        default_factory=lambda: ConfusionMatrix(labels=["SAFE", "UNSAFE"], matrix={})
    )
    context_metrics: ContextMetrics = Field(default_factory=ContextMetrics)
    policy_category_metrics: dict[str, CategoryMetric] = Field(default_factory=dict)
    model_disagreements: list[ModelDisagreement] = Field(default_factory=list)
    latency_metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)
    errors: list[ErrorAnalysisItem] = Field(default_factory=list)


def is_unsafe(decision: ModerationDecision | str) -> bool:
    """Classify whether a moderation decision is considered Unsafe (Positive)."""
    val = decision.value if isinstance(decision, ModerationDecision) else str(decision)
    return val in ("REVIEW_REQUIRED", "REJECTED")


def calculate_latency_stat(values: Sequence[float]) -> LatencyStat:
    """Calculate mean, median, min, max for a sequence of floating-point seconds."""
    if not values:
        return LatencyStat()
    sorted_vals = sorted(values)
    return LatencyStat(
        mean_seconds=round(statistics.mean(sorted_vals), 4),
        median_seconds=round(statistics.median(sorted_vals), 4),
        min_seconds=round(min(sorted_vals), 4),
        max_seconds=round(max(sorted_vals), 4),
    )


def calculate_binary_metrics(
    eval_pairs: Sequence[tuple[ModerationDecision | str, ModerationDecision | str]]
) -> BinaryMetrics:
    """Calculate binary accuracy, precision, recall, F1, and review rate."""
    if not eval_pairs:
        return BinaryMetrics()

    total = len(eval_pairs)
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    review_count = 0

    for exp, pred in eval_pairs:
        exp_unsafe = is_unsafe(exp)
        pred_unsafe = is_unsafe(pred)
        pred_str = pred.value if isinstance(pred, ModerationDecision) else str(pred)
        if pred_str == "REVIEW_REQUIRED":
            review_count += 1

        if exp_unsafe and pred_unsafe:
            tp += 1
        elif not exp_unsafe and pred_unsafe:
            fp += 1
        elif not exp_unsafe and not pred_unsafe:
            tn += 1
        elif exp_unsafe and not pred_unsafe:
            fn += 1

    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    review_rate = review_count / total if total > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return BinaryMetrics(
        total=total,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        review_rate=round(review_rate, 4),
        false_positive_rate=round(fpr, 4),
        false_negative_rate=round(fnr, 4),
    )


def match_context_category(expected: str, predicted: str) -> bool:
    """Check whether predicted context matches expected context semantically or via keywords."""
    exp_clean = expected.strip().lower()
    pred_clean = predicted.strip().lower()
    if exp_clean == pred_clean:
        return True
    # Keyword overlap check
    exp_tokens = set(exp_clean.replace("/", " ").replace("-", " ").split())
    pred_tokens = set(pred_clean.replace("/", " ").replace("-", " ").split())
    if exp_tokens & pred_tokens:
        return True
    return False
