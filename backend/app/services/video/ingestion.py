"""Orchestrates safe video ingestion without route-level business logic."""

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.enums import VideoStatus
from app.db.models import Video
from app.services.video.metadata import MetadataExtractionError, VideoMetadataService
from app.services.video.repository import VideoRepository
from app.services.video.storage import FileTooLargeError, LocalStorageService
from app.services.video.validation import VideoValidationError, validate_upload_name_and_mime


class VideoIngestionError(Exception):
    """A client-safe ingestion failure with an HTTP status code."""

    def __init__(self, detail: str, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code


class VideoIngestionService:
    """Validate, store, inspect, and persist a newly uploaded video."""

    def __init__(self, session: Session, storage: LocalStorageService, metadata: VideoMetadataService, max_size: int, max_duration: int) -> None:
        self.repository = VideoRepository(session)
        self.storage = storage
        self.metadata = metadata
        self.max_size = max_size
        self.max_duration = max_duration

    async def ingest(self, upload: UploadFile) -> Video:
        try:
            filename, extension = validate_upload_name_and_mime(upload.filename, upload.content_type)
        except VideoValidationError as error:
            raise VideoIngestionError(str(error), 415) from error
        video_id = f"vid_{uuid4().hex}"
        stored_path: Path | None = None
        persisted = False
        try:
            stored = await self.storage.save(upload, f"{video_id}{extension}", self.max_size)
            stored_path = stored.path
            metadata = self.metadata.extract(stored.path)
            if metadata.duration > self.max_duration:
                raise VideoIngestionError("The uploaded video exceeds the maximum duration.", 422)
            video = Video(id=video_id, filename=filename, storage_path=str(stored.path), duration=metadata.duration,
                          file_size=stored.size, width=metadata.width, height=metadata.height, fps=metadata.fps,
                          status=VideoStatus.UPLOADED)
            persisted_video = self.repository.add(video)
            persisted = True
            return persisted_video
        except FileTooLargeError as error:
            raise VideoIngestionError(str(error), 413) from error
        except MetadataExtractionError as error:
            raise VideoIngestionError(str(error), 422) from error
        except SQLAlchemyError as error:
            self.repository.session.rollback()
            raise VideoIngestionError("Unable to persist the uploaded video.", 500) from error
        finally:
            if stored_path is not None and not persisted:
                self.storage.delete(stored_path)
