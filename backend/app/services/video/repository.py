"""Persistence operations for videos."""

from sqlalchemy.orm import Session

from app.db.models import Video


class VideoRepository:
    """Small data-access wrapper for the Video entity."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, video: Video) -> Video:
        self.session.add(video)
        self.session.commit()
        self.session.refresh(video)
        return video

    def get(self, video_id: str) -> Video | None:
        return self.session.get(Video, video_id)
