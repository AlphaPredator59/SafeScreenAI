"""Automated tests for the general-purpose temporal context analysis pipeline.

Verifies all 15 required scenarios on synthetic and multi-minute timeline inputs
without depending on external model weights or specific real-world test media files.
"""

import json
from pathlib import Path
from typing import Any
import pytest

from app.db.enums import ModerationDecision, RiskLevel
from app.services.ai.contracts import (
    ContextWindowInterpretation,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)
from app.services.ai.context import QwenContextAnalyzer
from app.services.ai.temporal import (
    DetectionSummary,
    MergedTemporalEvent,
    TemporalPipelineConfig,
    TemporalWindow,
    aggregate_window_interpretations,
    build_window_prompt,
    calculate_video_timeline_duration,
    compress_visual_detections,
    enforce_token_budget,
    estimate_tokens,
    generate_temporal_windows,
    merge_overlapping_events,
    select_representative_frames,
    select_window_transcripts,
)
from app.services.moderation.engine import ModerationEngine


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or str(json_data)

    def json(self) -> dict[str, Any]:
        return self._json_data


class FakeHttpClient:
    """Mock HTTP client recording requests and returning deterministic responses."""

    def __init__(self, responses: list[FakeResponse] | FakeResponse | None = None):
        if isinstance(responses, list):
            self.responses = list(responses)
        elif responses is not None:
            self.responses = [responses]
        else:
            self.responses = []
        self.call_history: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> FakeResponse:
        self.call_history.append(json or {})
        if self.responses:
            resp = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
            if isinstance(resp, Exception):
                raise resp
            return resp
        # Default benign mock response
        default_json = {
            "category": "educational_demonstration",
            "confidence": 0.88,
            "reasoning": "Demonstration conducted in an educational setting.",
            "evidence_references": ["frame_0001"],
        }
        return FakeResponse(status_code=200, json_data={"message": {"content": json.dumps(default_json)}})


# ---------------------------------------------------------------------------
# 1. Short Video
# ---------------------------------------------------------------------------
def test_01_short_video() -> None:
    """1. Short video (<= 30s) is processed as a single temporal window without overhead."""
    frames = [TimestampedFrame(f"f_{i}", float(i), f"storage/f_{i}.jpg") for i in range(5)]
    detections = [VisualDetection("knife", 0.9, 2.0, "f_2")]
    transcripts = [TranscriptSegment(1.0, 3.0, "Cut the apple.")]
    signals = [TextModerationSignal("clean", 0.99, 1.0, 3.0, "Cut the apple.")]

    client = FakeHttpClient(
        FakeResponse(
            status_code=200,
            json_data={
                "message": {
                    "content": json.dumps(
                        {
                            "category": "cooking_preparation",
                            "confidence": 0.95,
                            "reasoning": "Person slicing fruit in a kitchen.",
                            "evidence_references": ["f_2"],
                        }
                    )
                }
            },
        )
    )

    analyzer = QwenContextAnalyzer(client=client, allow_partial_failures=True)
    interp = analyzer.analyze(detections, transcripts, signals, frames)

    assert interp.category == "cooking_preparation"
    assert interp.confidence == 0.95
    assert len(client.call_history) == 1  # Exactly 1 request
    assert len(interp.window_interpretations) == 1
    assert interp.window_interpretations[0].start_timestamp == 0.0
    assert interp.window_interpretations[0].end_timestamp == 4.0


# ---------------------------------------------------------------------------
# 2. Approximately 7-Minute Video
# ---------------------------------------------------------------------------
def test_02_approximately_seven_minute_video() -> None:
    """2. ~7-minute video (~420s) produces multiple bounded windows within budget."""
    duration = 420.0  # 7 minutes
    config = TemporalPipelineConfig(
        window_seconds=30.0,
        overlap_seconds=5.0,
        max_windows=15,
        max_frames_per_window=3,
        max_detections_per_window=20,
        max_transcript_tokens_per_window=400,
    )

    # Synthetic detections across the timeline
    detections = [
        VisualDetection("person", 0.85, t, f"f_{int(t)}")
        for t in range(0, 420, 2)  # 210 detections
    ]
    transcripts = [
        TranscriptSegment(float(t), float(t + 4), f"Dialogue snippet at minute {t//60}")
        for t in range(0, 410, 10)  # 42 transcript segments
    ]

    windows = generate_temporal_windows(duration, detections, transcripts, (), config)

    # Windows must cover timeline and respect candidate bounds
    assert len(windows) > 1
    candidate_windows = [w for w in windows if w.is_candidate]
    assert len(candidate_windows) <= config.max_windows

    # Verify each candidate window has bounded evidence
    for w in candidate_windows:
        rep_frames = select_representative_frames(w, None, detections, max_frames=config.max_frames_per_window)
        assert len(rep_frames) <= config.max_frames_per_window
        sums = compress_visual_detections(w, detections, max_categories=config.max_detections_per_window)
        assert len(sums) <= config.max_detections_per_window
        w_trans = select_window_transcripts(w, transcripts, max_tokens=config.max_transcript_tokens_per_window)
        assert len(w_trans) <= len(transcripts)


# ---------------------------------------------------------------------------
# 3. Longer-Than-Normal Video
# ---------------------------------------------------------------------------
def test_03_longer_than_normal_video() -> None:
    """3. 15-minute video (900s) degrades gracefully and strictly caps candidate windows."""
    duration = 900.0
    config = TemporalPipelineConfig(window_seconds=30.0, overlap_seconds=5.0, max_windows=12)

    detections = [VisualDetection("car", 0.8, t, f"f_{int(t)}") for t in range(50, 850, 20)]
    windows = generate_temporal_windows(duration, detections, (), (), config)

    candidate_windows = [w for w in windows if w.is_candidate]
    assert len(candidate_windows) <= config.max_windows
    # Ensure baseline windows (start, middle, end) are preserved
    cand_indices = {w.index for w in candidate_windows}
    assert 0 in cand_indices  # Beginning preserved
    assert len(windows) - 1 in cand_indices  # End preserved


# ---------------------------------------------------------------------------
# 4. Video with Very Dense Detections
# ---------------------------------------------------------------------------
def test_04_very_dense_detections() -> None:
    """4. Thousands of detections in a single window are compressed into bounded summaries."""
    win = TemporalWindow(0, 10.0, 40.0)
    # Generate 1,500 detections in a 30s window across 3 categories
    dens_dets: list[VisualDetection] = []
    for i in range(1500):
        cat = "person" if i % 3 == 0 else ("knife" if i % 3 == 1 else "bottle")
        ts = 10.0 + (i % 30)
        dens_dets.append(VisualDetection(cat, 0.85, ts, f"f_{i}", {"box": "[10, 20, 30, 40]"}))

    summaries = compress_visual_detections(win, dens_dets, max_categories=10)

    assert len(summaries) <= 10
    person_sum = next(s for s in summaries if s.category == "person")
    assert person_sum.count == 500
    assert person_sum.first_timestamp >= 10.0
    assert person_sum.last_timestamp <= 40.0
    assert len(person_sum.key_boxes) <= 2  # Bounded bounding boxes


# ---------------------------------------------------------------------------
# 5. Video with Very Long Transcript
# ---------------------------------------------------------------------------
def test_05_very_long_transcript() -> None:
    """5. Very long transcript (hundreds of segments) is bounded per window."""
    win = TemporalWindow(0, 0.0, 30.0)
    # Create 50 overlapping segments with 20 words each = 1,000 words
    long_trans = [
        TranscriptSegment(float(i * 0.5), float(i * 0.5 + 2.0), "word " * 20)
        for i in range(50)
    ]

    bounded = select_window_transcripts(win, long_trans, max_tokens=150)

    total_words = sum(len(t.text.split()) for t in bounded)
    assert total_words <= 170  # Bounded within token limit with truncation


# ---------------------------------------------------------------------------
# 6. Video with No Transcript
# ---------------------------------------------------------------------------
def test_06_no_transcript_video() -> None:
    """6. Audio-free video with visual signals builds valid prompt and analyzes cleanly."""
    win = TemporalWindow(0, 0.0, 30.0)
    detections = [VisualDetection("knife", 0.9, 15.0, "frame_15")]
    frames = [TimestampedFrame("frame_15", 15.0, "path.jpg")]
    sums = compress_visual_detections(win, detections)

    prompt = build_window_prompt(win, sums, (), (), frames)

    assert "No spoken dialogue in this window" in prompt
    assert "knife" in prompt


# ---------------------------------------------------------------------------
# 7. Video with No Detections
# ---------------------------------------------------------------------------
def test_07_no_detections_video() -> None:
    """7. Video with only audio dialogue and no visual detections builds valid prompt."""
    win = TemporalWindow(0, 0.0, 30.0)
    trans = [TranscriptSegment(5.0, 10.0, "Audio interview dialogue.")]

    prompt = build_window_prompt(win, (), trans, (), ())

    assert "None detected in this window" in prompt
    assert "Audio interview dialogue." in prompt


# ---------------------------------------------------------------------------
# 8. Video with Many Diverse Detected Categories
# ---------------------------------------------------------------------------
def test_08_many_detections_diverse_categories() -> None:
    """8. Video with 40 distinct object classes is capped at max_detections_per_window."""
    win = TemporalWindow(0, 0.0, 30.0)
    many_dets = [
        VisualDetection(f"object_class_{i}", 0.5 + (i * 0.01), 15.0, f"f_{i}")
        for i in range(40)
    ]

    summaries = compress_visual_detections(win, many_dets, max_categories=15)
    assert len(summaries) == 15
    # Most significant items prioritized first
    assert summaries[0].max_confidence >= summaries[-1].max_confidence


# ---------------------------------------------------------------------------
# 9. Context Window Overlap
# ---------------------------------------------------------------------------
def test_09_context_window_overlap() -> None:
    """9. Adjacent temporal windows exhibit expected overlap margin."""
    config = TemporalPipelineConfig(window_seconds=30.0, overlap_seconds=5.0)
    windows = generate_temporal_windows(duration=100.0, config=config)

    assert len(windows) >= 4
    w0, w1 = windows[0], windows[1]
    assert w0.start_timestamp == 0.0
    assert w0.end_timestamp == 30.0
    assert w1.start_timestamp == 25.0  # 30.0 - 5.0 overlap
    assert w1.end_timestamp == 55.0

    # Overlap duration between w0 and w1 is exactly 5.0s
    overlap_duration = w0.end_timestamp - w1.start_timestamp
    assert pytest.approx(overlap_duration, 0.01) == 5.0


# ---------------------------------------------------------------------------
# 10. Duplicate Event Merging Across Overlapping Windows
# ---------------------------------------------------------------------------
def test_10_duplicate_event_merging() -> None:
    """10. Consecutive overlapping windows detecting the same scenario merge cleanly."""
    win_results = [
        ContextWindowInterpretation(
            start_timestamp=0.0,
            end_timestamp=30.0,
            category="cooking_demonstration",
            confidence=0.91,
            reasoning="Chef preparing ingredients.",
            evidence_references=("f_1", "f_2"),
            status="success",
        ),
        ContextWindowInterpretation(
            start_timestamp=25.0,
            end_timestamp=55.0,
            category="cooking_demonstration",
            confidence=0.94,
            reasoning="Chef sauteing vegetables in pan.",
            evidence_references=("f_2", "f_3"),
            status="success",
        ),
    ]

    merged = merge_overlapping_events(win_results)

    assert len(merged) == 1
    ev = merged[0]
    assert ev.category == "cooking_demonstration"
    assert ev.start_timestamp == 0.0
    assert ev.end_timestamp == 55.0
    assert ev.confidence == 0.94
    assert ev.evidence_references == ("f_1", "f_2", "f_3")
    assert ev.window_indices == (0, 1)


# ---------------------------------------------------------------------------
# 11. Context Model Failure Handling
# ---------------------------------------------------------------------------
def test_11_context_model_failure_handling() -> None:
    """11. Single window HTTP failure does NOT become SAFE, remaining windows continue, ModerationEngine reviews."""
    responses = [
        # Window 0 fails with HTTP 500
        FakeResponse(status_code=500, text="Ollama Timeout / Internal Error"),
        # Window 1 succeeds
        FakeResponse(
            status_code=200,
            json_data={
                "message": {
                    "content": json.dumps(
                        {
                            "category": "sports_match",
                            "confidence": 0.85,
                            "reasoning": "Regulated athletics.",
                            "evidence_references": ["f_40"],
                        }
                    )
                }
            },
        ),
    ]
    client = FakeHttpClient(responses)

    analyzer = QwenContextAnalyzer(
        client=client,
        window_seconds=30.0,
        overlap_seconds=0.0,
        allow_partial_failures=True,
    )

    detections = [
        VisualDetection("knife", 0.90, 10.0, "f_10"),
        VisualDetection("person", 0.80, 40.0, "f_40"),
    ]
    frames = [
        TimestampedFrame("f_10", 10.0, "storage/f_10.jpg"),
        TimestampedFrame("f_40", 40.0, "storage/f_40.jpg"),
    ]

    interp = analyzer.analyze(detections=detections, transcripts=(), signals=(), frames=frames)

    # Window 0 failed, Window 1 succeeded
    assert len(interp.window_interpretations) == 2
    assert interp.window_interpretations[0].status == "failed"
    assert interp.window_interpretations[1].status == "success"

    # Aggregated category must be inconclusive due to unverified failure on window with knife detection
    assert interp.category == "inconclusive"

    # ModerationEngine evaluation: must NOT be APPROVED / SAFE
    engine = ModerationEngine()
    result = engine.evaluate(detections=detections, context=interp)

    assert result.decision == ModerationDecision.REVIEW_REQUIRED
    assert result.risk_level != RiskLevel.LOW
    assert "weapons" in result.detected_categories


# ---------------------------------------------------------------------------
# 12. Input Exceeding Token Budget Proactive Reduction
# ---------------------------------------------------------------------------
def test_12_input_exceeding_token_budget_proactive_reduction() -> None:
    """12. Inputs that would blow token budget are proactively reduced before sending."""
    config = TemporalPipelineConfig(
        max_input_tokens=2500,
        image_token_cost=1200,
    )
    win = TemporalWindow(0, 0.0, 30.0)
    summaries = [DetectionSummary(f"cat_{i}", 10, 0.0, 30.0, 0.9, (), ()) for i in range(25)]
    transcripts = [TranscriptSegment(float(i), float(i + 2), "long transcript dialogue text " * 10) for i in range(15)]
    frames = [TimestampedFrame(f"f_{i}", float(i), f"path_{i}.jpg") for i in range(4)]
    images = ["base64_image_data_placeholder"] * 4

    prompt, active_images, est_tokens = enforce_token_budget(
        window=win,
        summaries=summaries,
        transcripts=transcripts,
        signals=[],
        frames=frames,
        encoded_images=images,
        config=config,
    )

    # Proactive reduction ensures budget compliance
    assert est_tokens <= config.max_input_tokens
    assert len(active_images) <= 2  # Trimmed image count to stay safely under limit


# ---------------------------------------------------------------------------
# 13. Multiple Contextual Windows with Distinct Scenarios
# ---------------------------------------------------------------------------
def test_13_multiple_contextual_windows() -> None:
    """13. Video with distinct scenarios across time captures both and prioritizes hostile finding."""
    win_results = [
        ContextWindowInterpretation(
            start_timestamp=0.0,
            end_timestamp=30.0,
            category="cooking_demonstration",
            confidence=0.92,
            reasoning="Culinary chef preparing food.",
            evidence_references=("f_1",),
            status="success",
        ),
        ContextWindowInterpretation(
            start_timestamp=60.0,
            end_timestamp=90.0,
            category="violent_altercation",
            confidence=0.89,
            reasoning="Physical fight and aggression.",
            evidence_references=("f_10",),
            status="success",
        ),
    ]

    interp = aggregate_window_interpretations(win_results, total_duration=90.0)

    # Hostile finding takes precedence in primary assessment
    assert interp.category == "violent_altercation"
    assert interp.confidence == 0.89
    assert len(interp.window_interpretations) == 2
    assert "cooking_demonstration" in interp.reasoning
    assert "violent_altercation" in interp.reasoning


# ---------------------------------------------------------------------------
# 14. Preservation of Timestamps Across Aggregation
# ---------------------------------------------------------------------------
def test_14_preservation_of_timestamps() -> None:
    """14. Window and event start/end timestamps are strictly preserved in evidence and output."""
    win_results = [
        ContextWindowInterpretation(
            start_timestamp=15.5,
            end_timestamp=45.5,
            category="carpentry_crafts",
            confidence=0.88,
            reasoning="Woodworking tutorial.",
            evidence_references=("f_15",),
            status="success",
        )
    ]

    interp = aggregate_window_interpretations(win_results, total_duration=50.0)

    assert interp.window_interpretations[0].start_timestamp == 15.5
    assert interp.window_interpretations[0].end_timestamp == 45.5
    assert "15.5s" in interp.reasoning
    assert "45.5s" in interp.reasoning


# ---------------------------------------------------------------------------
# 15. Final Moderation Aggregation Integration
# ---------------------------------------------------------------------------
def test_15_final_moderation_aggregation() -> None:
    """15. Full temporal analysis flows through ModerationEngine with multi-window evidence trace."""
    engine = ModerationEngine()
    win_results = [
        ContextWindowInterpretation(
            start_timestamp=0.0,
            end_timestamp=30.0,
            category="sports_training",
            confidence=0.90,
            reasoning="Boxing gym training session with gloves.",
            evidence_references=("f_05",),
            status="success",
        ),
        ContextWindowInterpretation(
            start_timestamp=30.0,
            end_timestamp=60.0,
            category="sports_training",
            confidence=0.92,
            reasoning="Continued sparring practice in ring.",
            evidence_references=("f_15",),
            status="success",
        ),
    ]
    interp = aggregate_window_interpretations(win_results, total_duration=60.0)

    detections = [
        VisualDetection("person", 0.90, 10.0, "f_05"),
        VisualDetection("person", 0.88, 45.0, "f_15"),
    ]

    result = engine.evaluate(detections=detections, context=interp)

    assert result.decision == ModerationDecision.APPROVED
    assert result.risk_level == RiskLevel.LOW
    assert len(result.detected_categories) == 0

    # Evidence items preserve both visual and multi-window context evidence
    context_ev = [ev for ev in result.supporting_evidence if ev.modality == "context"]
    assert len(context_ev) >= 2  # Window-level evidence preserved
