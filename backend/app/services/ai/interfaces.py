"""Replaceable protocols for future AI adapters."""

from typing import Protocol, Sequence, runtime_checkable

from app.services.ai.contracts import ContextualInterpretation, TextModerationSignal, TimestampedFrame, TranscriptSegment, VisualDetection
from app.services.video.processing import AudioArtifact


@runtime_checkable
class VisionAnalyzer(Protocol):
    def analyze(self, frames: Sequence[TimestampedFrame]) -> list[VisualDetection]: ...


@runtime_checkable
class Transcriber(Protocol):
    def transcribe(self, audio: AudioArtifact) -> list[TranscriptSegment]: ...


@runtime_checkable
class TextModerator(Protocol):
    def moderate(self, segments: Sequence[TranscriptSegment]) -> list[TextModerationSignal]: ...


@runtime_checkable
class ContextAnalyzer(Protocol):
    def analyze(
        self,
        detections: Sequence[VisualDetection],
        transcripts: Sequence[TranscriptSegment],
        signals: Sequence[TextModerationSignal],
        frames: Sequence[TimestampedFrame] | None = None,
    ) -> ContextualInterpretation: ...


