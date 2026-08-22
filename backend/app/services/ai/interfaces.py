"""Replaceable protocols for future AI adapters."""

from typing import Protocol, Sequence

from app.services.ai.contracts import ContextualInterpretation, TextModerationSignal, TimestampedFrame, TranscriptSegment, VisualDetection
from app.services.video.processing import AudioArtifact


class VisionAnalyzer(Protocol):
    def analyze(self, frames: Sequence[TimestampedFrame]) -> list[VisualDetection]: ...


class Transcriber(Protocol):
    def transcribe(self, audio: AudioArtifact) -> list[TranscriptSegment]: ...


class TextModerator(Protocol):
    def moderate(self, segments: Sequence[TranscriptSegment]) -> list[TextModerationSignal]: ...


class ContextAnalyzer(Protocol):
    def analyze(self, detections: Sequence[VisualDetection], transcripts: Sequence[TranscriptSegment], signals: Sequence[TextModerationSignal]) -> ContextualInterpretation: ...
