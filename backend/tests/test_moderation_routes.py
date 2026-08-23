"""Integration tests for moderation and evidence API endpoints."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Video
from app.main import app
from app.services.moderation import ModerationPersistenceService, ModerationRepository, ModerationResult
from app.services.moderation.contracts import EvidenceItem


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient overriding get_db_session with the test SQLite db_session."""
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_video_with_moderation(db_session: Session, video_id: str = "vid_api_001") -> Video:
    """Helper to seed a video with a complete moderation run."""
    video = Video(
        id=video_id,
        filename="slap_clip.mp4",
        storage_path="storage/videos/slap_clip.mp4",
        duration=15.0,
        file_size=2048 * 1024,
        width=1920,
        height=1080,
        fps=30.0,
        status=VideoStatus.PROCESSING,
    )
    db_session.add(video)
    db_session.commit()

    repo = ModerationRepository(db_session)
    persistence = ModerationPersistenceService(repo)

    result = ModerationResult(
        decision=ModerationDecision.REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        risk_score=0.765,
        overall_confidence=0.90,
        detected_categories=("threats",),
        supporting_evidence=(
            EvidenceItem(
                modality="context",
                category="threatening interaction",
                confidence=0.90,
                reference="frame_0002.jpg",
                timestamp=1.5,
                description="Threatening altercation",
            ),
        ),
        explanation="Threatening interaction detected.",
    )

    persistence.persist_moderation_run(video_id=video.id, result=result)
    return video


def test_get_moderation_report_endpoint_success(client: TestClient, db_session: Session) -> None:
    """GET /api/v1/videos/{video_id}/moderation returns 200 with structured report."""
    video = seed_video_with_moderation(db_session, "vid_api_report_success")

    response = client.get(f"/api/v1/videos/{video.id}/moderation")
    assert response.status_code == 200

    data = response.json()
    assert data["video_id"] == video.id
    assert data["filename"] == "slap_clip.mp4"
    assert data["decision"] == "REVIEW_REQUIRED"
    assert data["risk_level"] == "HIGH"
    assert data["risk_score"] == 0.765
    assert data["overall_confidence"] == 0.90
    assert data["detected_categories"] == ["threats"]
    assert len(data["findings"]) == 1
    assert data["findings"][0]["category"] == "threats"
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["type"] == "context"
    assert "Threatening interaction detected" in data["explanation"]


def test_get_moderation_report_missing_video_returns_404(client: TestClient) -> None:
    """GET /api/v1/videos/{video_id}/moderation returns 404 for unknown video."""
    response = client.get("/api/v1/videos/non_existent_vid/moderation")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found."


def test_get_moderation_report_video_exists_without_moderation_returns_404(client: TestClient, db_session: Session) -> None:
    """GET /api/v1/videos/{video_id}/moderation returns 404 when video exists but moderation hasn't completed."""
    video = Video(
        id="vid_unmoderated",
        filename="raw.mp4",
        storage_path="storage/raw.mp4",
        duration=5.0,
        file_size=1000,
        width=1280,
        height=720,
        fps=25.0,
        status=VideoStatus.UPLOADED,
    )
    db_session.add(video)
    db_session.commit()

    response = client.get(f"/api/v1/videos/{video.id}/moderation")
    assert response.status_code == 404
    assert response.json()["detail"] == "Moderation report not found for this video."


def test_get_evidence_endpoint_success(client: TestClient, db_session: Session) -> None:
    """GET /api/v1/videos/{video_id}/evidence returns 200 with evidence items."""
    video = seed_video_with_moderation(db_session, "vid_api_evidence_success")

    response = client.get(f"/api/v1/videos/{video.id}/evidence")
    assert response.status_code == 200

    data = response.json()
    assert data["video_id"] == video.id
    assert data["total_count"] == 1
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["type"] == "context"
    assert data["evidence"][0]["reference"] == "frame_0002.jpg"


def test_get_evidence_endpoint_zero_evidence_returns_200_empty_list(client: TestClient, db_session: Session) -> None:
    """GET /api/v1/videos/{video_id}/evidence returns 200 with empty list for video with no policy evidence."""
    video = Video(
        id="vid_zero_ev",
        filename="empty.mp4",
        storage_path="storage/empty.mp4",
        duration=5.0,
        file_size=1000,
        width=1280,
        height=720,
        fps=25.0,
        status=VideoStatus.COMPLETED,
    )
    db_session.add(video)
    db_session.commit()

    response = client.get(f"/api/v1/videos/{video.id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == video.id
    assert data["total_count"] == 0
    assert data["evidence"] == []


def test_get_evidence_endpoint_missing_video_returns_404(client: TestClient) -> None:
    """GET /api/v1/videos/{video_id}/evidence returns 404 for non-existent video."""
    response = client.get("/api/v1/videos/non_existent_vid/evidence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found."


def test_video_id_validation_rejects_nul_byte(client: TestClient) -> None:
    """Malformed video IDs containing NUL bytes return HTTP 400 Bad Request."""
    for endpoint_suffix in ["", "/status", "/moderation", "/evidence"]:
        response = client.get(f"/api/v1/videos/null%00byte{endpoint_suffix}")
        assert response.status_code == 400
        assert "Invalid video ID format" in response.json()["detail"]


def test_video_id_validation_rejects_spaces(client: TestClient) -> None:
    """Malformed video IDs containing spaces return HTTP 400 Bad Request."""
    for endpoint_suffix in ["", "/status", "/moderation", "/evidence"]:
        response = client.get(f"/api/v1/videos/invalid%20id%20with%20spaces{endpoint_suffix}")
        assert response.status_code == 400
        assert "Invalid video ID format" in response.json()["detail"]


def test_video_id_validation_rejects_path_traversal(client: TestClient) -> None:
    """Malformed video IDs containing invalid characters (dots, special chars, traversal patterns) return HTTP 400 Bad Request."""
    invalid_ids = ["invalid..id", "invalid.path", "inv@lid", "invalid$id", "invalid!id", "invalid*id"]
    for inv_id in invalid_ids:
        for endpoint_suffix in ["", "/status", "/moderation", "/evidence"]:
            response = client.get(f"/api/v1/videos/{inv_id}{endpoint_suffix}")
            assert response.status_code == 400
            assert "Invalid video ID format" in response.json()["detail"]


def test_video_id_validation_accepts_valid_id_and_returns_404_for_unknown(client: TestClient) -> None:
    """Syntactically valid video IDs pass validation and return HTTP 404 if not found."""
    valid_unknown_id = "valid-video_id-12345"
    for endpoint_suffix in ["", "/status", "/moderation", "/evidence"]:
        response = client.get(f"/api/v1/videos/{valid_unknown_id}{endpoint_suffix}")
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]
