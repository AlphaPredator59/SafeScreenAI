"""Tests for vendor-neutral AI contracts and deterministic mock adapters."""

import pytest

from app.services.ai.contracts import TimestampedFrame, TranscriptSegment, VisualDetection
from app.services.ai.mocks import MockContextAnalyzer, MockTextModerator, MockTranscriber, MockVisionAnalyzer
from app.services.video.processing import AudioArtifact


def test_mock_ai_pipeline_returns_structured_results() -> None:
    frame = TimestampedFrame("frame_1", 1.0, "frames/one.jpg")
    detections = MockVisionAnalyzer().analyze([frame])
    segments = MockTranscriber().transcribe(AudioArtifact(True, None, "wav", 2.0))
    signals = MockTextModerator().moderate(segments)
    context = MockContextAnalyzer().analyze(detections, segments, signals)
    assert detections[0].evidence_reference == "frame_1"
    assert signals[0].source_text == "mock transcript"
    assert context.evidence_references == ("frame_1", "transcript:0")


@pytest.mark.parametrize("factory", [lambda: VisualDetection("x", 1.1, 0, "f"), lambda: TranscriptSegment(2, 1, "bad")])
def test_contracts_reject_invalid_values(factory) -> None:
    with pytest.raises(ValueError): factory()
