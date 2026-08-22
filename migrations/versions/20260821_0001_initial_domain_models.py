"""Create initial moderation domain tables.

Revision ID: 20260821_0001
Revises:
Create Date: 2026-08-21 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260821_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial PostgreSQL moderation schema."""
    video_status = sa.Enum("UPLOADED", "QUEUED", "PROCESSING", "ANALYZING", "COMPLETED", "FAILED", name="video_status")
    moderation_decision = sa.Enum("APPROVED", "REVIEW_REQUIRED", "REJECTED", name="moderation_decision")
    risk_level = sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level")

    op.create_table(
        "videos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("status", video_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("duration >= 0", name="ck_videos_duration_non_negative"),
        sa.CheckConstraint("file_size >= 0", name="ck_videos_file_size_non_negative"),
        sa.CheckConstraint("width > 0", name="ck_videos_width_positive"),
        sa.CheckConstraint("height > 0", name="ck_videos_height_positive"),
        sa.CheckConstraint("fps > 0", name="ck_videos_fps_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_status", "videos", ["status"])

    op.create_table(
        "moderation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_id", sa.String(length=36), nullable=False),
        sa.Column("decision", moderation_decision, nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("overall_confidence >= 0 AND overall_confidence <= 1", name="ck_moderation_results_confidence_range"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moderation_results_video_id", "moderation_results", ["video_id"])

    op.create_table(
        "detections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("moderation_result_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("start_timestamp", sa.Float(), nullable=False),
        sa.Column("end_timestamp", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_detections_confidence_range"),
        sa.CheckConstraint("start_timestamp >= 0", name="ck_detections_start_timestamp_non_negative"),
        sa.CheckConstraint("end_timestamp IS NULL OR end_timestamp >= start_timestamp", name="ck_detections_timestamp_order"),
        sa.ForeignKeyConstraint(["moderation_result_id"], ["moderation_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_detections_moderation_result_id", "detections", ["moderation_result_id"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("detection_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.CheckConstraint("timestamp >= 0", name="ck_evidence_timestamp_non_negative"),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_detection_id", "evidence", ["detection_id"])

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_id", sa.String(length=36), nullable=False),
        sa.Column("start_timestamp", sa.Float(), nullable=False),
        sa.Column("end_timestamp", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint("start_timestamp >= 0", name="ck_transcript_segments_start_timestamp_non_negative"),
        sa.CheckConstraint("end_timestamp >= start_timestamp", name="ck_transcript_segments_timestamp_order"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_segments_video_id", "transcript_segments", ["video_id"])


def downgrade() -> None:
    """Drop the initial moderation schema."""
    op.drop_index("ix_transcript_segments_video_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_index("ix_evidence_detection_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_detections_moderation_result_id", table_name="detections")
    op.drop_table("detections")
    op.drop_index("ix_moderation_results_video_id", table_name="moderation_results")
    op.drop_table("moderation_results")
    op.drop_index("ix_videos_status", table_name="videos")
    op.drop_table("videos")

    bind = op.get_bind()
    sa.Enum(name="risk_level").drop(bind, checkfirst=True)
    sa.Enum(name="moderation_decision").drop(bind, checkfirst=True)
    sa.Enum(name="video_status").drop(bind, checkfirst=True)
