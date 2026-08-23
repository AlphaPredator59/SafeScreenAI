"""API routes for moderation results and evidence retrieval."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.validators import validate_video_id
from app.db.database import get_db_session
from app.schemas.moderation import EvidenceListResponse, ModerationReportResponse
from app.services.moderation.reporting import ModerationReportService
from app.services.moderation.repository import ModerationRepository

router = APIRouter(prefix="/videos", tags=["moderation"])


def get_moderation_report_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ModerationReportService:
    """Build request-scoped ModerationReportService."""
    repository = ModerationRepository(session)
    return ModerationReportService(repository)


def get_moderation_repository(
    session: Annotated[Session, Depends(get_db_session)],
) -> ModerationRepository:
    """Build request-scoped ModerationRepository."""
    return ModerationRepository(session)


@router.get(
    "/{video_id}/moderation",
    response_model=ModerationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve full moderation report for a video",
)
def get_video_moderation_report(
    video_id: Annotated[str, Depends(validate_video_id)],
    service: Annotated[ModerationReportService, Depends(get_moderation_report_service)],
    repository: Annotated[ModerationRepository, Depends(get_moderation_repository)],
) -> ModerationReportResponse:
    """Return the structured moderation assessment, policy findings, evidence, and transcripts."""
    video = repository.get_video(video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    report = service.get_moderation_report(video_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Moderation report not found for this video.",
        )

    return report


@router.get(
    "/{video_id}/evidence",
    response_model=EvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve all traceable evidence supporting video moderation",
)
def get_video_evidence(
    video_id: Annotated[str, Depends(validate_video_id)],
    service: Annotated[ModerationReportService, Depends(get_moderation_report_service)],
    repository: Annotated[ModerationRepository, Depends(get_moderation_repository)],
) -> EvidenceListResponse:
    """Return the collection of traceable evidence supporting policy findings."""
    video = repository.get_video(video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    evidence_list = service.get_evidence_list(video_id)
    if evidence_list is None:
        return EvidenceListResponse(video_id=video_id, total_count=0, evidence=[])

    return evidence_list
