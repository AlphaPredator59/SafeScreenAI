"""Service for generating structured, explainable public moderation reports and evidence responses."""

from app.schemas.moderation import (
    EvidenceItemResponse,
    EvidenceListResponse,
    FindingResponse,
    ModerationReportResponse,
    TranscriptSegmentResponse,
)
from app.services.moderation.repository import ModerationRepository


class ModerationReportService:
    """Retrieves persisted moderation data and produces sanitized, structured public report schemas."""

    def __init__(self, repository: ModerationRepository) -> None:
        self.repository = repository

    def get_moderation_report(self, video_id: str) -> ModerationReportResponse | None:
        """Generate a complete moderation report for a video or return None if missing."""
        video = self.repository.get_video(video_id)
        if video is None:
            return None

        result = self.repository.get_latest_moderation_result(video_id)
        if result is None:
            return None

        transcripts = self.repository.get_transcript_segments_by_video_id(video_id)

        # 1. Structure findings from persisted policy detections
        findings: list[FindingResponse] = []
        all_evidence: list[EvidenceItemResponse] = []
        seen_evidence_ids: set[str] = set()
        detected_categories: list[str] = []

        for d in result.detections:
            if d.category not in detected_categories:
                detected_categories.append(d.category)

            ev_refs: list[str] = []
            for ev in d.evidence_items:
                ref_str = ev.storage_path or ev.id
                ev_refs.append(ref_str)
                if ev.id not in seen_evidence_ids:
                    seen_evidence_ids.add(ev.id)
                    all_evidence.append(
                        EvidenceItemResponse(
                            id=ev.id,
                            type=ev.type,
                            timestamp=ev.timestamp,
                            content=ev.content,
                            reference=ev.storage_path,
                        )
                    )

            findings.append(
                FindingResponse(
                    id=d.id,
                    category=d.category,
                    confidence=d.confidence,
                    start_timestamp=d.start_timestamp,
                    end_timestamp=d.end_timestamp,
                    explanation=d.explanation,
                    evidence_references=ev_refs,
                )
            )

        # 2. Structure transcript segments
        transcript_responses: list[TranscriptSegmentResponse] = [
            TranscriptSegmentResponse(
                start_timestamp=t.start_timestamp,
                end_timestamp=t.end_timestamp,
                text=t.text,
            )
            for t in transcripts
        ]

        return ModerationReportResponse(
            video_id=video.id,
            filename=video.filename,
            created_at=result.created_at,
            decision=result.decision,
            risk_level=result.risk_level,
            risk_score=result.risk_score,
            overall_confidence=result.overall_confidence,
            detected_categories=detected_categories,
            explanation=result.explanation or "",
            findings=findings,
            evidence=all_evidence,
            transcripts=transcript_responses,
        )

    def get_evidence_list(self, video_id: str) -> EvidenceListResponse | None:
        """Fetch all traceable evidence items for a video or return None if video doesn't exist."""
        video = self.repository.get_video(video_id)
        if video is None:
            return None

        evidence_items = self.repository.get_evidence_by_video_id(video_id)
        evidence_responses = [
            EvidenceItemResponse(
                id=ev.id,
                type=ev.type,
                timestamp=ev.timestamp,
                content=ev.content,
                reference=ev.storage_path,
            )
            for ev in evidence_items
        ]

        return EvidenceListResponse(
            video_id=video.id,
            total_count=len(evidence_responses),
            evidence=evidence_responses,
        )
