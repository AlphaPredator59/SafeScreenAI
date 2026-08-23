"""Report generation for SafeScreen AI evaluation benchmarks and ablation studies."""

import json
from pathlib import Path
from typing import Sequence

from app.services.evaluation.metrics import EvaluationSummaryMetrics
from app.services.evaluation.runner import SampleEvaluationResult


class EvaluationReportGenerator:
    """Formats and exports benchmark metrics, confusion matrices, and markdown reports."""

    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        summary: EvaluationSummaryMetrics,
        results: Sequence[SampleEvaluationResult],
        ablation_summaries: dict[str, EvaluationSummaryMetrics] | None = None,
    ) -> dict[str, Path]:
        """Export results.json, metrics.json, summary.md, and errors.md."""
        results_path = self.output_dir / "results.json"
        metrics_path = self.output_dir / "metrics.json"
        summary_path = self.output_dir / "summary.md"
        errors_path = self.output_dir / "errors.md"

        # 1. results.json
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode="json") for r in results], f, indent=2)

        # 2. metrics.json
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(mode="json"), f, indent=2)

        # 3. summary.md
        summary_md = self.generate_summary_markdown(summary, results, ablation_summaries)
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_md)

        # 4. errors.md
        errors_md = self.generate_errors_markdown(summary, results)
        with open(errors_path, "w", encoding="utf-8") as f:
            f.write(errors_md)

        return {
            "results_json": results_path,
            "metrics_json": metrics_path,
            "summary_md": summary_path,
            "errors_md": errors_path,
        }

    def generate_summary_markdown(
        self,
        summary: EvaluationSummaryMetrics,
        results: Sequence[SampleEvaluationResult],
        ablation_summaries: dict[str, EvaluationSummaryMetrics] | None = None,
    ) -> str:
        """Generate formatted human-readable summary markdown report."""
        dm = summary.decision_metrics
        cm_multi = summary.multiclass_confusion_matrix
        cm_bin = summary.binary_confusion_matrix
        ctx = summary.context_metrics
        lat = summary.latency_metrics

        lines = [
            "# SafeScreen AI — Benchmark Evaluation Report",
            "",
            "## Executive Summary",
            "",
            f"- **Dataset Total Samples**: {summary.total_dataset_samples}",
            f"- **Available Samples Evaluated**: {summary.evaluated_samples_count}",
            f"- **Unavailable Placeholder Samples**: {summary.unavailable_samples_count}",
            f"- **Inference Device**: {lat.hardware_device.upper()}",
            "",
            "> [!NOTE]",
            f"> {summary.statistical_note}",
            "",
            "---",
            "",
            "## 1. Headline Decision Metrics (Safe vs Unsafe)",
            "",
            "| Metric | Score | Note |",
            "| :--- | :--- | :--- |",
            f"| **Accuracy** | `{dm.accuracy * 100:.1f}%` | (TP + TN) / Total |",
            f"| **Precision** | `{dm.precision * 100:.1f}%` | TP / (TP + FP) |",
            f"| **Recall** | `{dm.recall * 100:.1f}%` | TP / (TP + FN) |",
            f"| **F1 Score** | `{dm.f1_score:.4f}` | Harmonic mean of Precision & Recall |",
            f"| **Review Rate** | `{dm.review_rate * 100:.1f}%` | Proportion resulting in REVIEW_REQUIRED |",
            f"| **False Positive Rate (FPR)** | `{dm.false_positive_rate * 100:.1f}%` | Safe misclassified as Unsafe |",
            f"| **False Negative Rate (FNR)** | `{dm.false_negative_rate * 100:.1f}%` | Unsafe misclassified as Safe |",
            "",
            "---",
            "",
            "## 2. Confusion Matrices",
            "",
            "### Binary Confusion Matrix",
            "",
            "| Expected \\ Predicted | Pred SAFE | Pred UNSAFE |",
            "| :--- | :--- | :--- |",
            f"| **Exp SAFE** | `{cm_bin.matrix.get('SAFE', {}).get('SAFE', 0)}` (TN) | `{cm_bin.matrix.get('SAFE', {}).get('UNSAFE', 0)}` (FP) |",
            f"| **Exp UNSAFE** | `{cm_bin.matrix.get('UNSAFE', {}).get('SAFE', 0)}` (FN) | `{cm_bin.matrix.get('UNSAFE', {}).get('UNSAFE', 0)}` (TP) |",
            "",
            "### Multiclass Confusion Matrix",
            "",
            "| Expected \\ Predicted | Pred APPROVED | Pred REVIEW_REQUIRED | Pred REJECTED |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for exp_label in cm_multi.labels:
            row = cm_multi.matrix.get(exp_label, {})
            app_cnt = row.get("APPROVED", 0)
            rev_cnt = row.get("REVIEW_REQUIRED", 0)
            rej_cnt = row.get("REJECTED", 0)
            lines.append(f"| **Exp {exp_label}** | `{app_cnt}` | `{rev_cnt}` | `{rej_cnt}` |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Dataset Sample Status Breakdown",
            "",
            "| Sample ID | Scenario | Local File | Status | Expected Decision | Predicted Decision | Match |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for r in results:
            stat_badge = f"**{r.status}**" if r.status == "EVALUATED" else f"*{r.status}*"
            pred_dec = r.predicted_decision.value if r.predicted_decision else "—"
            match_icon = "PASS" if r.is_correct_decision else ("FAIL" if r.status == "EVALUATED" else "N/A")
            fname = Path(r.video_path).name if r.video_path else "None"
            lines.append(
                f"| `{r.sample_id}` | {r.scenario_name} | `{fname}` | {stat_badge} | `{r.ground_truth.expected_decision.value}` | `{pred_dec}` | `{match_icon}` |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 4. Contextual Analysis & Disagreements",
            "",
            f"- **Context Categorization Accuracy**: `{ctx.accuracy * 100:.1f}%` ({ctx.correct_matches}/{ctx.total_evaluated})",
            f"- **Cross-Modal Disagreements Detected**: `{len(summary.model_disagreements)}`",
            "",
        ])

        if summary.model_disagreements:
            lines.extend([
                "| Sample | Scenario | YOLO Objects | Qwen Context | Resolved by Context |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ])
            for d in summary.model_disagreements:
                yolo_str = ", ".join(d.yolo_categories) or "None"
                res_str = "YES (Mitigated)" if d.resolved_by_context else "NO"
                lines.append(f"| `{d.sample_id}` | {d.scenario_name} | `{yolo_str}` | `{d.qwen_context}` | {res_str} |")
        else:
            lines.append("*No cross-modal model disagreements detected.*")

        lines.extend([
            "",
            "---",
            "",
            "## 5. Policy Category Classification Metrics",
            "",
            "| Category | Precision | Recall | F1 Score | Support (True Positives in Eval) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])

        for cat_name, cat_m in summary.policy_category_metrics.items():
            if cat_m.support > 0 or (cat_m.true_positives + cat_m.false_positives) > 0:
                lines.append(
                    f"| **{cat_name}** | `{cat_m.precision * 100:.1f}%` | `{cat_m.recall * 100:.1f}%` | `{cat_m.f1_score:.4f}` | {cat_m.support} |"
                )

        lines.extend([
            "",
            "---",
            "",
            "## 6. Pipeline Latency Breakdown",
            "",
            f"- **Total Pipeline Mean Latency**: `{lat.total_pipeline.mean_seconds:.2f}s` (Median: `{lat.total_pipeline.median_seconds:.2f}s`, Min: `{lat.total_pipeline.min_seconds:.2f}s`, Max: `{lat.total_pipeline.max_seconds:.2f}s`)",
            "",
            "| Stage | Mean Latency | Median Latency | Min Latency | Max Latency |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])

        for st_name, st_stat in lat.per_stage.items():
            lines.append(
                f"| **{st_name}** | `{st_stat.mean_seconds:.2f}s` | `{st_stat.median_seconds:.2f}s` | `{st_stat.min_seconds:.2f}s` | `{st_stat.max_seconds:.2f}s` |"
            )

        if ablation_summaries:
            lines.extend([
                "",
                "---",
                "",
                "## 7. Modality Ablation Analysis",
                "",
                "| Ablation Mode | Modalities Included | Accuracy | Precision | Recall | F1 Score | Mean Latency |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ])
            for mode_name, ab_sum in ablation_summaries.items():
                mod_desc = {
                    "full": "Visual + Audio + Text + Qwen",
                    "visual_qwen": "Visual + Qwen Context",
                    "visual_audio": "Visual + Whisper + Text Moderator",
                    "visual_only": "Visual Only",
                }.get(mode_name, mode_name)
                adm = ab_sum.decision_metrics
                alat = ab_sum.latency_metrics.total_pipeline.mean_seconds
                lines.append(
                    f"| **{mode_name}** | {mod_desc} | `{adm.accuracy * 100:.1f}%` | `{adm.precision * 100:.1f}%` | `{adm.recall * 100:.1f}%` | `{adm.f1_score:.4f}` | `{alat:.2f}s` |"
                )

        return "\n".join(lines)

    def generate_errors_markdown(
        self,
        summary: EvaluationSummaryMetrics,
        results: Sequence[SampleEvaluationResult],
    ) -> str:
        """Generate formatted human-readable error analysis markdown."""
        lines = [
            "# SafeScreen AI — Benchmark Error Analysis",
            "",
            f"**Total Evaluated Samples**: {summary.evaluated_samples_count}",
            f"**Total Decision Errors**: {len(summary.errors)}",
            "",
            "---",
        ]

        if not summary.errors:
            lines.extend([
                "## Error Diagnostics: Zero Decision Errors",
                "",
                "All evaluated available samples matched their ground-truth moderation decisions and policy classifications.",
                "",
                "### Evaluated Sample Ground Truth Validations:",
            ])
            for r in results:
                if r.status == "EVALUATED":
                    pred_dec_str = r.predicted_decision.value if r.predicted_decision else "NONE"
                    pred_risk_str = r.predicted_risk_level.value if r.predicted_risk_level else "NONE"
                    pred_score_str = f"{r.predicted_risk_score:.4f}" if r.predicted_risk_score is not None else "0.0000"
                    lines.append(
                        f"- **`{r.sample_id}` ({r.scenario_name})**: Predicted `{pred_dec_str}` (Risk: `{pred_risk_str}` / `{pred_score_str}`) exactly matched Ground Truth (`{r.ground_truth.expected_decision.value}`)."
                    )
            return "\n".join(lines)

        lines.append("## Error Diagnostics Details\n")
        for idx, err in enumerate(summary.errors, 1):
            lines.extend([
                f"### Error {idx}: `{err.sample_id}` ({err.scenario_name})",
                "",
                f"- **Expected Decision**: `{err.expected_decision}` (Risk: `{err.expected_risk}`)",
                f"- **Predicted Decision**: `{err.predicted_decision}` (Risk: `{err.predicted_risk}`)",
                f"- **Expected Policy Categories**: `{err.expected_policy}`",
                f"- **Predicted Policy Categories**: `{err.predicted_policy}`",
                f"- **Likely Responsible Stage**: `{err.likely_responsible_stage}`",
                f"- **Available Modalities**: `{err.available_modalities}`",
                f"- **Model Disagreement**: `{'YES' if err.model_disagreement_occurred else 'NO'}`",
                f"- **Context-Policy Mapping Contributed**: `{'YES' if err.context_policy_mapping_contributed else 'NO'}`",
                f"- **Failure Reason**: {err.failure_reason}",
                f"- **Possible Mitigation**: {err.possible_mitigation}",
                "",
                "---",
            ])

        return "\n".join(lines)
