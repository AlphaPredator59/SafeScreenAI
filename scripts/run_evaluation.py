"""CLI entry point for running SafeScreen AI benchmark evaluations and ablation studies."""

import argparse
import os
from pathlib import Path
import sys
import time

# Ensure backend directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Ensure PATH has system/user path for FFmpeg if recently installed on Windows
system_path = os.environ.get("PATH", "")
user_path = os.environ.get("Path", "")
if "ffmpeg" not in system_path.lower() and "ffmpeg" not in user_path.lower():
    import subprocess
    try:
        updated_path = subprocess.run(
            ["powershell", "-NoProfile", "-Command", '[System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")'],
            capture_output=True, text=True, check=False
        ).stdout.strip()
        if updated_path:
            os.environ["PATH"] = updated_path + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

from app.core.config import Settings, get_settings
from app.services.evaluation.dataset import EvaluationDataset
from app.services.evaluation.report import EvaluationReportGenerator
from app.services.evaluation.runner import EvaluationRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="SafeScreen AI — Benchmark Evaluation & Ablation Runner")
    parser.add_argument("--dataset", default="evaluation/dataset.json", help="Path to evaluation dataset JSON")
    parser.add_argument("--output-dir", default="evaluation", help="Directory to save evaluation reports")
    parser.add_argument("--ai-mode", default="real", choices=["real", "mock"], help="AI execution mode (default: real)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Inference device (default: cpu)")
    parser.add_argument("--ablations", action="store_true", help="Run modality ablation studies in addition to full pipeline")
    args = parser.parse_args()

    dataset_path = (root_dir / args.dataset).resolve() if not Path(args.dataset).is_absolute() else Path(args.dataset)
    output_dir = (root_dir / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)

    print("=" * 70)
    print("SAFESCREEN AI — BENCHMARK EVALUATION & QUALITY SUITE")
    print("=" * 70)
    print(f"Dataset File:   {dataset_path}")
    print(f"Output Directory: {output_dir}")
    print(f"AI Mode:        {args.ai_mode.upper()}")
    print(f"Inference Device: {args.device.upper()}")
    print("=" * 70)

    try:
        dataset = EvaluationDataset.load_from_file(dataset_path)
    except Exception as exc:
        print(f"Error loading evaluation dataset: {exc}", file=sys.stderr)
        sys.exit(1)

    available = dataset.get_available_samples(base_dir=root_dir)
    unavailable = dataset.get_unavailable_samples(base_dir=root_dir)

    print(f"\nLoaded {len(dataset.samples)} total benchmark scenarios:")
    print(f"  * Available media files on disk:      {len(available)}")
    print(f"  * Unavailable placeholder scenarios:  {len(unavailable)}")
    print("\nNote: Headline accuracy/metrics are computed exclusively over available media.")

    # Configure runtime settings
    base_settings = get_settings()
    custom_settings = base_settings.model_copy(
        update={
            "ai_mode": args.ai_mode,
            "ai_device": args.device,
            "storage_path": root_dir / "storage",
        }
    )

    runner = EvaluationRunner(settings=custom_settings, storage_dir=root_dir / "storage")

    # 1. Run full pipeline benchmark
    print("\n" + "=" * 70)
    print("RUNNING FULL PIPELINE BENCHMARK (Mode: 'full')...")
    print("=" * 70)

    full_results, full_summary = runner.evaluate_dataset(dataset, ablation_mode="full", base_dir=root_dir)

    # 2. Run ablation studies if requested
    ablation_summaries: dict[str, Any] = {"full": full_summary}
    if args.ablations:
        for ab_mode in ["visual_qwen", "visual_audio", "visual_only"]:
            print("\n" + "=" * 70)
            print(f"RUNNING ABLATION STUDY (Mode: '{ab_mode}')...")
            print("=" * 70)
            _, ab_summary = runner.evaluate_dataset(dataset, ablation_mode=ab_mode, base_dir=root_dir)
            ablation_summaries[ab_mode] = ab_summary

    # 3. Export all reports
    generator = EvaluationReportGenerator(output_dir=output_dir)
    exported_files = generator.export_all(
        summary=full_summary,
        results=full_results,
        ablation_summaries=ablation_summaries if args.ablations else None,
    )

    # 4. Print console summary
    dm = full_summary.decision_metrics
    lat = full_summary.latency_metrics

    print("\n" + "=" * 70)
    print("BENCHMARK EVALUATION SUMMARY RESULTS")
    print("=" * 70)
    print(f"  Evaluated Samples Count: {full_summary.evaluated_samples_count} / {full_summary.total_dataset_samples}")
    print(f"  Decision Accuracy:       {dm.accuracy * 100:.1f}%")
    print(f"  Precision:               {dm.precision * 100:.1f}%")
    print(f"  Recall:                  {dm.recall * 100:.1f}%")
    print(f"  F1 Score:                {dm.f1_score:.4f}")
    print(f"  Review Rate:             {dm.review_rate * 100:.1f}%")
    print(f"  False Positive Rate:     {dm.false_positive_rate * 100:.1f}%")
    print(f"  False Negative Rate:     {dm.false_negative_rate * 100:.1f}%")
    print(f"  Context Accuracy:        {full_summary.context_metrics.accuracy * 100:.1f}%")
    print(f"  Model Disagreements:     {len(full_summary.model_disagreements)}")
    print(f"  Total Mean Latency:      {lat.total_pipeline.mean_seconds:.2f}s (Median: {lat.total_pipeline.median_seconds:.2f}s)")
    print("-" * 70)
    print("Generated Artifacts:")
    for key, path in exported_files.items():
        print(f"  * {key:<16}: {path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
