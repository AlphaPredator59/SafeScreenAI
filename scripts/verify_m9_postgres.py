"""Verify PostgreSQL records and API endpoints for Milestone 9."""

from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.db.database import get_session_factory
from app.db.models import Detection, Evidence, ModerationResult, TranscriptSegment, Video
from app.main import app


def verify():
    factory = get_session_factory()
    with factory() as session:
        videos = session.query(Video).all()
        print("=" * 60)
        print(f"POSTGRESQL PERSISTED VIDEOS ({len(videos)} found):")
        print("=" * 60)
        for v in videos:
            print(f"  - Video ID:   {v.id}")
            print(f"    Filename:   {v.filename}")
            print(f"    Status:     {v.status.value}")
            print(f"    Duration:   {v.duration:.2f}s")
            results = session.query(ModerationResult).filter_by(video_id=v.id).all()
            print(f"    Moderation Results: {len(results)}")
            for r in results:
                print(f"      Decision: {r.decision.value} | Risk: {r.risk_level.value} ({r.risk_score:.4f}) | Conf: {r.overall_confidence:.4f}")
                detections = session.query(Detection).filter_by(moderation_result_id=r.id).all()
                print(f"      Policy Findings: {len(detections)}")
                for d in detections:
                    print(f"        Category: {d.category} | Conf: {d.confidence:.2f} | Evidence items: {len(d.evidence_items)}")
            transcripts = session.query(TranscriptSegment).filter_by(video_id=v.id).all()
            print(f"    Transcript Segments: {len(transcripts)}")

    print("\n" + "=" * 60)
    print("FASTAPI TEST CLIENT ENDPOINTS VERIFICATION:")
    print("=" * 60)
    client = TestClient(app)

    for vid in ["test_cooking", "test_slap"]:
        # 1. Moderation report endpoint
        mod_resp = client.get(f"/api/v1/videos/{vid}/moderation")
        print(f"  [GET /api/v1/videos/{vid}/moderation] -> HTTP {mod_resp.status_code}")
        if mod_resp.status_code == 200:
            data = mod_resp.json()
            print(f"    Decision: {data['decision']} | Risk: {data['risk_level']} ({data['risk_score']})")
            print(f"    Findings: {len(data['findings'])} | Evidence: {len(data['evidence'])} | Transcripts: {len(data['transcripts'])}")

        # 2. Evidence list endpoint
        ev_resp = client.get(f"/api/v1/videos/{vid}/evidence")
        print(f"  [GET /api/v1/videos/{vid}/evidence] -> HTTP {ev_resp.status_code}")
        if ev_resp.status_code == 200:
            data = ev_resp.json()
            print(f"    Total Count: {data['total_count']} items")

    # Test non-existent video
    missing_resp = client.get("/api/v1/videos/non_existent_id/moderation")
    print(f"  [GET /api/v1/videos/non_existent_id/moderation] -> HTTP {missing_resp.status_code} ({missing_resp.json()['detail']})")
    print("=" * 60)


if __name__ == "__main__":
    verify()
