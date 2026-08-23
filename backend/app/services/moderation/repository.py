"""Repository for transactional persistence and retrieval of moderation data."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.db.enums import VideoStatus
from app.db.models import Detection, Evidence, ModerationResult, TranscriptSegment, Video


class ModerationRepositoryError(Exception):
    """Base exception for moderation repository database operations."""


class ModerationRepository:
    """Encapsulates data access and transactional operations for moderation domain models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_video(self, video_id: str) -> Video | None:
        """Fetch a video by ID."""
        return self.session.get(Video, video_id)

    def get_latest_moderation_result(self, video_id: str) -> ModerationResult | None:
        """Fetch the most recent moderation result for a video with eagerly loaded detections and evidence."""
        stmt = (
            select(ModerationResult)
            .where(ModerationResult.video_id == video_id)
            .options(
                selectinload(ModerationResult.video),
                selectinload(ModerationResult.detections).selectinload(Detection.evidence_items),
            )
            .order_by(ModerationResult.created_at.desc())
        )
        return self.session.scalars(stmt).first()

    def get_evidence_by_video_id(self, video_id: str) -> list[Evidence]:
        """Fetch all traceable evidence items supporting moderation for a video."""
        stmt = (
            select(Evidence)
            .join(Evidence.detection)
            .join(Detection.moderation_result)
            .where(ModerationResult.video_id == video_id)
            .order_by(Evidence.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_transcript_segments_by_video_id(self, video_id: str) -> list[TranscriptSegment]:
        """Fetch all transcript segments for a video ordered by start timestamp."""
        stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.start_timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

    def save_moderation_run(
        self,
        video_id: str,
        moderation_result: ModerationResult,
        transcript_segments: Sequence[TranscriptSegment] = (),
    ) -> ModerationResult:
        """Atomically persist a completed moderation run, replacing any prior moderation tree."""
        video = self.get_video(video_id)
        if video is None:
            raise ModerationRepositoryError(f"Cannot persist moderation run: Video '{video_id}' not found.")

        try:
            # 1. Deterministically clean up previous moderation results and transcripts for this video
            existing_results = list(
                self.session.scalars(
                    select(ModerationResult).where(ModerationResult.video_id == video_id)
                ).all()
            )
            for old_res in existing_results:
                self.session.delete(old_res)

            existing_transcripts = list(
                self.session.scalars(
                    select(TranscriptSegment).where(TranscriptSegment.video_id == video_id)
                ).all()
            )
            for old_tx in existing_transcripts:
                self.session.delete(old_tx)

            # Flush deletions before adding replacements
            self.session.flush()

            # 2. Add new moderation result and associated detections/evidence
            moderation_result.video_id = video_id
            self.session.add(moderation_result)

            # 3. Add transcript segments
            for segment in transcript_segments:
                segment.video_id = video_id
                self.session.add(segment)

            # 4. Advance video processing state to COMPLETED
            video.status = VideoStatus.COMPLETED

            self.session.commit()
            self.session.refresh(moderation_result)
            return moderation_result

        except Exception as exc:
            self.session.rollback()
            raise ModerationRepositoryError(f"Failed to persist moderation run for video '{video_id}': {exc}") from exc
