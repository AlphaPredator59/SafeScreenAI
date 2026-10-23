"""Tests for the PostgreSQL-backed worker claiming and processing mechanisms."""

from pathlib import Path
import sys
from uuid import uuid4

# Ensure root directory is in sys.path for importing scripts
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.database import get_session_factory
from app.db.enums import VideoStatus
from app.db.models import Video
from scripts.worker import claim_next_video, process_claimed_video


from datetime import datetime, timezone

def test_claim_next_video_success():
    """Verify that claim_next_video claims an UPLOADED video and marks it as PROCESSING."""
    session_factory = get_session_factory()
    with session_factory() as session:
        vid_id = f"worker_test_{uuid4().hex[:8]}"
        video = Video(
            id=vid_id,
            filename="sample.mp4",
            storage_path="sample.mp4",
            duration=1.0,
            file_size=500,
            width=640,
            height=360,
            fps=25.0,
            status=VideoStatus.UPLOADED,
            created_at=datetime(1990, 1, 1, tzinfo=timezone.utc),
        )
        session.add(video)
        session.commit()

        # Claim the video
        claimed = claim_next_video(session)
        assert claimed is not None
        assert claimed.id == vid_id
        assert claimed.status == VideoStatus.PROCESSING

        # A subsequent claim should not return the same video
        next_claimed = claim_next_video(session)
        if next_claimed:
            assert next_claimed.id != vid_id


def test_process_claimed_video_failure_recovery(tmp_path: Path):
    """Verify that a video that cannot be processed fails safely to FAILED status without crashing."""
    session_factory = get_session_factory()
    with session_factory() as session:
        vid_id = f"fail_test_{uuid4().hex[:8]}"
        video = Video(
            id=vid_id,
            filename="corrupted.mp4",
            storage_path=str(tmp_path / "does_not_exist.mp4"),
            duration=1.0,
            file_size=500,
            width=640,
            height=360,
            fps=25.0,
            status=VideoStatus.PROCESSING,
        )
        session.add(video)
        session.commit()

        settings = Settings(
            ai_mode="mock",
            ai_device="cpu",
            storage_path=tmp_path / "storage",
        )

        # Execute worker processing
        success = process_claimed_video(vid_id, settings, session_factory)
        assert success is False

        # Verify database status is FAILED
        updated = session.get(Video, vid_id)
        assert updated is not None
        assert updated.status == VideoStatus.FAILED
