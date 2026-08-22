"""Internal frame and audio processing services for stored videos."""

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
from uuid import uuid4

from app.db.models import Video
from app.services.video.storage import LocalStorageService


class ProcessingError(RuntimeError):
    """Raised when a video processing artifact cannot be created."""


@dataclass(frozen=True)
class FrameArtifact:
    frame_id: str
    timestamp: float
    storage_path: Path


@dataclass(frozen=True)
class AudioArtifact:
    audio_available: bool
    storage_path: Path | None
    format: str | None
    duration: float | None


@dataclass(frozen=True)
class ProcessingResult:
    frames: list[FrameArtifact]
    audio: AudioArtifact


class FrameProcessingService:
    """Sample deterministic timestamped frames from a stored video."""

    def __init__(self, storage: LocalStorageService, interval_seconds: float = 1.0, image_format: str = "jpg", quality: int = 85) -> None:
        self.storage, self.interval_seconds, self.image_format, self.quality = storage, interval_seconds, image_format, quality

    def extract(self, video: Video) -> list[FrameArtifact]:
        if self.interval_seconds <= 0:
            raise ProcessingError("Frame sampling interval must be positive.")
        try:
            import cv2
        except ImportError as error:
            raise ProcessingError("OpenCV is unavailable for frame processing.") from error
        capture = cv2.VideoCapture(video.storage_path)
        artifacts: list[FrameArtifact] = []
        try:
            if not capture.isOpened():
                raise ProcessingError("Stored video is unreadable.")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if fps <= 0:
                raise ProcessingError("Stored video has invalid FPS metadata.")
            next_timestamp, frame_index = 0.0, 0
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp = frame_index / fps
                if timestamp + 1e-9 >= next_timestamp:
                    encoded, buffer = cv2.imencode(f".{self.image_format}", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                    if not encoded:
                        raise ProcessingError("Unable to encode extracted frame.")
                    frame_id = f"frame_{uuid4().hex}"
                    path = self.storage.write_bytes(Path("frames") / video.id / f"{frame_id}.{self.image_format}", buffer.tobytes())
                    artifacts.append(FrameArtifact(frame_id, timestamp, path))
                    next_timestamp += self.interval_seconds
                frame_index += 1
        except ProcessingError:
            self._cleanup(artifacts)
            raise
        finally:
            capture.release()
        if not artifacts:
            raise ProcessingError("Stored video contained no readable frames.")
        return artifacts

    def _cleanup(self, artifacts: list[FrameArtifact]) -> None:
        for artifact in artifacts:
            self.storage.delete(artifact.storage_path)


class AudioProcessingService:
    """Inspect and extract a source audio track with FFprobe and FFmpeg."""

    def __init__(self, storage: LocalStorageService, output_format: str = "wav") -> None:
        self.storage, self.output_format = storage, output_format

    def extract(self, video: Video) -> AudioArtifact:
        try:
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", video.storage_path], capture_output=True, text=True, check=False, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProcessingError("FFprobe could not inspect the stored video.") from error
        if probe.returncode != 0:
            raise ProcessingError("Stored video is unreadable by FFprobe.")
        streams = json.loads(probe.stdout).get("streams", [])
        if not any(stream.get("codec_type") == "audio" for stream in streams):
            return AudioArtifact(False, None, None, None)
        path = self.storage.artifact_path(Path("audio") / video.id / f"audio.{self.output_format}")
        try:
            result = subprocess.run(["ffmpeg", "-y", "-i", video.storage_path, "-vn", str(path)], capture_output=True, text=True, check=False, timeout=60)
            if result.returncode != 0:
                raise ProcessingError("FFmpeg could not extract the audio track.")
            return AudioArtifact(True, path, self.output_format, video.duration)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProcessingError("FFmpeg could not extract the audio track.") from error
        except ProcessingError:
            self.storage.delete(path)
            raise


class VideoProcessingOrchestrator:
    """Coordinate internal frame and audio processing for one stored video."""

    def __init__(self, frames: FrameProcessingService, audio: AudioProcessingService) -> None:
        self.frames, self.audio = frames, audio

    def process(self, video: Video) -> ProcessingResult:
        frames = self.frames.extract(video)
        try:
            audio = self.audio.extract(video)
        except ProcessingError:
            for frame in frames:
                self.frames.storage.delete(frame.storage_path)
            raise
        return ProcessingResult(frames, audio)
