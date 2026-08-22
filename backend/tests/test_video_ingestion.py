"""Focused tests for the existing video ingestion flow."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.videos import get_video_ingestion_service, get_video_repository
from app.db.models import Video
from app.main import app
from app.services.video.ingestion import VideoIngestionService
from app.services.video.metadata import MetadataExtractionError, VideoMetadata
from app.services.video.repository import VideoRepository
from app.services.video.storage import LocalStorageService


class FakeMetadata:
    def __init__(self, metadata: VideoMetadata | Exception) -> None:
        self.metadata = metadata

    def extract(self, _path: Path) -> VideoMetadata:
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata


def metadata(duration: float = 1.0) -> VideoMetadata:
    return VideoMetadata(duration, 16, 16, 24.0, 24, "mp4v", False)


@pytest.fixture
def client_and_storage(tmp_path: Path, db_session: Session):
    storage = LocalStorageService(tmp_path / "uploads")
    service = VideoIngestionService(db_session, storage, FakeMetadata(metadata()), 100, 10)
    app.dependency_overrides[get_video_ingestion_service] = lambda: service
    app.dependency_overrides[get_video_repository] = lambda: VideoRepository(db_session)
    with TestClient(app) as client:
        yield client, storage, service
    app.dependency_overrides.clear()


def post_video(client: TestClient, name: str = "tiny.mp4", content_type: str = "video/mp4", data: bytes = b"tiny"):
    return client.post("/api/v1/videos", files={"file": (name, data, content_type)})


def test_valid_upload_persists_video_and_exposes_status(client_and_storage, db_session: Session) -> None:
    client, storage, _ = client_and_storage
    response = post_video(client)
    assert response.status_code == 201
    video_id = response.json()["video_id"]
    video = db_session.get(Video, video_id)
    assert video is not None and video.status.value == "UPLOADED"
    assert Path(video.storage_path).exists()
    assert response.json()["status"] == "UPLOADED"

    details = client.get(f"/api/v1/videos/{video_id}")
    assert details.status_code == 200 and "storage_path" not in details.json()
    assert client.get(f"/api/v1/videos/{video_id}/status").json() == {"video_id": video_id, "status": "UPLOADED"}
    assert client.get("/api/v1/videos/missing").status_code == 404
    assert list(storage.root_path.iterdir())


@pytest.mark.parametrize(
    ("name", "content_type", "data", "expected"),
    [
        ("bad.txt", "text/plain", b"x", 415),
        ("tiny.mp4", "text/plain", b"x", 415),
        ("tiny.mp4", "video/mp4", b"x" * 101, 413),
    ],
)
def test_invalid_uploads_leave_no_records_or_files(client_and_storage, db_session: Session, name, content_type, data, expected) -> None:
    client, storage, _ = client_and_storage
    assert post_video(client, name, content_type, data).status_code == expected
    assert db_session.query(Video).count() == 0
    assert not storage.root_path.exists() or not list(storage.root_path.iterdir())


@pytest.mark.parametrize("failure", [MetadataExtractionError("corrupt"), metadata(11.0)])
def test_metadata_failures_and_duration_limit_clean_up(client_and_storage, db_session: Session, failure) -> None:
    client, storage, service = client_and_storage
    service.metadata = FakeMetadata(failure)
    assert post_video(client).status_code == 422
    assert db_session.query(Video).count() == 0
    assert not list(storage.root_path.iterdir())


def test_database_failure_cleans_stored_file(client_and_storage, monkeypatch: pytest.MonkeyPatch) -> None:
    client, storage, service = client_and_storage
    def fail_add(_video):
        raise SQLAlchemyError("database unavailable")
    monkeypatch.setattr(service.repository, "add", fail_add)
    assert post_video(client).status_code == 500
    assert not list(storage.root_path.iterdir())
