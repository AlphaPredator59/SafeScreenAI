"""Tests for the Qwen multimodal ContextAnalyzer adapter, prompt construction, and contract mapping."""

from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.services.ai import (
    AIServiceError,
    ContextAnalyzer,
    ContextualInterpretation,
    QwenContextAnalyzer,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
    get_context_analyzer,
)


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or str(json_data)

    def json(self) -> dict[str, Any]:
        return self._json_data


class FakeHttpClient:
    def __init__(self, response: FakeResponse | Exception):
        self.response = response
        self.last_payload: dict[str, Any] | None = None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs) -> FakeResponse:
        self.last_payload = json
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_qwen_context_analyzer_satisfies_protocol() -> None:
    analyzer = QwenContextAnalyzer()
    assert isinstance(analyzer, ContextAnalyzer)


def test_qwen_context_analyzer_empty_inputs_returns_neutral() -> None:
    analyzer = QwenContextAnalyzer()
    interpretation = analyzer.analyze([], [], [])
    assert interpretation.category == "neutral_scene"
    assert interpretation.confidence == 1.0
    assert interpretation.evidence_references == ()


def test_qwen_context_analyzer_parses_json_response_correctly(tmp_path: Path) -> None:
    frame_file = tmp_path / "frame1.jpg"
    frame_file.write_bytes(b"image_bytes")

    fake_json_output = {
        "category": "cooking_demonstration",
        "confidence": 0.92,
        "reasoning": "Person is slicing vegetables with a knife in a kitchen setting.",
        "evidence_references": ["frame_1", "transcript:0"],
    }
    fake_response = FakeResponse(
        status_code=200,
        json_data={"message": {"content": str(fake_json_output).replace("'", '"')}},
    )
    client = FakeHttpClient(fake_response)

    analyzer = QwenContextAnalyzer(client=client)

    detections = [VisualDetection("knife", 0.95, 1.0, "frame_1")]
    transcripts = [TranscriptSegment(0.0, 2.0, "Slice the vegetables carefully.")]
    signals = [TextModerationSignal("clean", 0.99, 0.0, 2.0, "Slice the vegetables carefully.")]
    frames = [TimestampedFrame("frame_1", 1.0, str(frame_file))]

    interpretation = analyzer.analyze(detections, transcripts, signals, frames)

    assert interpretation.category == "cooking_demonstration"
    assert interpretation.confidence == 0.92
    assert "slicing vegetables" in interpretation.reasoning
    assert interpretation.evidence_references == ("frame_1", "transcript:0")

    # Verify images were encoded in payload
    assert client.last_payload is not None
    user_msg = client.last_payload["messages"][1]
    assert len(user_msg["images"]) == 1


def test_qwen_context_analyzer_handles_markdown_json_wrapping() -> None:
    raw_markdown = """```json
{
  "category": "sports_event",
  "confidence": 0.88,
  "reasoning": "Boxers competing in a regulated ring.",
  "evidence_references": ["frame_5"]
}
```"""
    fake_response = FakeResponse(status_code=200, json_data={"message": {"content": raw_markdown}})
    client = FakeHttpClient(fake_response)

    analyzer = QwenContextAnalyzer(client=client)
    detections = [VisualDetection("person", 0.85, 5.0, "frame_5")]

    interpretation = analyzer.analyze(detections, [], [])
    assert interpretation.category == "sports_event"
    assert interpretation.confidence == 0.88
    assert interpretation.evidence_references == ("frame_5",)


def test_qwen_context_analyzer_handles_string_confidence() -> None:
    fake_json_output = {
        "category": "educational_tutorial",
        "confidence": "high",
        "reasoning": "Physics lecture on mechanics.",
        "evidence_references": ["frame_1"],
    }
    fake_response = FakeResponse(
        status_code=200,
        json_data={"message": {"content": str(fake_json_output).replace("'", '"')}},
    )
    client = FakeHttpClient(fake_response)

    analyzer = QwenContextAnalyzer(client=client)
    detections = [VisualDetection("whiteboard", 0.9, 1.0, "frame_1")]

    interpretation = analyzer.analyze(detections, [], [])
    assert interpretation.confidence == 0.9


def test_qwen_context_analyzer_http_error_raises_ai_error() -> None:
    fake_response = FakeResponse(status_code=500, text="Internal Server Error")
    client = FakeHttpClient(fake_response)

    analyzer = QwenContextAnalyzer(client=client)
    detections = [VisualDetection("knife", 0.9, 1.0, "frame_1")]

    with pytest.raises(AIServiceError, match="status 500"):
        analyzer.analyze(detections, [], [])


def test_qwen_context_analyzer_malformed_json_raises_ai_error() -> None:
    fake_response = FakeResponse(status_code=200, json_data={"message": {"content": "not valid json"}})
    client = FakeHttpClient(fake_response)

    analyzer = QwenContextAnalyzer(client=client)
    detections = [VisualDetection("knife", 0.9, 1.0, "frame_1")]

    with pytest.raises(AIServiceError, match="Failed to parse Qwen JSON response"):
        analyzer.analyze(detections, [], [])


def test_factory_returns_qwen_context_analyzer_when_real() -> None:
    settings = Settings(ai_mode="real", context_model_name="qwen2.5vl:7b")
    analyzer = get_context_analyzer(settings)
    assert isinstance(analyzer, QwenContextAnalyzer)
    assert analyzer.model_name == "qwen2.5vl:7b"
