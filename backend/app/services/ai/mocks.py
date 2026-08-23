from collections.abc import Sequence

from app.services.ai.contracts import ContextualInterpretation, TextModerationSignal, TimestampedFrame, TranscriptSegment, VisualDetection
from app.services.video.processing import AudioArtifact


class MockVisionAnalyzer:
    def analyze(self, frames: Sequence[TimestampedFrame]) -> list[VisualDetection]:
        return [VisualDetection("mock_visual", 0.9, frame.timestamp, frame.frame_id) for frame in frames]


class MockTranscriber:
    def transcribe(self, audio: AudioArtifact) -> list[TranscriptSegment]:
        return [] if not audio.audio_available else [TranscriptSegment(0.0, min(audio.duration or 1.0, 1.0), "mock transcript")]


class MockTextModerator:
    def moderate(self, segments: Sequence[TranscriptSegment]) -> list[TextModerationSignal]:
        return [TextModerationSignal("mock_text", 0.8, item.start, item.end, item.text) for item in segments]


class MockContextAnalyzer:
    def analyze(
        self,
        detections: Sequence[VisualDetection],
        transcripts: Sequence[TranscriptSegment],
        signals: Sequence[TextModerationSignal],
        frames: Sequence[TimestampedFrame] | None = None,
    ) -> ContextualInterpretation:
        frame_refs = [f.frame_id for f in (frames or ())]
        det_refs = [item.evidence_reference for item in detections]
        trans_refs = [f"transcript:{index}" for index, _ in enumerate(transcripts)]
        refs = tuple(dict.fromkeys(frame_refs + det_refs + trans_refs))
        return ContextualInterpretation("mock_context", 0.7, "Deterministic mock interpretation.", refs)
