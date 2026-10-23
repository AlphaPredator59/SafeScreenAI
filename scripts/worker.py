"""SafeScreen AI — Standalone PostgreSQL-backed Video Moderation Worker.

Architectural Concurrency Model & Assumptions:
----------------------------------------------
1. Database-backed queue with row-level transactional claims:
   - Pending videos have status `UPLOADED` (or `QUEUED`).
   - Claiming queries use:
       `SELECT ... WHERE status IN ('UPLOADED', 'QUEUED') ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1`
   - In PostgreSQL, `FOR UPDATE SKIP LOCKED` guarantees that:
       * Only one worker can acquire an exclusive row lock on any given video.
       * Concurrent workers skip locked rows immediately without blocking or waiting.
       * No two workers can ever claim or execute the same video concurrently.
2. Two-phase state transition:
   - Phase 1 (Claim): The claiming worker updates status to `PROCESSING` and commits immediately.
     The row lock is released, and the row is no longer eligible for claiming by any worker.
   - Phase 2 (Execution): The worker instantiates `PipelineRunner` which executes the multi-modal
     moderation pipeline (frames, audio, YOLO, Whisper, Toxic-BERT, Qwen 2.5-VL, ModerationEngine).
   - Phase 3 (Completion or Failure):
     * On success, `ModerationPersistenceService` atomically records the moderation findings and sets
       the video status to `COMPLETED`.
     * On unrecoverable error, the worker transitions the video status to `FAILED`, logs the error,
       and continues polling for subsequent videos without terminating the worker process.

Requirements & Constraints:
--------------------------
- No Celery, Redis, Kafka, or RabbitMQ required for this MVP.
- Clean isolation between worker process and FastAPI web server.
- Supports both AI_MODE=mock and AI_MODE=real.
- Safe graceful shutdown on SIGINT/SIGTERM.
"""

import argparse
import logging
import os
from pathlib import Path
import signal
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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_session_factory
from app.db.enums import VideoStatus
from app.db.models import Video
from app.services.moderation import (
    PipelineExecutionError,
    PipelineRunResult,
    PipelineRunner,
)

# Ensure unbuffered stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
logger = logging.getLogger("safescreen.worker")

# Global graceful shutdown flag
_stop_requested = False


def _signal_handler(signum: int, frame: Any) -> None:
    global _stop_requested
    logger.info("Shutdown signal received (%s). Finishing active jobs and exiting...", signum)
    _stop_requested = True


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def claim_next_video(session: Session) -> Video | None:
    """Transactionally claim one video waiting for moderation using FOR UPDATE SKIP LOCKED.

    Returns the claimed Video instance with its status committed as PROCESSING,
    or None if no pending videos are available.
    """
    stmt = (
        select(Video)
        .where(Video.status.in_([VideoStatus.UPLOADED, VideoStatus.QUEUED]))
        .order_by(Video.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    video = session.scalars(stmt).first()
    if video is None:
        session.rollback()
        return None

    video_id = video.id
    video.status = VideoStatus.PROCESSING
    session.commit()
    session.refresh(video)
    return video


def process_claimed_video(video_id: str, settings: Settings, session_factory: Any) -> bool:
    """Execute the full moderation pipeline for a claimed video.

    Guarantees:
      - Successful execution transitions video to COMPLETED.
      - Any failure transitions video to FAILED.
      - Worker process never crashes due to a video error.
    """
    start_time = time.perf_counter()
    logger.info("Processing claimed video: %s", video_id)

    with session_factory() as session:
        try:
            runner = PipelineRunner(session=session, settings=settings)
            result: PipelineRunResult = runner.run(video_id=video_id)
            total_duration = time.perf_counter() - start_time

            logger.info(
                "COMPLETED video '%s' in %.2fs | Decision: %s | Risk: %s (%.4f) | Confidence: %.4f | Categories: %s",
                video_id,
                total_duration,
                result.decision.value,
                result.risk_level.value,
                result.risk_score,
                result.overall_confidence,
                list(result.moderation_result.detected_categories),
            )
            return True

        except Exception as exc:
            total_duration = time.perf_counter() - start_time
            logger.error(
                "FAILED video '%s' after %.2fs [%s]: %s",
                video_id,
                total_duration,
                exc.__class__.__name__,
                str(exc),
            )

            # Ensure database status is marked as FAILED in an isolated transaction
            try:
                session.rollback()
                failed_video = session.get(Video, video_id)
                if failed_video and failed_video.status != VideoStatus.FAILED:
                    failed_video.status = VideoStatus.FAILED
                    session.commit()
                    logger.info("Successfully marked video '%s' as FAILED in database.", video_id)
            except Exception as db_exc:
                logger.error("Could not persist FAILED status for video '%s': %s", video_id, db_exc)
                try:
                    session.rollback()
                except Exception:
                    pass

            return False


def run_worker_loop(
    settings: Settings,
    poll_interval: float = 2.0,
    run_once: bool = False,
    single_video_id: str | None = None,
) -> None:
    """Continuously poll PostgreSQL for pending videos and execute moderation pipeline."""
    session_factory = get_session_factory()
    logger.info("SafeScreen Moderation Worker started.")
    logger.info("AI Mode:         %s", settings.ai_mode.upper())
    logger.info("AI Device:       %s", settings.ai_device.upper())
    logger.info("Poll Interval:   %.1fs", poll_interval)
    logger.info("Storage Path:    %s", settings.storage_path)

    # If single video requested directly
    if single_video_id:
        logger.info("Single video mode: Processing video '%s'", single_video_id)
        with session_factory() as session:
            v = session.get(Video, single_video_id)
            if not v:
                logger.error("Video '%s' not found.", single_video_id)
                return
            v.status = VideoStatus.PROCESSING
            session.commit()
        process_claimed_video(single_video_id, settings, session_factory)
        return

    logger.info("Listening for pending videos (UPLOADED / QUEUED)...")

    while not _stop_requested:
        claimed_id: str | None = None

        try:
            with session_factory() as session:
                claimed_video = claim_next_video(session)
                if claimed_video is not None:
                    claimed_id = claimed_video.id

            if claimed_id:
                process_claimed_video(claimed_id, settings, session_factory)
                # Immediately poll again without sleeping if there might be a queue backlog
                continue

            # Queue is currently empty
            if run_once:
                logger.info("Single pass complete (--once flag). Exiting.")
                break

            time.sleep(poll_interval)

        except Exception as loop_exc:
            logger.error("Error in worker polling loop: %s", loop_exc)
            if run_once:
                break
            time.sleep(poll_interval)

    logger.info("SafeScreen Moderation Worker stopped cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SafeScreen AI — Standalone PostgreSQL Moderation Worker")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds when idle (default: 2.0)")
    parser.add_argument("--ai-mode", default=None, choices=["real", "mock"], help="Override AI mode (default: from config)")
    parser.add_argument("--device", default=None, choices=["cpu", "cuda"], help="Override inference device (default: from config)")
    parser.add_argument("--once", action="store_true", help="Process all currently pending videos and exit")
    parser.add_argument("--video-id", default=None, help="Process a specific video ID directly and exit")
    args = parser.parse_args()

    base_settings = get_settings()
    updates: dict[str, Any] = {"storage_path": root_dir / "storage"}
    if args.ai_mode:
        updates["ai_mode"] = args.ai_mode
    if args.device:
        updates["ai_device"] = args.device

    custom_settings = base_settings.model_copy(update=updates)

    run_worker_loop(
        settings=custom_settings,
        poll_interval=args.poll_interval,
        run_once=args.once,
        single_video_id=args.video_id,
    )


if __name__ == "__main__":
    main()
