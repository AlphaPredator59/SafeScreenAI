"""Development script to run and evaluate the end-to-end M1-M9 pipeline against a test video.

Refactored to delegate pipeline orchestration to the production PipelineRunner.
"""

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Any

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
from app.db.database import get_session_factory
from app.services.moderation import (
    PipelineExecutionError,
    PipelineRunResult,
    PipelineRunner,
)


def find_test_video(explicit_path: str | None = None) -> Path:
    """Locate the test video in the Test Videos folder or explicit path."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = root_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Specified video file not found at: {path}")
        return path

    test_videos_dir = root_dir / "Test Videos"
    if not test_videos_dir.exists():
        raise FileNotFoundError(f"'Test Videos' directory not found at: {test_videos_dir}")

    mp4_files = list(test_videos_dir.glob("*.mp4"))
    if not mp4_files:
        raise FileNotFoundError(f"No .mp4 files found in {test_videos_dir}")

    return mp4_files[0]


def run_pipeline(
    video_path: Path,
    ai_mode: str = "real",
    device: str = "cpu",
    interval: float = 1.0,
) -> bool:
    print("=" * 70)
    print("SafeScreen AI — M1-M9 Production Pipeline Evaluation")
    print("=" * 70)
    print(f"Target Video:    {video_path.name}")
    print(f"Absolute Path:   {video_path.resolve()}")
    print(f"File Size:       {video_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"AI Mode:         {ai_mode.upper()}")
    print(f"AI Device:       {device.upper()}")
    print(f"Frame Interval:  {interval}s")
    print("=" * 70)

    # Resolve settings
    base_settings = get_settings()
    settings = base_settings.model_copy(
        update={
            "ai_mode": ai_mode,
            "ai_device": device,
            "frame_sampling_interval_seconds": interval,
            "storage_path": root_dir / "storage",
        }
    )

    stage_display_names = {
        "metadata_extraction": "1. Metadata Extraction",
        "frame_processing": "2. Frame Processing",
        "audio_extraction": "3. Audio Extraction",
        "vision_analysis": "4. Vision Analysis (YOLO)",
        "transcription": "5. Transcription (Whisper)",
        "text_moderation": "6. Text Moderation (Transformer)",
        "context_analysis": "7. Context Analysis (Qwen 2.5 VL)",
        "moderation_engine": "8. Moderation Engine (Decision)",
        "persistence_reporting": "9. Persistence & Reporting",
    }

    stage_results: dict[str, dict[str, str | float | bool]] = {}
    warnings: list[str] = []

    def on_stage_complete(stage_name: str, data: dict[str, Any]) -> None:
        duration = data.get("duration", 0.0)
        display_name = stage_display_names.get(stage_name, stage_name)
        stage_results[display_name] = {"success": True, "time": duration}

        if stage_name == "frame_processing":
            frames = data.get("frames", [])
            print(f"\n[Stage 2/9] Sampling and Processing Frames (Milestone 2)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            print(f"  -> Extracted Frames: {len(frames)}")
            if frames:
                print(f"  -> First Frame:     ID={frames[0].frame_id}, t={frames[0].timestamp:.2f}s")
                mid = len(frames) // 2
                print(f"  -> Middle Frame:    ID={frames[mid].frame_id}, t={frames[mid].timestamp:.2f}s")
                print(f"  -> Last Frame:      ID={frames[-1].frame_id}, t={frames[-1].timestamp:.2f}s")

        elif stage_name == "audio_extraction":
            audio_avail = data.get("audio_available", False)
            artifact = data.get("artifact")
            print(f"\n[Stage 3/9] Extracting Audio Track (Milestone 3)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            print(f"  -> Audio Available: {audio_avail}")
            if audio_avail and artifact and artifact.storage_path:
                print(f"  -> Output Format:   {artifact.format}")
                print(f"  -> Audio Duration:  {artifact.duration:.2f}s" if artifact.duration else "  -> Audio Duration:  N/A")
                print(f"  -> Artifact Path:   {artifact.storage_path.resolve()}")
            else:
                print("  -> Notice:          No audio stream present in this video.")
                warnings.append("Video has no audio stream; transcription and text moderation received empty inputs.")

        elif stage_name == "vision_analysis":
            detections = data.get("detections", [])
            print(f"\n[Stage 4/9] Running YOLO VisionAnalyzer (Milestone 4)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            print(f"  -> Total Detections: {len(detections)}")
            categories_found = sorted(list({d.category for d in detections}))
            print(f"  -> Detected Classes: {', '.join(categories_found) if categories_found else 'None'}")
            for idx, d in enumerate(detections[:10]):
                box = d.metadata.get("box", "N/A")
                print(f"     [{idx+1:02d}] t={d.timestamp:4.1f}s | Category: {d.category:<12} | Conf: {d.confidence:.2f} | Evidence: {d.evidence_reference} | Box: {box}")
            if len(detections) > 10:
                print(f"     ... and {len(detections) - 10} more detections.")

        elif stage_name == "transcription":
            transcripts = data.get("transcripts", [])
            print(f"\n[Stage 5/9] Running Whisper Transcriber (Milestone 5)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            print(f"  -> Transcript Segments: {len(transcripts)}")
            if transcripts:
                for idx, seg in enumerate(transcripts):
                    print(f"     [seg_{idx:02d}] [{seg.start:4.1f}s - {seg.end:4.1f}s] \"{seg.text}\"")
            else:
                print("  -> Spoken Dialogue:  (None / Silent)")

        elif stage_name == "text_moderation":
            signals = data.get("signals", [])
            print(f"\n[Stage 6/9] Running Transformer TextModerator (Milestone 6)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            print(f"  -> Policy Signals Flagged: {len(signals)}")
            if signals:
                for idx, sig in enumerate(signals):
                    print(f"     [sig_{idx:02d}] [{sig.start_timestamp:4.1f}s - {sig.end_timestamp:4.1f}s] Category: {sig.category} | Conf: {sig.confidence:.2f} | Text: \"{sig.source_text}\"")
            else:
                print("  -> Policy Signals:  None (No harmful/toxic speech detected)")

        elif stage_name == "context_analysis":
            interp = data.get("interpretation")
            print(f"\n[Stage 7/9] Running Qwen 2.5 VL Multimodal ContextAnalyzer (Milestone 7)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.2f}s)")
            if interp:
                print("\n" + "-" * 50)
                print("QWEN 2.5 VL CONTEXTUAL INTERPRETATION:")
                print("-" * 50)
                print(f"  Category:            {interp.category}")
                print(f"  Confidence:          {interp.confidence:.2f}")
                print(f"  Reasoning:           {interp.reasoning}")
                print(f"  Evidence References: {list(interp.evidence_references)}")
                print("-" * 50)

        elif stage_name == "moderation_engine":
            mod_res = data.get("result")
            print(f"\n[Stage 8/9] Running Moderation Engine Evaluation (Milestone 8)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.4f}s)")
            if mod_res:
                print("\n" + "=" * 50)
                print("FINAL MODERATION ASSESSMENT (MILESTONE 8):")
                print("=" * 50)
                print(f"  Decision:            {mod_res.decision.value}")
                print(f"  Risk Level:          {mod_res.risk_level.value}")
                print(f"  Risk Score:          {mod_res.risk_score:.4f}")
                print(f"  Overall Confidence:  {mod_res.overall_confidence:.4f}")
                print(f"  Detected Categories: {list(mod_res.detected_categories)}")
                print(f"  Evidence Count:      {len(mod_res.supporting_evidence)}")
                print(f"  Explanation:         {mod_res.explanation}")
                print("=" * 50)

        elif stage_name == "persistence_reporting":
            rep = data.get("report")
            print(f"\n[Stage 9/9] Persisting to PostgreSQL & Generating Report (Milestone 9)...")
            print(f"  -> STATUS: SUCCESS (took {duration:.4f}s)")
            if rep:
                print("\n" + "=" * 50)
                print("PERSISTED STRUCTURED MODERATION REPORT (MILESTONE 9):")
                print("=" * 50)
                print(f"  Report Video ID:     {rep.video_id}")
                print(f"  Filename:            {rep.filename}")
                print(f"  Decision:            {rep.decision.value}")
                print(f"  Risk Level:          {rep.risk_level.value}")
                print(f"  Risk Score:          {rep.risk_score:.4f}")
                print(f"  Overall Confidence:  {rep.overall_confidence:.4f}")
                print(f"  Detected Categories: {rep.detected_categories}")
                print(f"  Findings Count:      {len(rep.findings)}")
                for idx, f in enumerate(rep.findings):
                    print(f"    [Finding {idx+1}] Category: {f.category} | Conf: {f.confidence:.2f} | Time: [{f.start_timestamp}s - {f.end_timestamp}s]")
                    print(f"                     Explanation: {f.explanation}")
                    print(f"                     Evidence Refs: {f.evidence_references}")
                    if f.events:
                        for ev_idx, ev in enumerate(f.events):
                            print(f"                     -> Event {ev_idx+1}: [{ev.start_time:.1f}s - {ev.end_time:.1f}s] Conf: {ev.confidence:.2f} | Evidence items: {len(ev.evidence_ids)}")
                            print(f"                                  Desc: {ev.description}")
                print(f"  Traceable Evidence:  {len(rep.evidence)} items")
                print(f"  Transcripts:         {len(rep.transcripts)} segments")
                print(f"  Explanation:         {rep.explanation}")
                print("=" * 50)

    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            runner = PipelineRunner(session=session, settings=settings)

            # Metadata extraction logging
            print("\n[Stage 1/9] Extracting Video Metadata (Milestone 1)...")
            s1_start = time.perf_counter()
            from app.services.video.metadata import VideoMetadataService
            metadata = VideoMetadataService().extract(video_path)
            s1_time = time.perf_counter() - s1_start
            stage_results["1. Metadata Extraction"] = {"success": True, "time": s1_time}
            print(f"  -> STATUS: SUCCESS (took {s1_time:.2f}s)")
            print(f"  -> Duration:        {metadata.duration:.2f}s")
            print(f"  -> Resolution:      {metadata.width}x{metadata.height}")
            print(f"  -> FPS:             {metadata.fps:.2f}")
            print(f"  -> Total Frames:    {metadata.frame_count}")
            print(f"  -> Codec:           {metadata.codec or 'Unknown'}")
            print(f"  -> Audio Stream:    {'Detected' if metadata.audio_available else 'Not detected'}")

            # Execute production pipeline runner
            result: PipelineRunResult = runner.register_and_run(
                video_path=video_path,
                stage_callback=on_stage_complete,
            )

        print("\n" + "=" * 70)
        print("PIPELINE EXECUTION SUMMARY (M1 - M9):")
        print("=" * 70)
        all_succeeded = all(bool(res.get("success")) for res in stage_results.values())

        for stage_name, res in stage_results.items():
            status_str = "PASS" if res.get("success") else "FAIL"
            time_str = f"{res.get('time', 0.0):.2f}s"
            print(f"  * {stage_name:<36} [{status_str}] ({time_str})")

        print("-" * 70)
        print(f"  Total Pipeline Execution Time: {result.total_duration:.2f}s")
        print(f"  All Stages Succeeded:          {'YES' if all_succeeded else 'NO'}")
        if warnings:
            print("\n  Warnings encountered:")
            for w in warnings:
                print(f"    - {w}")
        print(f"  End-to-End M1-M9 Integration:  {'CONFIRMED OPERATIONAL' if all_succeeded else 'INCOMPLETE'}")
        print("=" * 70)

        # Print structured moderation JSON
        import json
        report_json = json.dumps(result.report.model_dump(mode="json"), indent=2)
        print("\nFINAL STRUCTURED MODERATION REPORT JSON:")
        print(report_json)

        return all_succeeded

    except PipelineExecutionError as exc:
        print(f"\nPipeline execution failed: {exc}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"\nUnexpected error during pipeline run: {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Test M1-M9 Video Moderation Pipeline end-to-end via PipelineRunner.")
    parser.add_argument("--video", default=None, help="Path to input video file (default: first .mp4 in 'Test Videos/')")
    parser.add_argument("--ai-mode", default="real", choices=["real", "mock"], help="AI execution mode (default: real)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Torch device for local models (default: cpu)")
    parser.add_argument("--interval", type=float, default=1.0, help="Frame sampling interval in seconds (default: 1.0)")
    args = parser.parse_args()

    try:
        video_path = find_test_video(args.video)
    except Exception as exc:
        print(f"Error locating input video: {exc}", file=sys.stderr)
        sys.exit(1)

    success = run_pipeline(
        video_path=video_path,
        ai_mode=args.ai_mode,
        device=args.device,
        interval=args.interval,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
