"""Service for generating structured, explainable public moderation reports and evidence responses."""

from typing import Any

from app.schemas.moderation import (
    EvidenceItemResponse,
    EvidenceListResponse,
    FindingResponse,
    ModerationReportResponse,
    PolicyEventResponse,
    TranscriptSegmentResponse,
)
from app.services.moderation.formatting import GeminiReportFormatter, get_report_formatter
from app.services.moderation.repository import ModerationRepository


class ModerationReportService:
    """Retrieves persisted moderation data and produces sanitized, structured public report schemas."""

    def __init__(
        self,
        repository: ModerationRepository,
        formatter: GeminiReportFormatter | None = None,
    ) -> None:
        self.repository = repository
        self.formatter = formatter or get_report_formatter()

    def get_moderation_report(self, video_id: str) -> ModerationReportResponse | None:
        """Generate a complete moderation report for a video or return None if missing."""
        video = self.repository.get_video(video_id)
        if video is None:
            return None

        result = self.repository.get_latest_moderation_result(video_id)
        if result is None:
            return None

        transcripts = self.repository.get_transcript_segments_by_video_id(video_id)

        # 1. Structure findings and discrete policy events from persisted detections
        findings: list[FindingResponse] = []
        all_evidence: list[EvidenceItemResponse] = []
        seen_evidence_ids: set[str] = set()

        category_order: list[str] = []
        detections_by_category: dict[str, list[Any]] = {}

        for d in result.detections:
            if d.category not in category_order:
                category_order.append(d.category)
                detections_by_category[d.category] = []
            detections_by_category[d.category].append(d)

            for ev in d.evidence_items:
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

        detected_categories = category_order

        for cat in category_order:
            cat_detections = detections_by_category[cat]
            events: list[PolicyEventResponse] = []
            finding_ev_refs: list[str] = []

            for d in cat_detections:
                d_ev_refs = [ev.storage_path or ev.id for ev in d.evidence_items]
                d_ev_types = sorted(list({ev.type for ev in d.evidence_items}))
                finding_ev_refs.extend(d_ev_refs)

                events.append(
                    PolicyEventResponse(
                        id=d.id,
                        start_time=d.start_timestamp,
                        end_time=d.end_timestamp if d.end_timestamp is not None else d.start_timestamp,
                        confidence=d.confidence,
                        evidence_ids=d_ev_refs,
                        evidence_types=d_ev_types,
                        description=d.explanation or "",
                    )
                )

            # Finding-level aggregate fields
            finding_conf = max((d.confidence for d in cat_detections), default=result.overall_confidence)
            start_ts = min((d.start_timestamp for d in cat_detections), default=0.0)
            end_ts = max(((d.end_timestamp or d.start_timestamp) for d in cat_detections), default=None)
            deduped_refs = list(dict.fromkeys(finding_ev_refs))
            summary_text = (
                f"Flagged {len(events)} event(s) for '{cat}' policy with peak confidence {finding_conf:.2f}."
                if len(events) > 1
                else (cat_detections[0].explanation or f"Policy finding for '{cat}'.")
            )

            findings.append(
                FindingResponse(
                    id=cat_detections[0].id,
                    category=cat,
                    severity=0.0,
                    confidence=round(finding_conf, 4),
                    summary=summary_text,
                    start_timestamp=round(start_ts, 2),
                    end_timestamp=round(end_ts, 2) if end_ts is not None else None,
                    explanation=summary_text,
                    evidence_references=deduped_refs,
                    events=events,
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

        report = ModerationReportResponse(
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

        # Generate Gemini-formatted or deterministic fallback executive summary & AI justification
        summary, justification = self.formatter.format_report(report)
        report.executive_summary = summary
        report.ai_justification = justification

        return report

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
