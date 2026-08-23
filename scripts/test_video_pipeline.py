"""Development script to run and evaluate the end-to-end M1-M7 pipeline against a test video."""

import argparse
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

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
from app.db.models import Video
from app.services.ai.contracts import (
    AIServiceError,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)
from app.services.ai.factory import (
    get_context_analyzer,
    get_text_moderator,
    get_transcriber,
    get_vision_analyzer,
)
from app.services.video.metadata import VideoMetadata, VideoMetadataService
from app.services.video.processing import (
    AudioArtifact,
    AudioProcessingService,
    FrameArtifact,
    FrameProcessingService,
)
from app.services.video.storage import LocalStorageService


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
    print("SafeScreen AI — M1-M7 End-to-End Pipeline Evaluation")
    print("=" * 70)
    print(f"Target Video:    {video_path.name}")
    print(f"Absolute Path:   {video_path.resolve()}")
    print(f"File Size:       {video_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"AI Mode:         {ai_mode.upper()}")
    print(f"AI Device:       {device.upper()}")
    print(f"Frame Interval:  {interval}s")
    print("=" * 70)

    # Initialize settings and local storage
    settings = Settings(
        ai_mode=ai_mode,
        ai_device=device,
        frame_sampling_interval_seconds=interval,
        storage_path=root_dir / "storage",
    )
    storage = LocalStorageService(root_path=settings.storage_path)

    stage_results: dict[str, dict[str, str | float | bool]] = {}
    warnings: list[str] = []
    overall_start_time = time.perf_counter()

    # -------------------------------------------------------------------------
    # Milestone 1: Video Metadata Extraction
    # -------------------------------------------------------------------------
    print("\n[Stage 1/7] Extracting Video Metadata (Milestone 1)...")
    s1_start = time.perf_counter()
    metadata: VideoMetadata | None = None
    try:
        metadata_service = VideoMetadataService()
        metadata = metadata_service.extract(video_path)
        s1_time = time.perf_counter() - s1_start
        stage_results["1. Metadata Extraction"] = {"success": True, "time": s1_time}
        print(f"  -> STATUS: SUCCESS (took {s1_time:.2f}s)")
        print(f"  -> Duration:        {metadata.duration:.2f}s")
        print(f"  -> Resolution:      {metadata.width}x{metadata.height}")
        print(f"  -> FPS:             {metadata.fps:.2f}")
        print(f"  -> Total Frames:    {metadata.frame_count}")
        print(f"  -> Codec:           {metadata.codec or 'Unknown'}")
        print(f"  -> Audio Stream:    {'Detected' if metadata.audio_available else 'Not detected'}")
    except Exception as exc:
        s1_time = time.perf_counter() - s1_start
        stage_results["1. Metadata Extraction"] = {"success": False, "time": s1_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # Create in-memory Video entity for internal processing services
    video_id = f"test_{uuid4().hex[:8]}"
    video_model = Video(
        id=video_id,
        filename=video_path.name,
        storage_path=str(video_path.resolve()),
        duration=metadata.duration,
        file_size=video_path.stat().st_size,
        width=metadata.width,
        height=metadata.height,
        fps=metadata.fps,
    )

    # -------------------------------------------------------------------------
    # Milestone 2: Frame Processing & Sampling
    # -------------------------------------------------------------------------
    print("\n[Stage 2/7] Sampling and Processing Frames (Milestone 2)...")
    s2_start = time.perf_counter()
    frame_artifacts: list[FrameArtifact] = []
    timestamped_frames: list[TimestampedFrame] = []
    try:
        frame_service = FrameProcessingService(
            storage=storage,
            interval_seconds=settings.frame_sampling_interval_seconds,
            image_format=settings.frame_image_format,
            quality=settings.frame_image_quality,
        )
        frame_artifacts = frame_service.extract(video_model)
        timestamped_frames = [
            TimestampedFrame(
                frame_id=fa.frame_id,
                timestamp=fa.timestamp,
                storage_path=str(fa.storage_path.resolve()),
            )
            for fa in frame_artifacts
        ]
        s2_time = time.perf_counter() - s2_start
        stage_results["2. Frame Processing"] = {"success": True, "time": s2_time}
        print(f"  -> STATUS: SUCCESS (took {s2_time:.2f}s)")
        print(f"  -> Extracted Frames: {len(timestamped_frames)}")
        if timestamped_frames:
            print(f"  -> First Frame:     ID={timestamped_frames[0].frame_id}, t={timestamped_frames[0].timestamp:.2f}s")
            mid = len(timestamped_frames) // 2
            print(f"  -> Middle Frame:    ID={timestamped_frames[mid].frame_id}, t={timestamped_frames[mid].timestamp:.2f}s")
            print(f"  -> Last Frame:      ID={timestamped_frames[-1].frame_id}, t={timestamped_frames[-1].timestamp:.2f}s")
            print(f"  -> Storage Path:    {Path(timestamped_frames[0].storage_path).parent}")
    except Exception as exc:
        s2_time = time.perf_counter() - s2_start
        stage_results["2. Frame Processing"] = {"success": False, "time": s2_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # -------------------------------------------------------------------------
    # Milestone 3: Audio Extraction
    # -------------------------------------------------------------------------
    print("\n[Stage 3/7] Extracting Audio Track (Milestone 3)...")
    s3_start = time.perf_counter()
    audio_artifact: AudioArtifact | None = None
    try:
        audio_service = AudioProcessingService(
            storage=storage,
            output_format=settings.audio_output_format,
        )
        audio_artifact = audio_service.extract(video_model)
        s3_time = time.perf_counter() - s3_start
        stage_results["3. Audio Extraction"] = {"success": True, "time": s3_time}
        print(f"  -> STATUS: SUCCESS (took {s3_time:.2f}s)")
        print(f"  -> Audio Available: {audio_artifact.audio_available}")
        if audio_artifact.audio_available and audio_artifact.storage_path:
            print(f"  -> Output Format:   {audio_artifact.format}")
            print(f"  -> Audio Duration:  {audio_artifact.duration:.2f}s" if audio_artifact.duration else "  -> Audio Duration:  N/A")
            print(f"  -> Artifact Path:   {audio_artifact.storage_path.resolve()}")
        else:
            print("  -> Notice:          No audio stream present in this video.")
            warnings.append("Video has no audio stream; transcription and text moderation received empty inputs.")
    except Exception as exc:
        s3_time = time.perf_counter() - s3_start
        stage_results["3. Audio Extraction"] = {"success": False, "time": s3_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # -------------------------------------------------------------------------
    # Milestone 4: YOLO VisionAnalyzer
    # -------------------------------------------------------------------------
    print("\n[Stage 4/7] Running YOLO VisionAnalyzer (Milestone 4)...")
    s4_start = time.perf_counter()
    detections: list[VisualDetection] = []
    try:
        vision_analyzer = get_vision_analyzer(settings)
        detections = vision_analyzer.analyze(timestamped_frames)
        s4_time = time.perf_counter() - s4_start
        stage_results["4. Vision Analysis (YOLO)"] = {"success": True, "time": s4_time}
        print(f"  -> STATUS: SUCCESS (took {s4_time:.2f}s)")
        print(f"  -> Total Detections: {len(detections)}")

        # Group and summarize detections by timestamp / category
        categories_found = sorted(list({d.category for d in detections}))
        print(f"  -> Detected Classes: {', '.join(categories_found) if categories_found else 'None'}")
        print("  -> Sample Detections with Timestamps & Evidence References:")
        for idx, d in enumerate(detections[:10]):
            box = d.metadata.get("box", "N/A")
            print(f"     [{idx+1:02d}] t={d.timestamp:4.1f}s | Category: {d.category:<12} | Conf: {d.confidence:.2f} | Evidence: {d.evidence_reference} | Box: {box}")
        if len(detections) > 10:
            print(f"     ... and {len(detections) - 10} more detections.")
    except Exception as exc:
        s4_time = time.perf_counter() - s4_start
        stage_results["4. Vision Analysis (YOLO)"] = {"success": False, "time": s4_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # -------------------------------------------------------------------------
    # Milestone 5: Whisper Transcriber
    # -------------------------------------------------------------------------
    print("\n[Stage 5/7] Running Whisper Transcriber (Milestone 5)...")
    s5_start = time.perf_counter()
    transcript_segments: list[TranscriptSegment] = []
    try:
        transcriber = get_transcriber(settings)
        transcript_segments = transcriber.transcribe(audio_artifact)
        s5_time = time.perf_counter() - s5_start
        stage_results["5. Transcription (Whisper)"] = {"success": True, "time": s5_time}
        print(f"  -> STATUS: SUCCESS (took {s5_time:.2f}s)")
        print(f"  -> Transcript Segments: {len(transcript_segments)}")
        if transcript_segments:
            for idx, seg in enumerate(transcript_segments):
                print(f"     [seg_{idx:02d}] [{seg.start:4.1f}s - {seg.end:4.1f}s] \"{seg.text}\"")
        else:
            print("  -> Spoken Dialogue:  (None / Silent)")
    except Exception as exc:
        s5_time = time.perf_counter() - s5_start
        stage_results["5. Transcription (Whisper)"] = {"success": False, "time": s5_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # -------------------------------------------------------------------------
    # Milestone 6: Transformer TextModerator
    # -------------------------------------------------------------------------
    print("\n[Stage 6/7] Running Transformer TextModerator (Milestone 6)...")
    s6_start = time.perf_counter()
    text_signals: list[TextModerationSignal] = []
    try:
        text_moderator = get_text_moderator(settings)
        text_signals = text_moderator.moderate(transcript_segments)
        s6_time = time.perf_counter() - s6_start
        stage_results["6. Text Moderation (Transformer)"] = {"success": True, "time": s6_time}
        print(f"  -> STATUS: SUCCESS (took {s6_time:.2f}s)")
        print(f"  -> Policy Signals Flagged: {len(text_signals)}")
        if text_signals:
            for idx, sig in enumerate(text_signals):
                print(f"     [sig_{idx:02d}] [{sig.start_timestamp:4.1f}s - {sig.end_timestamp:4.1f}s] Category: {sig.category} | Conf: {sig.confidence:.2f} | Text: \"{sig.source_text}\"")
        else:
            print("  -> Policy Signals:  None (No harmful/toxic speech detected)")
    except Exception as exc:
        s6_time = time.perf_counter() - s6_start
        stage_results["6. Text Moderation (Transformer)"] = {"success": False, "time": s6_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    # -------------------------------------------------------------------------
    # Milestone 7: Qwen 2.5 VL ContextAnalyzer
    # -------------------------------------------------------------------------
    print("\n[Stage 7/7] Running Qwen 2.5 VL Multimodal ContextAnalyzer (Milestone 7)...")
    s7_start = time.perf_counter()
    interpretation: ContextualInterpretation | None = None
    try:
        context_analyzer = get_context_analyzer(settings)
        interpretation = context_analyzer.analyze(
            detections=detections,
            transcripts=transcript_segments,
            signals=text_signals,
            frames=timestamped_frames,
        )
        s7_time = time.perf_counter() - s7_start
        stage_results["7. Context Analysis (Qwen 2.5 VL)"] = {"success": True, "time": s7_time}
        print(f"  -> STATUS: SUCCESS (took {s7_time:.2f}s)")
        print("\n" + "-" * 50)
        print("QWEN 2.5 VL CONTEXTUAL INTERPRETATION:")
        print("-" * 50)
        print(f"  Category:            {interpretation.category}")
        print(f"  Confidence:          {interpretation.confidence:.2f}")
        print(f"  Reasoning:           {interpretation.reasoning}")
        print(f"  Evidence References: {list(interpretation.evidence_references)}")
        print("-" * 50)
    except Exception as exc:
        s7_time = time.perf_counter() - s7_start
        stage_results["7. Context Analysis (Qwen 2.5 VL)"] = {"success": False, "time": s7_time}
        print(f"  -> STATUS: FAILED ({exc})")
        return False

    total_time = time.perf_counter() - overall_start_time

    # -------------------------------------------------------------------------
    # Final Pipeline Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PIPELINE EXECUTION SUMMARY (M1 - M7):")
    print("=" * 70)
    all_succeeded = all(bool(res.get("success")) for res in stage_results.values())

    for stage_name, res in stage_results.items():
        status_str = "PASS" if res.get("success") else "FAIL"
        time_str = f"{res.get('time', 0.0):.2f}s"
        print(f"  * {stage_name:<36} [{status_str}] ({time_str})")

    print("-" * 70)
    print(f"  Total Pipeline Execution Time: {total_time:.2f}s")
    print(f"  All Stages Succeeded:          {'YES' if all_succeeded else 'NO'}")
    if warnings:
        print("\n  Warnings encountered:")
        for w in warnings:
            print(f"    - {w}")
    print(f"  End-to-End M1-M7 Integration:  {'CONFIRMED OPERATIONAL' if all_succeeded else 'INCOMPLETE'}")
    print("=" * 70)

    return all_succeeded


def main() -> None:
    parser = argparse.ArgumentParser(description="Test M1-M7 Video Moderation Pipeline end-to-end.")
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
