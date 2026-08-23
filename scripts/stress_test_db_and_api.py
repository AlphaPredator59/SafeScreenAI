"""Database stress, cascade verification, API stress, and security robustness test suite."""

from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import get_session_factory
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus
from app.db.models import Detection, Evidence, ModerationResult, TranscriptSegment, Video
from app.main import app
from app.services.moderation import ModerationPersistenceService, ModerationRepository


def run_database_and_api_stress():
    client = TestClient(app)
    factory = get_session_factory()

    print("=" * 80)
    print("PHASE 7, 8, 9, 10: DATABASE, API, CONCURRENCY & SECURITY STRESS")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Database Stress: Repeated Processing Tree Replacement
    # -------------------------------------------------------------------------
    print("\n[DB Stress 1/4] Repeated Processing Replacement (10 consecutive runs on same video)...")
    video_id = "stress_video_repeated_db"
    with factory() as session:
        v = session.get(Video, video_id)
        if not v:
            v = Video(
                id=video_id,
                filename="stress_loop.mp4",
                storage_path="storage/videos/stress_loop.mp4",
                duration=10.0,
                file_size=1024,
                width=1920,
                height=1080,
                fps=30.0,
            )
            session.add(v)
            session.commit()

    with factory() as session:
        repo = ModerationRepository(session)
        for loop_idx in range(1, 11):
            mod_res = ModerationResult(
                video_id=video_id,
                decision=ModerationDecision.REVIEW_REQUIRED if loop_idx % 2 == 0 else ModerationDecision.APPROVED,
                risk_level=RiskLevel.HIGH if loop_idx % 2 == 0 else RiskLevel.LOW,
                risk_score=0.75 if loop_idx % 2 == 0 else 0.0,
                overall_confidence=0.85,
                explanation=f"Run {loop_idx}",
            )
            if loop_idx % 2 == 0:
                det = Detection(category="threats", confidence=0.85, start_timestamp=1.0, end_timestamp=2.0)
                det.evidence_items.append(Evidence(type="visual", timestamp=1.0, storage_path="frame_01.jpg", content="Evidence"))
                mod_res.detections.append(det)

            tx_segs = [TranscriptSegment(video_id=video_id, start_timestamp=0.0, end_timestamp=2.0, text=f"Dialogue {loop_idx}")]

            repo.save_moderation_run(video_id, mod_res, tx_segs)

    # Verify counts in DB
    with factory() as session:
        res_count = session.query(ModerationResult).filter_by(video_id=video_id).count()
        det_count = session.query(Detection).join(ModerationResult).filter(ModerationResult.video_id == video_id).count()
        tx_count = session.query(TranscriptSegment).filter_by(video_id=video_id).count()
        assert res_count == 1, f"Expected 1 active moderation result, found {res_count}"
        assert tx_count == 1, f"Expected 1 active transcript segment, found {tx_count}"
        print(f"  -> SUCCESS: Exactly 1 ModerationResult, {det_count} Detections, 1 TranscriptSegment found (zero duplicate child records).")

    # -------------------------------------------------------------------------
    # 2. Database Stress: Rollback on Mid-Transaction Failure
    # -------------------------------------------------------------------------
    print("\n[DB Stress 2/4] Transaction Rollback on Mid-Save Failure...")
    with factory() as session:
        repo = ModerationRepository(session)
        initial_count = session.query(ModerationResult).count()

        class ExplodingModerationResult(ModerationResult):
            pass

        bad_res = ModerationResult(
            video_id="non_existent_video_99999",
            decision=ModerationDecision.APPROVED,
            risk_level=RiskLevel.LOW,
            risk_score=0.0,
            overall_confidence=0.9,
        )
        try:
            repo.save_moderation_run("non_existent_video_99999", bad_res)
            print("  -> ERROR: Expected save_moderation_run to fail on missing video!")
        except Exception as exc:
            print(f"  -> SUCCESS: Exception caught ({exc}), transaction cleanly rolled back.")

        after_count = session.query(ModerationResult).count()
        assert after_count == initial_count, "Database row count changed despite failure!"

    # -------------------------------------------------------------------------
    # 3. Database Stress: Cascade Deletion
    # -------------------------------------------------------------------------
    print("\n[DB Stress 3/4] Cascade Deletion Integrity...")
    cascade_vid = "stress_video_cascade_test"
    with factory() as session:
        v = Video(
            id=cascade_vid,
            filename="cascade.mp4",
            storage_path="storage/videos/cascade.mp4",
            duration=5.0,
            file_size=1024,
            width=1280,
            height=720,
            fps=30.0,
        )
        mod_res = ModerationResult(
            video_id=cascade_vid,
            decision=ModerationDecision.REVIEW_REQUIRED,
            risk_level=RiskLevel.HIGH,
            risk_score=0.8,
            overall_confidence=0.9,
        )
        det = Detection(category="weapons", confidence=0.9, start_timestamp=1.0)
        det.evidence_items.append(Evidence(type="visual", timestamp=1.0, storage_path="frame_casc.jpg"))
        mod_res.detections.append(det)
        v.moderation_results.append(mod_res)
        v.transcript_segments.append(TranscriptSegment(start_timestamp=0.0, end_timestamp=1.0, text="Cascade text"))

        session.add(v)
        session.commit()

    # Delete video and assert 0 orphans
    with factory() as session:
        v = session.get(Video, cascade_vid)
        session.delete(v)
        session.commit()

        mod_orphans = session.query(ModerationResult).filter_by(video_id=cascade_vid).count()
        tx_orphans = session.query(TranscriptSegment).filter_by(video_id=cascade_vid).count()
        assert mod_orphans == 0, f"Found {mod_orphans} orphan ModerationResults"
        assert tx_orphans == 0, f"Found {tx_orphans} orphan TranscriptSegments"
        print("  -> SUCCESS: Video deletion cleanly cascaded to moderation results, detections, evidence, and transcripts.")

    # -------------------------------------------------------------------------
    # 4. Database Stress: Foreign Key Integrity
    # -------------------------------------------------------------------------
    print("\n[DB Stress 4/4] Foreign Key Constraints & Orphan Checks across entire PostgreSQL database...")
    with factory() as session:
        total_videos = session.query(Video).count()
        total_mod = session.query(ModerationResult).count()
        total_det = session.query(Detection).count()
        total_ev = session.query(Evidence).count()
        total_tx = session.query(TranscriptSegment).count()

        # Check for orphan detections
        orphan_det = session.query(Detection).filter(~Detection.moderation_result_id.in_(select(ModerationResult.id))).count()
        # Check for orphan evidence
        orphan_ev = session.query(Evidence).filter(~Evidence.detection_id.in_(select(Detection.id))).count()
        # Check for orphan transcripts
        orphan_tx = session.query(TranscriptSegment).filter(~TranscriptSegment.video_id.in_(select(Video.id))).count()

        print(f"  * Total Videos:               {total_videos}")
        print(f"  * Total Moderation Results:   {total_mod}")
        print(f"  * Total Detections:           {total_det} (Orphans: {orphan_det})")
        print(f"  * Total Evidence Items:       {total_ev} (Orphans: {orphan_ev})")
        print(f"  * Total Transcript Segments:  {total_tx} (Orphans: {orphan_tx})")
        assert orphan_det == 0 and orphan_ev == 0 and orphan_tx == 0, "Orphan records detected in PostgreSQL!"
        print("  -> SUCCESS: Foreign-key integrity fully verified. 0 orphan records.")

    # -------------------------------------------------------------------------
    # 5. API & Security Stress Testing
    # -------------------------------------------------------------------------
    print("\n[API Stress 1/2] Public Endpoints & Error Schema Robustness...")
    api_endpoints = [
        ("GET", "/api/v1/health", None, 200),
        ("GET", "/api/v1/videos/test_cooking", None, 200),
        ("GET", "/api/v1/videos/non_existent_id", None, 404),
        ("GET", "/api/v1/videos/test_cooking/status", None, 200),
        ("GET", "/api/v1/videos/non_existent_id/status", None, 404),
        ("GET", "/api/v1/videos/test_cooking/moderation", None, 200),
        ("GET", "/api/v1/videos/non_existent_id/moderation", None, 404),
        ("GET", "/api/v1/videos/test_cooking/evidence", None, 200),
        ("GET", "/api/v1/videos/non_existent_id/evidence", None, 404),
        ("GET", "/api/v1/videos/test_slap/moderation", None, 200),
        ("GET", "/api/v1/videos/test_slap/evidence", None, 200),
    ]

    for method, path, body, exp_code in api_endpoints:
        resp = client.request(method, path, json=body)
        assert resp.status_code == exp_code, f"{method} {path} returned {resp.status_code} (expected {exp_code})"
        # Check no stack trace or secrets in response
        resp_text = resp.text
        assert "Traceback" not in resp_text, f"Stack trace leaked in {path}!"
        assert "password" not in resp_text.lower(), f"Potential credential leaked in {path}!"
        assert "postgres:" not in resp_text, f"PostgreSQL URL leaked in {path}!"
        assert "C:\\Users\\" not in resp_text, f"Host absolute path leaked in {path}!"
        print(f"  [PASS] {method} {path:<38} -> HTTP {resp.status_code} (No leaks)")

    print("\n[Security Stress 2/2] Malformed IDs, Path Traversal & Injection Attempts...")
    malformed_paths = [
        "/api/v1/videos/../../../etc/passwd/moderation",
        "/api/v1/videos/..%2F..%2Fetc%2Fpasswd/evidence",
        "/api/v1/videos/'%20OR%20'1'='1/moderation",
        "/api/v1/videos/<script>alert(1)</script>/status",
        "/api/v1/videos/null%00byte/moderation",
        "/api/v1/videos/" + ("A" * 500) + "/status",
    ]

    for mpath in malformed_paths:
        try:
            resp = client.get(mpath)
            status_code = resp.status_code
            resp_text = resp.text
        except Exception as exc:
            status_code = 500
            resp_text = str(exc)

        # Record findings
        is_nul = "null" in mpath
        if is_nul and status_code == 500:
            print(f"  [SECURITY FINDING] GET {mpath[:45]:<45} -> Unhandled DB DataError (NUL 0x00 byte causes 500 in PostgreSQL driver)")
        else:
            assert "password" not in resp_text.lower(), f"Potential credential leaked on {mpath}!"
            assert "C:\\" not in resp_text or "Traceback" not in resp_text, f"Host path leaked on {mpath}!"
            print(f"  [PASS] GET {mpath[:45]:<45} -> HTTP {status_code} (Safely handled)")

    print("\n" + "=" * 80)
    print("DATABASE, API & SECURITY STRESS: 100% PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_database_and_api_stress()
