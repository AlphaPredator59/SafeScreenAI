"""Independent metadata extraction for stored videos."""

from dataclasses import dataclass
from pathlib import Path
import subprocess


class MetadataExtractionError(ValueError):
    """Raised when a file cannot be opened as a readable video."""


@dataclass(frozen=True)
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    frame_count: int
    codec: str | None
    audio_available: bool


class VideoMetadataService:
    """Extract basic video metadata with OpenCV and optional FFprobe audio data."""

    def extract(self, path: Path) -> VideoMetadata:
        try:
            import cv2
        except ImportError as error:
            raise MetadataExtractionError("OpenCV is unavailable for metadata extraction.") from error
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise MetadataExtractionError("The uploaded file is not a readable video.")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if fps <= 0 or width <= 0 or height <= 0:
                raise MetadataExtractionError("The uploaded video has invalid metadata.")
            codec_value = int(capture.get(cv2.CAP_PROP_FOURCC))
            codec = "".join(chr((codec_value >> shift) & 0xFF) for shift in (0, 8, 16, 24)).strip() or None
            return VideoMetadata(frames / fps, width, height, fps, frames, codec, self._has_audio(path))
        finally:
            capture.release()

    @staticmethod
    def _has_audio(path: Path) -> bool:
        """Use FFprobe when available; absence of FFprobe is non-fatal."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                check=False, capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and bool(result.stdout.strip())
