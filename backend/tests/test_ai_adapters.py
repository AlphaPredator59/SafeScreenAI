"""Tests for real AI model adapters, error translation, and factory selection."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.ai import (
    AIServiceError,
    MockContextAnalyzer,
    MockTextModerator,
    MockTranscriber,
    MockVisionAnalyzer,
    QwenContextAnalyzer,
    TextModerator,
    TimestampedFrame,
    Transcriber,
    TranscriptSegment,
    TransformerTextModerator,
    VisionAnalyzer,
    WhisperTranscriber,
    YoloVisionAnalyzer,
    get_context_analyzer,
    get_text_moderator,
    get_transcriber,
    get_vision_analyzer,
)
from app.services.video.processing import AudioArtifact


# ---------------------------------------------------------------------------
# 1. Vision Adapter Tests
# ---------------------------------------------------------------------------


def test_yolo_vision_analyzer_satisfies_protocol() -> None:
    analyzer = YoloVisionAnalyzer()
    assert isinstance(analyzer, VisionAnalyzer)


def test_yolo_vision_analyzer_empty_frames() -> None:
    analyzer = YoloVisionAnalyzer()
    assert analyzer.analyze([]) == []


def test_yolo_vision_analyzer_missing_file_raises_ai_error(tmp_path: Path) -> None:
    analyzer = YoloVisionAnalyzer()
    frame = TimestampedFrame("f1", 1.0, str(tmp_path / "nonexistent.jpg"))
    with pytest.raises(AIServiceError, match="Frame image not found"):
        analyzer.analyze([frame])


def test_yolo_vision_analyzer_model_load_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frame_file = tmp_path / "frame.jpg"
    frame_file.write_bytes(b"dummy")
    frame = TimestampedFrame("f1", 1.0, str(frame_file))

    analyzer = YoloVisionAnalyzer(model_name_or_path="invalid_model.pt")

    import sys
    import types

    fake_ultralytics = types.ModuleType("ultralytics")

    def broken_yolo(*args, **kwargs):
        raise RuntimeError("Model corrupted")

    fake_ultralytics.YOLO = broken_yolo
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    with pytest.raises(AIServiceError, match="Model corrupted"):
        analyzer.analyze([frame])


def test_yolo_vision_analyzer_parses_detections_correctly(tmp_path: Path) -> None:
    frame_file = tmp_path / "frame.jpg"
    frame_file.write_bytes(b"dummy")
    frame = TimestampedFrame("frame_42", 3.5, str(frame_file))

    # Construct mock YOLO prediction result
    class FakeTensor:
        def __init__(self, val):
            self.val = val

        def item(self):
            return self.val

        def tolist(self):
            return self.val

    class FakeBox:
        def __init__(self, cls_id: int, conf: float, xyxy: list[float]):
            self.cls = [FakeTensor(cls_id)]
            self.conf = [FakeTensor(conf)]
            self.xyxy = [FakeTensor(xyxy)]

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeYoloModel:
        names = {0: "person", 43: "knife"}

        def predict(self, source: str, conf: float, device: str, verbose: bool):
            return [FakeResult([FakeBox(43, 0.92, [10.0, 20.0, 50.0, 60.0])])]

    analyzer = YoloVisionAnalyzer(model=FakeYoloModel())
    detections = analyzer.analyze([frame])

    assert len(detections) == 1
    det = detections[0]
    assert det.category == "knife"
    assert det.confidence == 0.92
    assert det.timestamp == 3.5
    assert det.evidence_reference == "frame_42"
    assert "box" in det.metadata


def test_yolo_vision_analyzer_inference_error_raises_ai_error(tmp_path: Path) -> None:
    frame_file = tmp_path / "frame.jpg"
    frame_file.write_bytes(b"dummy")
    frame = TimestampedFrame("f1", 1.0, str(frame_file))

    class BrokenYoloModel:
        names = {}

        def predict(self, *args, **kwargs):
            raise RuntimeError("CUDA out of memory")

    analyzer = YoloVisionAnalyzer(model=BrokenYoloModel())
    with pytest.raises(AIServiceError, match="Vision inference failed"):
        analyzer.analyze([frame])


# ---------------------------------------------------------------------------
# 2. Speech-to-Text Adapter Tests
# ---------------------------------------------------------------------------


def test_whisper_transcriber_satisfies_protocol() -> None:
    transcriber = WhisperTranscriber()
    assert isinstance(transcriber, Transcriber)


def test_whisper_transcriber_handles_no_audio() -> None:
    transcriber = WhisperTranscriber()
    no_audio = AudioArtifact(audio_available=False, storage_path=None, format=None, duration=None)
    assert transcriber.transcribe(no_audio) == []


def test_whisper_transcriber_missing_audio_file_raises_ai_error(tmp_path: Path) -> None:
    transcriber = WhisperTranscriber()
    artifact = AudioArtifact(audio_available=True, storage_path=tmp_path / "missing.wav", format="wav", duration=5.0)
    with pytest.raises(AIServiceError, match="Audio file not found"):
        transcriber.transcribe(artifact)


def test_whisper_transcriber_model_load_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"dummy")
    artifact = AudioArtifact(audio_available=True, storage_path=audio_file, format="wav", duration=5.0)

    transcriber = WhisperTranscriber()

    import sys
    import types

    fake_whisper = types.ModuleType("whisper")

    def broken_load(*args, **kwargs):
        raise RuntimeError("Checkpoint missing")

    fake_whisper.load_model = broken_load
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)

    with pytest.raises(AIServiceError, match="Checkpoint missing"):
        transcriber.transcribe(artifact)


def test_whisper_transcriber_parses_segments_correctly(tmp_path: Path) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"dummy")
    artifact = AudioArtifact(audio_available=True, storage_path=audio_file, format="wav", duration=10.0)

    class FakeWhisperModel:
        def transcribe(self, path: str, **kwargs):
            return {
                "segments": [
                    {"start": 1.2, "end": 3.4, "text": "  Stop right there.  "},
                    {"start": 3.5, "end": 6.0, "text": "Do not move."},
                ]
            }

    transcriber = WhisperTranscriber(model=FakeWhisperModel())
    segments = transcriber.transcribe(artifact)

    assert len(segments) == 2
    assert segments[0].start == 1.2
    assert segments[0].end == 3.4
    assert segments[0].text == "Stop right there."
    assert segments[1].start == 3.5
    assert segments[1].end == 6.0
    assert segments[1].text == "Do not move."


def test_whisper_transcriber_inference_error_raises_ai_error(tmp_path: Path) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"dummy")
    artifact = AudioArtifact(audio_available=True, storage_path=audio_file, format="wav", duration=5.0)

    class BrokenWhisperModel:
        def transcribe(self, path: str, **kwargs):
            raise RuntimeError("Audio decoding failed")

    transcriber = WhisperTranscriber(model=BrokenWhisperModel())
    with pytest.raises(AIServiceError, match="Whisper transcription failed"):
        transcriber.transcribe(artifact)


def test_whisper_transcriber_precision_flags_for_cpu_and_cuda(tmp_path: Path) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"dummy")
    artifact = AudioArtifact(audio_available=True, storage_path=audio_file, format="wav", duration=5.0)

    captured_kwargs: list[dict[str, Any]] = []

    class MockWhisperModel:
        def transcribe(self, path: Any, **kwargs: Any) -> dict[str, Any]:
            captured_kwargs.append(kwargs)
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "test"}]}

    # CPU mode must pass fp16=False
    transcriber_cpu = WhisperTranscriber(device="cpu", model=MockWhisperModel())
    transcriber_cpu.transcribe(artifact)
    assert captured_kwargs[-1].get("fp16") is False

    # CUDA mode must pass fp16=True
    transcriber_cuda = WhisperTranscriber(device="cuda", model=MockWhisperModel())
    transcriber_cuda.transcribe(artifact)
    assert captured_kwargs[-1].get("fp16") is True


# ---------------------------------------------------------------------------
# 3. Text Moderation Adapter Tests
# ---------------------------------------------------------------------------


def test_transformer_text_moderator_satisfies_protocol() -> None:
    moderator = TransformerTextModerator()
    assert isinstance(moderator, TextModerator)


def test_transformer_text_moderator_empty_segments() -> None:
    moderator = TransformerTextModerator()
    assert moderator.moderate([]) == []


def test_transformer_text_moderator_pipeline_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    moderator = TransformerTextModerator()

    import sys
    import types

    fake_transformers = types.ModuleType("transformers")

    def broken_pipeline(*args, **kwargs):
        raise RuntimeError("Model weights not found")

    fake_transformers.pipeline = broken_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    segment = TranscriptSegment(1.0, 2.0, "hello world")
    with pytest.raises(AIServiceError, match="Model weights not found"):
        moderator.moderate([segment])


def test_transformer_text_moderator_parses_and_filters_signals() -> None:
    class FakePipeline:
        def __call__(self, text: str):
            if "knife" in text:
                return [
                    {"label": "threat", "score": 0.85},
                    {"label": "neutral", "score": 0.15},
                    {"label": "insult", "score": 0.30},  # below threshold 0.5
                ]
            return [{"label": "non-toxic", "score": 0.99}]

    moderator = TransformerTextModerator(
        confidence_threshold=0.5,
        pipeline=FakePipeline(),
    )

    segments = [
        TranscriptSegment(0.0, 2.0, "I will use this knife"),
        TranscriptSegment(2.5, 4.0, "Have a nice day"),
    ]

    signals = moderator.moderate(segments)

    assert len(signals) == 1
    assert signals[0].category == "threat"
    assert signals[0].confidence == 0.85
    assert signals[0].start_timestamp == 0.0
    assert signals[0].end_timestamp == 2.0
    assert signals[0].source_text == "I will use this knife"


def test_transformer_text_moderator_inference_error_raises_ai_error() -> None:
    class BrokenPipeline:
        def __call__(self, text: str):
            raise RuntimeError("Tokenizer error")

    moderator = TransformerTextModerator(pipeline=BrokenPipeline())
    segment = TranscriptSegment(0.0, 1.0, "sample text")
    with pytest.raises(AIServiceError, match="Text moderation inference failed"):
        moderator.moderate([segment])


# ---------------------------------------------------------------------------
# 4. Factory & Selection Tests
# ---------------------------------------------------------------------------


def test_factory_returns_mock_adapters_by_default() -> None:
    settings = Settings(ai_mode="mock")
    assert isinstance(get_vision_analyzer(settings), MockVisionAnalyzer)
    assert isinstance(get_transcriber(settings), MockTranscriber)
    assert isinstance(get_text_moderator(settings), MockTextModerator)
    assert isinstance(get_context_analyzer(settings), MockContextAnalyzer)


def test_factory_returns_real_adapters_when_configured() -> None:
    settings = Settings(ai_mode="real", ai_device="cpu")
    assert isinstance(get_vision_analyzer(settings), YoloVisionAnalyzer)
    assert isinstance(get_transcriber(settings), WhisperTranscriber)
    assert isinstance(get_text_moderator(settings), TransformerTextModerator)
    assert isinstance(get_context_analyzer(settings), QwenContextAnalyzer)
