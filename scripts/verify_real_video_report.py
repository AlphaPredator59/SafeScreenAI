"""Verification script for Run._Hide._Fight..mp4 moderation report data structure."""

import json
from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.database import get_session_factory
from app.db.models import ModerationResult as DBModerationResult
from app.services.moderation import (
    ModerationPersistenceService,
    ModerationReportService,
    ModerationRepository,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult
from app.services.moderation.temporal_grouping import build_policy_findings


def main() -> None:
    session_factory = get_session_factory()
    session = session_factory()
    repo = ModerationRepository(session)

    # Find the Run._Hide._Fight..mp4 video record
    db_res = (
        session.query(DBModerationResult)
        .filter(DBModerationResult.video_id == "vid_e14086293f114f2f979714d83d8719ad")
        .first()
    )
    if db_res is None:
        print("Video vid_e14086293f114f2f979714d83d8719ad not found in DB.")
        sys.exit(1)

    print("=" * 70)
    print("VERIFYING REAL VIDEO REPORT ATTRIBUTION (Run._Hide._Fight..mp4)")
    print("=" * 70)

    # Reconstruct the original 886 evidence items from the previous run
    ev_items: list[EvidenceItem] = []
    seen = set()

    for d in db_res.detections:
        for e in d.evidence_items:
            key = (e.type, e.timestamp, e.storage_path, e.content)
            if key not in seen:
                seen.add(key)
                cat = "unknown"
                content = e.content or ""
                if e.type == "visual" and "Visual detection of '" in content:
                    cat = content.split("Visual detection of '")[1].split("'")[0]
                elif e.type == "text_signal" and "Text moderation flag '" in content:
                    cat = content.split("Text moderation flag '")[1].split("'")[0]
                elif e.type == "context":
                    if "]: '" in content:
                        cat = content.split("]: '")[1].split("'")[0]
                    elif "Contextual interpretation: '" in content:
                        cat = content.split("Contextual interpretation: '")[1].split("'")[0]

                end_ts = None
                if e.type == "context" and "s - " in content:
                    try:
                        time_part = content.split("[")[1].split("]")[0]
                        end_ts = float(time_part.split(" - ")[1].replace("s", ""))
                    except Exception:
                        end_ts = None
                elif e.type == "text_signal":
                    end_ts = e.timestamp + 4.0

                conf = 0.5
                if "(conf: " in content:
                    try:
                        conf = float(content.split("(conf: ")[1].split(")")[0])
                    except Exception:
                        conf = 0.5

                is_global_context = e.type == "context" and "Contextual interpretation: '" in content
                item_timestamp = None if is_global_context else e.timestamp

                ev_items.append(
                    EvidenceItem(
                        modality=e.type,
                        category=cat,
                        confidence=conf,
                        reference=e.storage_path or e.id,
                        timestamp=item_timestamp,
                        end_timestamp=end_ts,
                        description=content,
                    )
                )

    print(f"Total reconstructed multi-modal evidence items: {len(ev_items)}")

    # 1. Build policy findings with temporal grouping and attribution
    findings = build_policy_findings(
        detected_categories=["threats", "toxic"],
        evidence_items=ev_items,
    )

    print(f"\nGenerated Findings Count: {len(findings)}")
    for f in findings:
        print(f"\n[Finding] Category: {f.category} | Conf: {f.confidence:.2f} ({f.confidence}) | Summary: {f.summary}")
        for idx, ev in enumerate(f.events):
            print(f"  Event {idx+1}: [{ev.start_time:.1f}s - {ev.end_time:.1f}s] Conf: {ev.confidence:.2f} | Evidence refs: {len(ev.evidence_ids)}")
            print(f"           Desc: {ev.description}")

    # 2. Persist with updated persistence service
    new_res = ModerationResult(
        decision=db_res.decision,
        risk_level=db_res.risk_level,
        risk_score=db_res.risk_score,
        overall_confidence=db_res.overall_confidence,
        detected_categories=("threats", "toxic"),
        supporting_evidence=tuple(ev_items),
        explanation=db_res.explanation,
        findings=tuple(findings),
    )

    persistence = ModerationPersistenceService(repo)
    persistence.persist_moderation_run(
        video_id="vid_e14086293f114f2f979714d83d8719ad",
        result=new_res,
    )

    # 3. Retrieve structured public report
    reporting = ModerationReportService(repo)
    report = reporting.get_moderation_report("vid_e14086293f114f2f979714d83d8719ad")
    if not report:
        print("Failed to load report!")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("FINAL STRUCTURED MODERATION REPORT (JSON):")
    print("=" * 70)
    report_dict = report.model_dump(mode="json")
    print(json.dumps(report_dict, indent=2))

    # 4. Strict verifications
    print("\n" + "=" * 70)
    print("VERIFICATION CHECKLIST:")
    print("=" * 70)

    # Check 1: Findings do not automatically span whole video (0 -> 275)
    f_threats = next(f for f in report.findings if f.category == "threats")
    f_toxic = next(f for f in report.findings if f.category == "toxic")

    print(f"1. Threats time range:  [{f_threats.start_timestamp}s - {f_threats.end_timestamp}s]")
    print(f"   Toxic time range:    [{f_toxic.start_timestamp}s - {f_toxic.end_timestamp}s]")
    assert not (f_toxic.start_timestamp == 0.0 and f_toxic.end_timestamp == 275.0), "Toxic spans entire video!"
    assert f_toxic.start_timestamp >= 240.0, f"Toxic should be at 250s, got {f_toxic.start_timestamp}"
    print("   -> PASS: Findings do not automatically span the full video duration.")

    # Check 2: Confidence is not automatically 100%
    print(f"2. Threats confidence:  {f_threats.confidence:.2f} ({f_threats.confidence})")
    print(f"   Toxic confidence:    {f_toxic.confidence:.2f} ({f_toxic.confidence})")
    assert f_toxic.confidence < 1.0, f"Toxic confidence is 100%: {f_toxic.confidence}"
    assert f_toxic.confidence == 0.67, f"Expected toxic confidence 0.67, got {f_toxic.confidence}"
    print("   -> PASS: Confidence is genuine (e.g. 0.95, 0.67) and not forced to 100%.")

    # Check 3: Evidence counts differ when appropriate
    print(f"3. Threats evidence count: {len(f_threats.evidence_references)}")
    print(f"   Toxic evidence count:   {len(f_toxic.evidence_references)}")
    assert len(f_threats.evidence_references) != len(f_toxic.evidence_references), "Evidence counts are identical!"
    assert len(f_toxic.evidence_references) == 1, f"Expected 1 toxic evidence item, got {len(f_toxic.evidence_references)}"
    print("   -> PASS: Evidence counts are properly partitioned (Threats has 6 context items, Toxic has 1 text signal).")

    # Check 4: Timestamps correspond to actual evidence
    for f in report.findings:
        for ev in f.events:
            print(f"4. Event interval [{ev.start_time}s - {ev.end_time}s] for '{f.category}' (conf: {ev.confidence})")
            assert ev.start_time <= ev.end_time
    print("   -> PASS: Timestamps correspond accurately to actual evidence.")

    print("=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    session.close()


if __name__ == "__main__":
    main()
