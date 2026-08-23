"""Reusable request and path parameter validation utilities."""

import re

from fastapi import HTTPException, Path, status

# Valid video IDs contain letters, numbers, underscores, and hyphens (up to 128 chars).
VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def validate_video_id(
    video_id: str = Path(..., description="Unique identifier for the video"),
) -> str:
    """Validate that a video_id path parameter conforms to the expected character set.

    Raises HTTP 400 Bad Request if the ID contains forbidden characters (e.g. NUL bytes,
    spaces, path traversal sequences, or control characters) before reaching the database.
    """
    if not isinstance(video_id, str) or not VIDEO_ID_REGEX.match(video_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format. Video ID must contain only alphanumeric characters, underscores, or hyphens.",
        )
    return video_id
