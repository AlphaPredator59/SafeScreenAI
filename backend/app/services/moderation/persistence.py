"""Persistence service bridging M1-M8 domain evaluations to transactional database records."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.db.models import (
    Detection as DetectionModel,
    Evidence as EvidenceModel,
    ModerationResult as ModerationResultModel,
    TranscriptSegment as TranscriptSegmentModel,
)
from app.services.ai.contracts import (
    ContextualInterpretation,
    TextModerationSignal,
    TranscriptSegment,
    VisualDetection,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult
from app.services.moderation.repository import ModerationRepository, ModerationRepositoryError
from app.services.moderation.temporal_grouping import (
    build_policy_findings,
    get_category_supporting_evidence,
)


class ModerationPersistenceError(Exception):
    """Exception raised when persistence of moderation data fails."""


class ModerationPersistenceService:
    """Orchestrates mapping and persistence of in-memory moderation results to PostgreSQL."""

    def __init__(self, repository: ModerationRepository) -> None:
        self.repository = repository

    def persist_moderation_run(
        self,
        video_id: str,
        result: ModerationResult,
        transcripts: Sequence[TranscriptSegment] = (),
        detections: Sequence[VisualDetection] = (),
        text_signals: Sequence[TextModerationSignal] = (),
        context: ContextualInterpretation | None = None,
    ) -> ModerationResultModel:
        """Persist a complete moderation evaluation run to the database."""
        # 1. Create ORM ModerationResult model
        db_result = ModerationResultModel(
            video_id=video_id,
            decision=result.decision,
            risk_level=result.risk_level,
            risk_score=result.risk_score,
            overall_confidence=result.overall_confidence,
            explanation=result.explanation,
        )

        # 2. Map only policy-relevant detections at event-level intervals
        # Note: Non-violating raw YOLO objects (e.g. broccoli, bowl, chair) are NOT persisted as policy violations.
        findings = result.findings
        if not findings and result.detected_categories:
            findings = tuple(
                build_policy_findings(
                    detected_categories=result.detected_categories,
                    evidence_items=result.supporting_evidence,
                )
            )

        if findings:
            for finding in findings:
                # Supporting evidence for this category
                cat_evidence = get_category_supporting_evidence(
                    category=finding.category,
                    evidence_items=result.supporting_evidence,
                )

                if finding.events:
                    for event in finding.events:
                        detection_model = DetectionModel(
                            category=finding.category,
                            confidence=round(event.confidence, 4),
                            start_timestamp=round(event.start_time, 2),
                            end_timestamp=round(event.end_time, 2) if event.end_time is not None else None,
                            explanation=event.description or finding.summary,
                        )

                        # Find evidence items that support this specific event
                        event_evidence = [
                            ev for ev in cat_evidence
                            if ev.reference in event.evidence_ids
                            or (
                                ev.timestamp is not None
                                and (event.start_time - 1.0) <= ev.timestamp <= (event.end_time + 1.0)
                            )
                        ]
                        if not event_evidence:
                            event_evidence = cat_evidence

                        for ev in event_evidence:
                            sanitized_ref = (
                                Path(ev.reference).name
                                if ("/" in ev.reference or "\\" in ev.reference)
                                else ev.reference
                            )
                            evidence_model = EvidenceModel(
                                type=ev.modality,
                                timestamp=round(ev.timestamp if ev.timestamp is not None else event.start_time, 2),
                                storage_path=sanitized_ref,
                                content=ev.description,
                            )
                            detection_model.evidence_items.append(evidence_model)

                        db_result.detections.append(detection_model)
                else:
                    # Untimed or empty-event finding fallback
                    start_ts = 0.0
                    end_ts = 0.0
                    detection_model = DetectionModel(
                        category=finding.category,
                        confidence=round(finding.confidence, 4),
                        start_timestamp=round(start_ts, 2),
                        end_timestamp=round(end_ts, 2),
                        explanation=finding.summary,
                    )
                    for ev in cat_evidence:
                        sanitized_ref = (
                            Path(ev.reference).name
                            if ("/" in ev.reference or "\\" in ev.reference)
                            else ev.reference
                        )
                        evidence_model = EvidenceModel(
                            type=ev.modality,
                            timestamp=round(ev.timestamp if ev.timestamp is not None else start_ts, 2),
                            storage_path=sanitized_ref,
                            content=ev.description,
                        )
                        detection_model.evidence_items.append(evidence_model)
                    db_result.detections.append(detection_model)

        # 3. Map transcript segments
        db_transcripts: list[TranscriptSegmentModel] = []
        for seg in transcripts:
            db_transcripts.append(
                TranscriptSegmentModel(
                    video_id=video_id,
                    start_timestamp=round(seg.start, 2),
                    end_timestamp=round(seg.end, 2),
                    text=seg.text,
                )
            )

        # 4. Atomically persist through repository
        try:
            return self.repository.save_moderation_run(
                video_id=video_id,
                moderation_result=db_result,
                transcript_segments=db_transcripts,
            )
        except ModerationRepositoryError as exc:
            raise ModerationPersistenceError(str(exc)) from exc
