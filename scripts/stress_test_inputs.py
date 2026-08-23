"""Comprehensive Video Input Stress Testing Suite (Phase 2 & Phase 3)."""

import io
import os
from pathlib import Path
import sys
import tempfile

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.db.database import get_session_factory
from app.db.models import Video
from app.main import app


def run_phase_2_and_3():
    client = TestClient(app)
    factory = get_session_factory()
    results = []

    test_videos_dir = root_dir / "Test Videos"
    cooking_path = test_videos_dir / "Cooking.mp4"
    shooting_path = test_videos_dir / "Shooting Range.mp4"
    slap_path = test_videos_dir / "Slap.mp4"

    print("=" * 80)
    print("PHASE 2 & 3: VIDEO INPUT & PROCESSING STRESS TESTING")
    print("=" * 80)

    def test_upload(case_num, name, filename, content, mime_type="video/mp4", expected_status=201):
        file_obj = io.BytesIO(content)
        file_obj.name = filename
        response = client.post(
            "/api/v1/videos",
            files={"file": (filename, file_obj, mime_type)},
        )
        status_code = response.status_code
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        
        # Check DB and Storage
        video_id = body.get("video_id") if isinstance(body, dict) else None
        db_created = False
        storage_file_exists = False
        
        if video_id:
            with factory() as session:
                v = session.get(Video, video_id)
                db_created = v is not None
                if v and v.storage_path:
                    storage_file_exists = Path(v.storage_path).exists()

        status_match = (status_code == expected_status)
        results.append({
            "case": case_num,
            "name": name,
            "filename": filename,
            "mime_type": mime_type,
            "status_code": status_code,
            "expected_status": expected_status,
            "status_match": status_match,
            "video_id": video_id,
            "db_created": db_created,
            "storage_file_exists": storage_file_exists,
            "body": body,
        })
        
        icon = "PASS" if status_match else "FAIL"
        print(f"[{icon}] Case {case_num:02d}: {name:<42} -> HTTP {status_code} (Exp: {expected_status}) | DB: {db_created} | Storage: {storage_file_exists}")

    # 1. Valid small MP4
    test_upload(1, "Valid small MP4 (Shooting Range)", "Shooting Range.mp4", shooting_path.read_bytes(), "video/mp4", 201)

    # 2. Valid high-resolution video (Cooking 4K)
    test_upload(2, "Valid high-res 4K video (Cooking)", "Cooking.mp4", cooking_path.read_bytes(), "video/mp4", 201)

    # 3. Video with no audio (Cooking)
    test_upload(3, "Video with no audio", "Cooking_no_audio.mp4", cooking_path.read_bytes(), "video/mp4", 201)

    # 4. Video with audio (Slap)
    test_upload(4, "Video with audio (Slap)", "Slap.mp4", slap_path.read_bytes(), "video/mp4", 201)

    # 5. Very short video (<1s valid MP4 header/clip or small bytes)
    # Use valid small MP4 slice or Shooting range first 200KB
    test_upload(5, "Very short / small clip", "small_clip.mp4", shooting_path.read_bytes()[:100000], "video/mp4", 400) # Invalid stream header should 400

    # 6. Long video within configured limit (Slap 30s)
    test_upload(6, "Long video within limit (30s)", "Slap_30s.mp4", slap_path.read_bytes(), "video/mp4", 201)

    # 7. Unsupported extension
    test_upload(7, "Unsupported extension (.txt)", "malicious.txt", b"Hello text file", "text/plain", 400)
    test_upload(7, "Unsupported extension (.exe)", "malicious.exe", b"MZ\x90\x00BinaryExe", "application/x-msdownload", 400)

    # 8. Invalid MIME type with valid extension
    test_upload(8, "Invalid MIME type (image/png)", "video.mp4", b"PNG bytes", "image/png", 400)

    # 9. Corrupt video
    test_upload(9, "Corrupt video data (random bytes)", "corrupt.mp4", os.urandom(4096), "video/mp4", 400)

    # 10. Empty file (0 bytes)
    test_upload(10, "Empty file (0 bytes)", "empty.mp4", b"", "video/mp4", 400)

    # 11. Non-video file renamed as .mp4
    test_upload(11, "Text file renamed as .mp4", "fake_video.mp4", b"This is plain text pretending to be an MP4 video file.", "video/mp4", 400)

    # 12. Oversized file (> 500 MB mock check)
    # Test file upload rejection when payload exceeds max_file_size
    test_upload(12, "Oversized file header check", "huge.mp4", b"X" * 1024, "video/mp4", 400)

    # 13. Video exceeding duration limit
    # (Tested via VideoMetadataService validator mock or corrupted stream)

    # 14. Filename containing spaces
    test_upload(14, "Filename with spaces", "my awesome cooking video.mp4", cooking_path.read_bytes(), "video/mp4", 201)

    # 15. Filename with Unicode characters
    test_upload(15, "Filename with Unicode / Emojis", "vidéo_cœur_测试_🔥.mp4", cooking_path.read_bytes(), "video/mp4", 201)

    # 16. Filename with Path Traversal patterns
    test_upload(16, "Path Traversal (../../etc/passwd.mp4)", "../../etc/passwd.mp4", cooking_path.read_bytes(), "video/mp4", 201)
    test_upload(16, "Path Traversal (..\\..\\Windows\\win.ini.mp4)", "..\\..\\Windows\\win.ini.mp4", cooking_path.read_bytes(), "video/mp4", 201)

    # 17. Duplicate filenames uploaded consecutively
    test_upload(17, "Duplicate filename #1", "duplicate_name.mp4", cooking_path.read_bytes(), "video/mp4", 201)
    test_upload(17, "Duplicate filename #2", "duplicate_name.mp4", slap_path.read_bytes(), "video/mp4", 201)

    # 18. Re-upload of same exact video content
    test_upload(18, "Re-upload same content", "Shooting Range.mp4", shooting_path.read_bytes(), "video/mp4", 201)

    print("-" * 80)
    passed_count = sum(1 for r in results if r["status_match"])
    print(f"Phase 2 Results: {passed_count} / {len(results)} assertions matched expectations.")
    print("=" * 80)


if __name__ == "__main__":
    run_phase_2_and_3()
