"""Real AI model stress testing across repeated runs, cold vs warm latencies, and cross-modal disagreements."""

import json
from pathlib import Path
import statistics
import sys
import time

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.services.evaluation.dataset import EvaluationSample, GroundTruth
from app.services.evaluation.runner import EvaluationRunner


def run_real_ai_stress():
    settings = get_settings().model_copy(update={"ai_mode": "real", "ai_device": "cpu"})
    runner = EvaluationRunner(settings=settings, storage_dir=root_dir / "storage")

    videos_to_test = [
        ("cooking", "Cooking.mp4", "cooking"),
        ("shooting_range", "Shooting Range.mp4", "shooting range / controlled firearm practice"),
        ("slap", "Slap.mp4", "threatening interaction / physical assault"),
    ]

    print("=" * 80)
    print("PHASE 4 & 5 & 6: REAL AI STRESS TEST (3 REPEATS PER VIDEO)")
    print("=" * 80)

    stress_data = {}

    for vid_id, vid_file, exp_ctx in videos_to_test:
        vid_path = root_dir / "Test Videos" / vid_file
        print(f"\nEvaluating '{vid_file}' (Repeats: 3)...")

        sample = EvaluationSample(
            id=f"stress_{vid_id}",
            scenario_name=f"Stress test {vid_file}",
            local_path=str(vid_path),
            available=True,
            ground_truth=GroundTruth(
                expected_context=exp_ctx,
                expected_decision="APPROVED" if "slap" not in vid_id else "REVIEW_REQUIRED",
                expected_risk_level="LOW" if "slap" not in vid_id else "HIGH",
            ),
        )

        runs = []
        for r_idx in range(1, 4):
            t_start = time.perf_counter()
            res = runner.run_sample(sample, ablation_mode="full", base_dir=root_dir)
            t_elapsed = time.perf_counter() - t_start

            runs.append({
                "run": r_idx,
                "decision": res.predicted_decision.value if res.predicted_decision else "NONE",
                "risk_level": res.predicted_risk_level.value if res.predicted_risk_level else "NONE",
                "risk_score": res.predicted_risk_score,
                "confidence": res.predicted_overall_confidence,
                "context": res.predicted_context,
                "yolo_classes": res.yolo_categories,
                "policy_categories": res.predicted_policy_categories,
                "transcripts": res.transcripts,
                "total_latency": res.total_latency,
                "stage_latencies": res.stage_latencies,
            })
            print(f"  [Run {r_idx}] Decision: {res.predicted_decision.value} | Risk: {res.predicted_risk_level.value} ({res.predicted_risk_score:.4f}) | Latency: {res.total_latency:.2f}s | Context: '{res.predicted_context}'")

        latencies = [r["total_latency"] for r in runs]
        stress_data[vid_file] = {
            "runs": runs,
            "cold_latency": latencies[0],
            "warm_latencies": latencies[1:],
            "mean_latency": statistics.mean(latencies),
            "median_latency": statistics.median(latencies),
            "variance": statistics.variance(latencies) if len(latencies) > 1 else 0.0,
        }

    print("\n" + "=" * 80)
    print("AI STRESS & LATENCY SUMMARY:")
    print("=" * 80)
    for vname, vstat in stress_data.items():
        print(f"  * {vname:<20}: Cold={vstat['cold_latency']:.2f}s | Warm Mean={statistics.mean(vstat['warm_latencies']):.2f}s | Var={vstat['variance']:.4f}")
    print("=" * 80)

    # Save stress data
    out_file = root_dir / "evaluation" / "ai_stress_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(stress_data, f, indent=2)
    print(f"Saved AI stress details to {out_file}")


if __name__ == "__main__":
    run_real_ai_stress()
