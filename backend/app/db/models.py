"""SQLAlchemy ORM models for persisted moderation data."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.enums import ModerationDecision, RiskLevel, VideoStatus


class Video(Base):
    """A stored video and its processing lifecycle state."""

    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint("duration >= 0", name="ck_videos_duration_non_negative"),
        CheckConstraint("file_size >= 0", name="ck_videos_file_size_non_negative"),
        CheckConstraint("width > 0", name="ck_videos_width_positive"),
        CheckConstraint("height > 0", name="ck_videos_height_positive"),
        CheckConstraint("fps > 0", name="ck_videos_fps_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status", create_constraint=True),
        nullable=False,
        default=VideoStatus.UPLOADED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    moderation_results: Mapped[list["ModerationResult"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class ModerationResult(Base):
    """A moderation assessment for a video."""

    __tablename__ = "moderation_results"
    __table_args__ = (
        CheckConstraint("overall_confidence >= 0 AND overall_confidence <= 1", name="ck_moderation_results_confidence_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[ModerationDecision] = mapped_column(
        Enum(ModerationDecision, name="moderation_decision", create_constraint=True), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level", create_constraint=True), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    video: Mapped[Video] = relationship(back_populates="moderation_results")
    detections: Mapped[list["Detection"]] = relationship(back_populates="moderation_result", cascade="all, delete-orphan")


class Detection(Base):
    """A model signal associated with one moderation result."""

    __tablename__ = "detections"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_detections_confidence_range"),
        CheckConstraint("start_timestamp >= 0", name="ck_detections_start_timestamp_non_negative"),
        CheckConstraint("end_timestamp IS NULL OR end_timestamp >= start_timestamp", name="ck_detections_timestamp_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    moderation_result_id: Mapped[str] = mapped_column(ForeignKey("moderation_results.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    start_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    end_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    moderation_result: Mapped[ModerationResult] = relationship(back_populates="detections")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="detection", cascade="all, delete-orphan")


class Evidence(Base):
    """Traceable evidence supporting a detection."""

    __tablename__ = "evidence"
    __table_args__ = (CheckConstraint("timestamp >= 0", name="ck_evidence_timestamp_non_negative"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    detection: Mapped[Detection] = relationship(back_populates="evidence_items")


class TranscriptSegment(Base):
    """A timestamped transcript segment extracted from a video."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        CheckConstraint("start_timestamp >= 0", name="ck_transcript_segments_start_timestamp_non_negative"),
        CheckConstraint("end_timestamp >= start_timestamp", name="ck_transcript_segments_timestamp_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    start_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    end_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    video: Mapped[Video] = relationship(back_populates="transcript_segments")
