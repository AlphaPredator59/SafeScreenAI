"""Validation for untrusted uploaded video files."""

from pathlib import Path


class VideoValidationError(ValueError):
    """Raised when an uploaded file fails policy validation."""


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
MIME_TYPES = {
    ".mp4": {"video/mp4", "application/octet-stream"},
    ".mov": {"video/quicktime", "video/mp4", "application/octet-stream"},
    ".avi": {"video/x-msvideo", "video/avi", "application/octet-stream"},
    ".mkv": {"video/x-matroska", "video/webm", "application/octet-stream"},
}


def validate_upload_name_and_mime(filename: str | None, content_type: str | None) -> tuple[str, str]:
    """Validate the client filename and practical MIME information."""
    if not filename:
        raise VideoValidationError("A video filename is required.")
    safe_name = Path(filename).name
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError("Unsupported video format.")
    if content_type and content_type.lower() not in MIME_TYPES[extension]:
        raise VideoValidationError("The file MIME type does not match its extension.")
    return safe_name[:255], extension
