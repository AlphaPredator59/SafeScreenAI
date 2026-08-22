"""Public schemas for video ingestion and retrieval."""

from datetime import datetime

from pydantic import BaseModel

from app.db.enums import VideoStatus


class VideoUploadResponse(BaseModel):
    video_id: str
    status: VideoStatus


class VideoStatusResponse(BaseModel):
    video_id: str
    status: VideoStatus


class VideoResponse(VideoStatusResponse):
    filename: str
    duration: float
    file_size: int
    width: int
    height: int
    fps: float
    created_at: datetime
