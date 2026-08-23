"""Deterministic unit tests for Milestone 10 evaluation dataset, metrics, and report generator."""

import json
from pathlib import Path
import pytest

from app.db.enums import ModerationDecision, RiskLevel
from app.services.evaluation.dataset import (
    EvaluationDataset,
    EvaluationSample,
    GroundTruth,
    ModalityAvailability,
)
from app.services.evaluation.metrics import (
    BinaryMetrics,
    ConfusionMatrix,
    ContextMetrics,
    EvaluationSummaryMetrics,
    LatencyMetrics,
    LatencyStat,
    calculate_binary_metrics,
    calculate_latency_stat,
    is_unsafe,
    match_context_category,
)
from app.services.evaluation.report import EvaluationReportGenerator
from app.services.evaluation.runner import EvaluationRunner, SampleEvaluationResult


def test_dataset_parsing_and_validation(tmp_path: Path) -> None:
    """Evaluation dataset correctly parses valid JSON schemas."""
    sample_data = {
        "version": "1.0.0",
        "description": "Test dataset",
        "samples": [
            {
                "id": "test_01",
                "scenario_name": "Sample Cooking",
                "local_path": "Test Videos/Cooking.mp4",
                "available": True,
                "modalities": {"visual": True, "audio": False, "transcript": False},
                "ground_truth": {
                    "expected_context": "cooking",
                    "expected_decision": "APPROVED",
                    "expected_risk_level": "LOW",
                    "expected_policy_categories": [],
                    "acceptable_policy_alternatives": [],
                },
                "notes": "Test note",
            },
            {
                "id": "test_02_placeholder",
                "scenario_name": "Placeholder",
                "local_path": "non_existent_clip.mp4",
                "available": False,
                "modalities": {"visual": True, "audio": True, "transcript": True},
                "ground_truth": {
                    "expected_context": "assault",
                    "expected_decision": "REVIEW_REQUIRED",
                    "expected_risk_level": "HIGH",
                    "expected_policy_categories": ["violence"],
                    "acceptable_policy_alternatives": [],
                },
                "notes": "Placeholder",
            },
        ],
    }

    dataset_file = tmp_path / "dataset.json"
    with open(dataset_file, "w", encoding="utf-8") as f:
        json.dump(sample_data, f)

    dataset = EvaluationDataset.load_from_file(dataset_file)
    assert len(dataset.samples) == 2
    assert dataset.samples[0].id == "test_01"
    assert dataset.samples[0].ground_truth.expected_decision == ModerationDecision.APPROVED
    assert dataset.samples[1].available is False


def test_available_vs_unavailable_separation(tmp_path: Path) -> None:
    """Dataset separates confirmed media files from placeholder samples."""
    real_video = tmp_path / "real.mp4"
    real_video.touch()

    dataset = EvaluationDataset(
        version="1.0.0",
        description="Test",
        samples=[
            EvaluationSample(
                id="s1",
                scenario_name="Real",
                local_path=str(real_video),
                available=True,
                ground_truth=GroundTruth(
                    expected_context="test",
                    expected_decision=ModerationDecision.APPROVED,
                    expected_risk_level=RiskLevel.LOW,
                ),
            ),
            EvaluationSample(
                id="s2",
                scenario_name="Missing",
                local_path=str(tmp_path / "missing.mp4"),
                available=False,
                ground_truth=GroundTruth(
                    expected_context="test",
                    expected_decision=ModerationDecision.REVIEW_REQUIRED,
                    expected_risk_level=RiskLevel.HIGH,
                ),
            ),
        ],
    )

    available = dataset.get_available_samples()
    unavailable = dataset.get_unavailable_samples()

    assert len(available) == 1
    assert available[0].id == "s1"
    assert len(unavailable) == 1
    assert unavailable[0].id == "s2"


def test_confusion_matrix_creation() -> None:
    """ConfusionMatrix aggregates row (expected) and column (predicted) frequencies correctly."""
    labels = ["APPROVED", "REVIEW_REQUIRED", "REJECTED"]
    pairs = [
        ("APPROVED", "APPROVED"),
        ("APPROVED", "APPROVED"),
        ("APPROVED", "REVIEW_REQUIRED"),  # 1 FP
        ("REVIEW_REQUIRED", "REVIEW_REQUIRED"),
        ("REJECTED", "REJECTED"),
    ]

    cm = ConfusionMatrix.create(labels, pairs)
    assert cm.matrix["APPROVED"]["APPROVED"] == 2
    assert cm.matrix["APPROVED"]["REVIEW_REQUIRED"] == 1
    assert cm.matrix["REVIEW_REQUIRED"]["REVIEW_REQUIRED"] == 1
    assert cm.matrix["REJECTED"]["REJECTED"] == 1
    assert cm.matrix["REJECTED"]["APPROVED"] == 0


def test_binary_metrics_calculation_perfect_score() -> None:
    """Perfect predictions yield 1.0 accuracy, precision, recall, and F1."""
    pairs = [
        (ModerationDecision.APPROVED, ModerationDecision.APPROVED),
        (ModerationDecision.APPROVED, ModerationDecision.APPROVED),
        (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.REVIEW_REQUIRED),
        (ModerationDecision.REJECTED, ModerationDecision.REJECTED),
    ]

    metrics = calculate_binary_metrics(pairs)
    assert metrics.total == 4
    assert metrics.true_positives == 2  # 2 Unsafe
    assert metrics.true_negatives == 2  # 2 Safe
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1_score == 1.0
    assert metrics.review_rate == 0.25  # 1 of 4 is REVIEW_REQUIRED


def test_binary_metrics_calculation_with_errors() -> None:
    """Mathematical validation for false positives and false negatives."""
    pairs = [
        (ModerationDecision.APPROVED, ModerationDecision.APPROVED),  # TN
        (ModerationDecision.APPROVED, ModerationDecision.REVIEW_REQUIRED),  # FP
        (ModerationDecision.REVIEW_REQUIRED, ModerationDecision.APPROVED),  # FN
        (ModerationDecision.REJECTED, ModerationDecision.REJECTED),  # TP
    ]

    metrics = calculate_binary_metrics(pairs)
    assert metrics.total == 4
    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 1
    assert metrics.false_negatives == 1
    assert metrics.accuracy == 0.5
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1_score == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.false_negative_rate == 0.5


def test_latency_stat_calculation() -> None:
    """Latency calculation accurately computes mean, median, min, max."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    stat = calculate_latency_stat(values)
    assert stat.mean_seconds == 3.0
    assert stat.median_seconds == 3.0
    assert stat.min_seconds == 1.0
    assert stat.max_seconds == 5.0


def test_context_matching_logic() -> None:
    """Semantic and keyword matching tests for context predictions."""
    assert match_context_category("cooking", "cooking") is True
    assert match_context_category("cooking", "Cooking demonstration") is True
    assert match_context_category("shooting range / firearm practice", "controlled shooting range") is True
    assert match_context_category("threatening interaction", "threatening altercation") is True
    assert match_context_category("cooking", "violent street fight") is False


def test_runner_calculates_summary_without_unavailable_samples() -> None:
    """Summary metrics strictly evaluate available samples and exclude placeholders."""
    dataset = EvaluationDataset(
        version="1.0.0",
        description="Test",
        samples=[
            EvaluationSample(
                id="s1",
                scenario_name="Real",
                local_path="real.mp4",
                available=True,
                ground_truth=GroundTruth(
                    expected_context="cooking",
                    expected_decision=ModerationDecision.APPROVED,
                    expected_risk_level=RiskLevel.LOW,
                ),
            ),
            EvaluationSample(
                id="s2",
                scenario_name="Placeholder",
                local_path="missing.mp4",
                available=False,
                ground_truth=GroundTruth(
                    expected_context="assault",
                    expected_decision=ModerationDecision.REVIEW_REQUIRED,
                    expected_risk_level=RiskLevel.HIGH,
                ),
            ),
        ],
    )

    results = [
        SampleEvaluationResult(
            sample_id="s1",
            scenario_name="Real",
            video_path="real.mp4",
            status="EVALUATED",
            ground_truth=dataset.samples[0].ground_truth,
            predicted_decision=ModerationDecision.APPROVED,
            predicted_risk_level=RiskLevel.LOW,
            predicted_risk_score=0.0,
            predicted_overall_confidence=0.95,
            predicted_context="cooking",
            is_correct_decision=True,
            is_correct_context=True,
            total_latency=1.5,
        ),
        SampleEvaluationResult(
            sample_id="s2",
            scenario_name="Placeholder",
            video_path="missing.mp4",
            status="UNAVAILABLE",
            ground_truth=dataset.samples[1].ground_truth,
            error_message="Not found",
        ),
    ]

    runner = EvaluationRunner()
    summary = runner.calculate_summary(dataset, results)

    assert summary.total_dataset_samples == 2
    assert summary.available_samples_count == 1
    assert summary.unavailable_samples_count == 1
    assert summary.evaluated_samples_count == 1
    assert summary.decision_metrics.accuracy == 1.0
    assert summary.decision_metrics.total == 1


def test_report_generator_exports_all_files(tmp_path: Path) -> None:
    """Report generator produces valid JSON and markdown artifacts."""
    generator = EvaluationReportGenerator(output_dir=tmp_path)

    summary = EvaluationSummaryMetrics(
        total_dataset_samples=2,
        available_samples_count=1,
        unavailable_samples_count=1,
        evaluated_samples_count=1,
        decision_metrics=BinaryMetrics(total=1, true_negatives=1, accuracy=1.0, precision=0.0, recall=0.0, f1_score=0.0),
        context_metrics=ContextMetrics(total_evaluated=1, correct_matches=1, accuracy=1.0),
        latency_metrics=LatencyMetrics(total_pipeline=LatencyStat(mean_seconds=2.0, median_seconds=2.0, min_seconds=2.0, max_seconds=2.0)),
    )

    results = [
        SampleEvaluationResult(
            sample_id="s1",
            scenario_name="Real",
            video_path="real.mp4",
            status="EVALUATED",
            ground_truth=GroundTruth(
                expected_context="cooking",
                expected_decision=ModerationDecision.APPROVED,
                expected_risk_level=RiskLevel.LOW,
            ),
            predicted_decision=ModerationDecision.APPROVED,
            is_correct_decision=True,
            total_latency=2.0,
        )
    ]

    files = generator.export_all(summary, results)
    assert files["results_json"].exists()
    assert files["metrics_json"].exists()
    assert files["summary_md"].exists()
    assert files["errors_md"].exists()

    with open(files["summary_md"], "r", encoding="utf-8") as f:
        content = f.read()
        assert "Benchmark Evaluation Report" in content
        assert "Headline Decision Metrics" in content
