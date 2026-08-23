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

        # 2. Map only policy-relevant detections
        # Note: Non-violating raw YOLO objects (e.g. broccoli, bowl, knife in cooking) are NOT persisted as policy violations.
        if result.detected_categories:
            for category in result.detected_categories:
                # Find supporting evidence items matching or relevant to this policy category
                relevant_evidence = [
                    ev for ev in result.supporting_evidence
                    if category.lower() in ev.category.lower() or ev.modality in ("context", "text_signal", "visual")
                ]
                if not relevant_evidence:
                    relevant_evidence = list(result.supporting_evidence)

                # Compute bounds
                timestamps = [ev.timestamp for ev in relevant_evidence if ev.timestamp is not None]
                start_ts = min(timestamps) if timestamps else 0.0
                end_ts = max(timestamps) if timestamps else None
                conf = max([ev.confidence for ev in relevant_evidence], default=result.overall_confidence)

                detection_model = DetectionModel(
                    category=category,
                    confidence=round(conf, 4),
                    start_timestamp=round(start_ts, 2),
                    end_timestamp=round(end_ts, 2) if end_ts is not None else None,
                    explanation=f"Policy finding for '{category}' supported by multi-modal evidence synthesis.",
                )

                # Attach traceable evidence items to this detection
                for ev in relevant_evidence:
                    # Sanitize storage_path to avoid exposing server-side absolute paths
                    sanitized_ref = Path(ev.reference).name if "/" in ev.reference or "\\" in ev.reference else ev.reference
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
