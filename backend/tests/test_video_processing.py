"""Tests for internal frame, audio, and orchestration services."""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.db.models import Video
from app.services.video.processing import AudioProcessingService, FrameProcessingService, ProcessingError, VideoProcessingOrchestrator
from app.services.video.storage import LocalStorageService


def video(tmp_path: Path) -> Video:
    path = tmp_path / "tiny.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (16, 16))
    for _ in range(20): writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.release()
    return Video(id="vid_test", filename="tiny.avi", storage_path=str(path), duration=2, file_size=1, width=16, height=16, fps=10)


def test_frame_sampling_writes_timestamped_artifacts(tmp_path: Path) -> None:
    artifacts = FrameProcessingService(LocalStorageService(tmp_path / "artifacts"), interval_seconds=0.5).extract(video(tmp_path))
    assert len(artifacts) == 4
    assert all(item.timestamp >= 0 and item.storage_path.exists() for item in artifacts)


def test_audio_no_track_and_orchestrator_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stored = LocalStorageService(tmp_path / "artifacts")
    source = video(tmp_path)
    monkeypatch.setattr("app.services.video.processing.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"streams": []}'))
    assert AudioProcessingService(stored).extract(source).audio_available is False
    orchestrator = VideoProcessingOrchestrator(FrameProcessingService(stored), AudioProcessingService(stored))
    monkeypatch.setattr(orchestrator.audio, "extract", lambda _v: (_ for _ in ()).throw(ProcessingError("fail")))
    with pytest.raises(ProcessingError): orchestrator.process(source)
    assert not list((stored.root_path / "frames" / source.id).glob("*"))
