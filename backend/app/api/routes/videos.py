"""Video ingestion and status routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db_session
from app.schemas.video import VideoResponse, VideoStatusResponse, VideoUploadResponse
from app.services.video.ingestion import VideoIngestionError, VideoIngestionService
from app.services.video.metadata import VideoMetadataService
from app.services.video.repository import VideoRepository
from app.services.video.storage import LocalStorageService

router = APIRouter(prefix="/videos", tags=["videos"])


def get_video_ingestion_service(session: Annotated[Session, Depends(get_db_session)]) -> VideoIngestionService:
    """Build the ingestion service from request-scoped infrastructure."""
    settings = get_settings()
    return VideoIngestionService(
        session=session,
        storage=LocalStorageService(settings.storage_path / "videos"),
        metadata=VideoMetadataService(),
        max_size=settings.max_upload_size_bytes,
        max_duration=settings.max_video_duration_seconds,
    )


def get_video_repository(session: Annotated[Session, Depends(get_db_session)]) -> VideoRepository:
    """Build the request-scoped repository for read-only video routes."""
    return VideoRepository(session)


@router.post("", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: Annotated[UploadFile, File(description="MP4, MOV, AVI, or MKV video file")],
    service: Annotated[VideoIngestionService, Depends(get_video_ingestion_service)],
) -> VideoUploadResponse:
    """Accept a video and persist its validated metadata."""
    try:
        video = await service.ingest(file)
    except VideoIngestionError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return VideoUploadResponse(video_id=video.id, status=video.status)


def get_video_or_404(video_id: str, repository: VideoRepository):
    """Fetch a video or expose a consistent not-found response."""
    video = repository.get(video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return video


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, repository: Annotated[VideoRepository, Depends(get_video_repository)]) -> VideoResponse:
    """Return stored public metadata and processing status for a video."""
    video = get_video_or_404(video_id, repository)
    return VideoResponse(video_id=video.id, status=video.status, filename=video.filename, duration=video.duration,
                         file_size=video.file_size, width=video.width, height=video.height, fps=video.fps,
                         created_at=video.created_at)


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
def get_video_status(video_id: str, repository: Annotated[VideoRepository, Depends(get_video_repository)]) -> VideoStatusResponse:
    """Return the current persisted processing state for a video."""
    video = get_video_or_404(video_id, repository)
    return VideoStatusResponse(video_id=video.id, status=video.status)
