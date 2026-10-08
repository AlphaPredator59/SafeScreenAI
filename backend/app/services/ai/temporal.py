"""General-purpose temporal context analysis pipeline for SafeScreen AI.

Provides scalable temporal windowing, generic candidate event generation,
evidence compression, token budgeting, per-window analysis, and temporal aggregation.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
import math
import re
from typing import Any, Callable, Mapping, Sequence

from app.services.ai.contracts import (
    ContextWindowInterpretation,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)

logger = logging.getLogger(__name__)

# Canonical categorizations for multi-window aggregation priority
HOSTILE_KEYWORDS = (
    "threat",
    "violen",
    "altercat",
    "assault",
    "fight",
    "weapon",
    "robber",
    "hostil",
    "attack",
    "aggress",
    "harass",
    "abuse",
    "danger",
)

BENIGN_KEYWORDS = (
    "cook",
    "culinar",
    "recipe",
    "sport",
    "match",
    "game",
    "educat",
    "lecture",
    "demonstrat",
    "neutral",
    "peaceful",
    "craft",
    "woodwork",
    "science",
    "ordinar",
    "landscape",
)


@dataclass(frozen=True)
class TemporalWindow:
    """Bounded temporal slice of a video timeline."""

    index: int
    start_timestamp: float
    end_timestamp: float
    activity_score: float = 0.0
    is_candidate: bool = True
    reason: str = "scheduled"

    @property
    def duration(self) -> float:
        return max(0.0, self.end_timestamp - self.start_timestamp)


@dataclass(frozen=True)
class DetectionSummary:
    """Compressed representation of visual detections for a single category."""

    category: str
    count: int
    first_timestamp: float
    last_timestamp: float
    max_confidence: float
    key_boxes: tuple[str, ...] = ()
    key_references: tuple[str, ...] = ()


@dataclass
class WindowEvidence:
    """Structured, bounded evidence package prepared for a single temporal window."""

    window: TemporalWindow
    frames: list[TimestampedFrame] = field(default_factory=list)
    detections: list[VisualDetection] = field(default_factory=list)
    transcripts: list[TranscriptSegment] = field(default_factory=list)
    signals: list[TextModerationSignal] = field(default_factory=list)
    summaries: list[DetectionSummary] = field(default_factory=list)
    encoded_images: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TemporalPipelineConfig:
    """Configuration for temporal windowing, evidence selection, and token budgets."""

    window_seconds: float = 30.0
    overlap_seconds: float = 5.0
    max_windows: int = 15
    max_frames_per_window: int = 3
    max_detections_per_window: int = 20
    max_transcript_tokens_per_window: int = 400
    num_ctx: int = 8192
    max_input_tokens: int = 6000
    image_token_cost: int = 1200
    allow_partial_failures: bool = True


@dataclass(frozen=True)
class MergedTemporalEvent:
    """Continuous or aggregated temporal scenario spanning one or more windows."""

    category: str
    start_timestamp: float
    end_timestamp: float
    confidence: float
    reasoning: str
    evidence_references: tuple[str, ...]
    window_indices: tuple[int, ...]


# ---------------------------------------------------------------------------
# 1. Candidate Event Generation & Temporal Windowing
# ---------------------------------------------------------------------------

def calculate_video_timeline_duration(
    frames: Sequence[TimestampedFrame] | None = None,
    detections: Sequence[VisualDetection] | None = None,
    transcripts: Sequence[TranscriptSegment] | None = None,
    signals: Sequence[TextModerationSignal] | None = None,
) -> float:
    """Infer the total timeline duration across all provided multi-modal signals."""
    timestamps: list[float] = [0.0]
    for f in frames or ():
        timestamps.append(f.timestamp)
    for d in detections or ():
        timestamps.append(d.timestamp)
    for t in transcripts or ():
        timestamps.extend([t.start, t.end])
    for s in signals or ():
        timestamps.extend([s.start_timestamp, s.end_timestamp])
    return max(timestamps)


def generate_temporal_windows(
    duration: float,
    detections: Sequence[VisualDetection] = (),
    transcripts: Sequence[TranscriptSegment] = (),
    signals: Sequence[TextModerationSignal] = (),
    config: TemporalPipelineConfig | None = None,
) -> list[TemporalWindow]:
    """Divide video timeline into sliding windows and prioritize candidate regions."""
    cfg = config or TemporalPipelineConfig()
    win_sec = max(5.0, cfg.window_seconds)
    overlap = max(0.0, min(cfg.overlap_seconds, win_sec - 1.0))
    stride = max(1.0, win_sec - overlap)

    # Empty or zero-duration timeline
    if duration <= 0.0:
        return [TemporalWindow(index=0, start_timestamp=0.0, end_timestamp=0.0, activity_score=0.0, is_candidate=True, reason="zero_duration")]

    # Single short clip
    if duration <= win_sec:
        return [TemporalWindow(index=0, start_timestamp=0.0, end_timestamp=duration, activity_score=1.0, is_candidate=True, reason="single_window")]

    # Build raw sliding windows covering [0, duration]
    raw_windows: list[TemporalWindow] = []
    current_start = 0.0
    idx = 0

    while current_start < duration:
        current_end = min(duration, current_start + win_sec)

        # Gather signals overlapping this window
        win_dets = [d for d in detections if current_start <= d.timestamp <= current_end]
        win_trans = [t for t in transcripts if t.end >= current_start and t.start <= current_end]
        win_sigs = [s for s in signals if s.end_timestamp >= current_start and s.start_timestamp <= current_end]

        # Generic activity score computation
        det_score = sum(d.confidence for d in win_dets)
        unique_cats = len({d.category for d in win_dets})
        trans_score = len(win_trans) * 0.5
        sig_score = sum(s.confidence * 2.5 for s in win_sigs)
        density = len(win_dets) / max(1.0, current_end - current_start)

        activity_score = round(det_score + trans_score + sig_score + (unique_cats * 0.5) + density, 3)

        raw_windows.append(
            TemporalWindow(
                index=idx,
                start_timestamp=round(current_start, 2),
                end_timestamp=round(current_end, 2),
                activity_score=activity_score,
                is_candidate=True,
                reason="scheduled",
            )
        )
        idx += 1
        current_start += stride

    if not raw_windows:
        return [TemporalWindow(index=0, start_timestamp=0.0, end_timestamp=duration, activity_score=0.0, is_candidate=True, reason="fallback")]

    # If windows fit comfortably within max_windows
    if len(raw_windows) <= cfg.max_windows:
        return raw_windows

    # When windows exceed max_windows, prioritize candidate segments while preserving baseline context
    # Always keep first window, middle baseline, and last window to preserve narrative transitions
    reserved_indices: set[int] = {0, len(raw_windows) // 2, len(raw_windows) - 1}
    remaining_budget = max(0, cfg.max_windows - len(reserved_indices))

    # Rank non-reserved windows by activity score descending
    unreserved = [w for w in raw_windows if w.index not in reserved_indices]
    unreserved_sorted = sorted(unreserved, key=lambda w: w.activity_score, reverse=True)
    selected_from_unreserved = {w.index for w in unreserved_sorted[:remaining_budget]}

    final_selected_indices = reserved_indices | selected_from_unreserved

    # Produce final window list marking selected ones as candidate
    windows: list[TemporalWindow] = []
    for w in raw_windows:
        if w.index in final_selected_indices:
            windows.append(w)
        else:
            windows.append(
                TemporalWindow(
                    index=w.index,
                    start_timestamp=w.start_timestamp,
                    end_timestamp=w.end_timestamp,
                    activity_score=w.activity_score,
                    is_candidate=False,
                    reason="budget_pruned",
                )
            )

    return windows


# ---------------------------------------------------------------------------
# 2. Evidence Selection & Compression
# ---------------------------------------------------------------------------

def select_representative_frames(
    window: TemporalWindow,
    frames: Sequence[TimestampedFrame] | None,
    detections: Sequence[VisualDetection],
    max_frames: int = 3,
) -> list[TimestampedFrame]:
    """Select beginning, middle, end, and peak-detection frames within a window."""
    if not frames:
        return []

    # Find frames falling strictly inside window
    in_window = [f for f in frames if window.start_timestamp <= f.timestamp <= window.end_timestamp]
    if not in_window:
        # Fall back to closest available frame to window center
        center = (window.start_timestamp + window.end_timestamp) / 2.0
        closest = min(frames, key=lambda f: abs(f.timestamp - center))
        return [closest]

    if len(in_window) <= max_frames:
        return in_window

    # Key selection anchors
    beginning_frame = in_window[0]
    end_frame = in_window[-1]
    center_time = (window.start_timestamp + window.end_timestamp) / 2.0
    middle_frame = min(in_window, key=lambda f: abs(f.timestamp - center_time))

    # Peak detection frame: frame closest to highest-confidence visual detection
    win_dets = [d for d in detections if window.start_timestamp <= d.timestamp <= window.end_timestamp]
    peak_frame: TimestampedFrame | None = None
    if win_dets:
        highest_det = max(win_dets, key=lambda d: d.confidence)
        peak_frame = min(in_window, key=lambda f: abs(f.timestamp - highest_det.timestamp))

    # Assemble candidate key frames
    candidates: list[TimestampedFrame] = [beginning_frame]
    if peak_frame and peak_frame.frame_id != beginning_frame.frame_id:
        candidates.append(peak_frame)
    if middle_frame.frame_id not in {f.frame_id for f in candidates}:
        candidates.append(middle_frame)
    if end_frame.frame_id not in {f.frame_id for f in candidates}:
        candidates.append(end_frame)

    # Sort candidates chronologically and take up to max_frames
    unique_candidates: list[TimestampedFrame] = []
    seen_ids: set[str] = set()
    for f in candidates:
        if f.frame_id not in seen_ids:
            seen_ids.add(f.frame_id)
            unique_candidates.append(f)

    unique_candidates.sort(key=lambda f: f.timestamp)
    return unique_candidates[:max_frames]


def compress_visual_detections(
    window: TemporalWindow,
    detections: Sequence[VisualDetection],
    max_categories: int = 20,
) -> list[DetectionSummary]:
    """Group and compress high-density detections into compact temporal summaries."""
    in_window = [d for d in detections if window.start_timestamp <= d.timestamp <= window.end_timestamp]
    if not in_window:
        return []

    groups: dict[str, list[VisualDetection]] = defaultdict(list)
    for d in in_window:
        groups[d.category].append(d)

    summaries: list[DetectionSummary] = []
    for cat, items in groups.items():
        first_ts = min(d.timestamp for d in items)
        last_ts = max(d.timestamp for d in items)
        max_conf = max(d.confidence for d in items)

        # Extract representative boxes & references
        boxes: list[str] = []
        refs: list[str] = []
        # Sort items by confidence descending
        for item in sorted(items, key=lambda x: x.confidence, reverse=True)[:2]:
            if item.metadata.get("box"):
                boxes.append(str(item.metadata["box"]))
            refs.append(item.evidence_reference)

        summaries.append(
            DetectionSummary(
                category=cat,
                count=len(items),
                first_timestamp=round(first_ts, 2),
                last_timestamp=round(last_ts, 2),
                max_confidence=round(max_conf, 2),
                key_boxes=tuple(dict.fromkeys(boxes)),
                key_references=tuple(dict.fromkeys(refs)),
            )
        )

    # Prioritize summaries by count * max_confidence
    summaries.sort(key=lambda s: s.count * s.max_confidence, reverse=True)
    return summaries[:max_categories]


def select_window_transcripts(
    window: TemporalWindow,
    transcripts: Sequence[TranscriptSegment],
    max_tokens: int = 400,
) -> list[TranscriptSegment]:
    """Select and bound dialogue segments overlapping the temporal window."""
    overlapping = [t for t in transcripts if t.end >= window.start_timestamp and t.start <= window.end_timestamp]
    if not overlapping:
        return []

    selected: list[TranscriptSegment] = []
    word_count = 0

    for t in overlapping:
        words = t.text.split()
        if word_count + len(words) > max_tokens and selected:
            # Add truncated snippet if space remains
            rem = max(0, max_tokens - word_count)
            if rem > 3:
                snippet = " ".join(words[:rem]) + "..."
                selected.append(TranscriptSegment(start=t.start, end=t.end, text=snippet))
            break
        selected.append(t)
        word_count += len(words)

    return selected


# ---------------------------------------------------------------------------
# 3. Token Budget Estimation & Enforcement
# ---------------------------------------------------------------------------

def estimate_tokens(prompt: str, image_count: int, image_token_cost: int = 1200) -> int:
    """Conservatively estimate token count for prompt text and multimodal image patches."""
    words = len(prompt.split())
    text_tokens = int(max(words * 1.35, len(prompt) / 3.2))
    image_tokens = image_count * image_token_cost
    return text_tokens + image_tokens


def build_window_prompt(
    window: TemporalWindow,
    summaries: Sequence[DetectionSummary],
    transcripts: Sequence[TranscriptSegment],
    signals: Sequence[TextModerationSignal],
    frames: Sequence[TimestampedFrame],
) -> str:
    """Format structured, bounded timeline prompt for a specific temporal window."""
    lines = [
        f"[TEMPORAL WINDOW EVIDENCE: {window.start_timestamp:.1f}s - {window.end_timestamp:.1f}s (Index #{window.index})]"
    ]

    # 1. Visual Detection Summary
    lines.append("\n1. Visual Detections Summary (YOLO):")
    if summaries:
        for s in summaries:
            box_str = f" | Box: {s.key_boxes[0]}" if s.key_boxes else ""
            lines.append(
                f"- Category: '{s.category}' | Count: {s.count}x | Span: [{s.first_timestamp:.1f}s - {s.last_timestamp:.1f}s] | "
                f"Max Conf: {s.max_confidence:.2f} | Evidence: {','.join(s.key_references)}{box_str}"
            )
    else:
        lines.append("- None detected in this window.")

    # 2. Audio Transcript
    lines.append("\n2. Audio Dialogue Transcript (Whisper):")
    if transcripts:
        for idx, t in enumerate(transcripts):
            lines.append(f"- [{t.start:.1f}s - {t.end:.1f}s] \"{t.text}\"")
    else:
        lines.append("- No spoken dialogue in this window.")

    # 3. Text Moderation Signals
    lines.append("\n3. Text Moderation Signals:")
    if signals:
        for sig in signals:
            lines.append(
                f"- [{sig.start_timestamp:.1f}s - {sig.end_timestamp:.1f}s] Category: {sig.category} | "
                f"Confidence: {sig.confidence:.2f} | Text: \"{sig.source_text}\""
            )
    else:
        lines.append("- No text policy flags in this window.")

    # 4. Attached Frame References
    if frames:
        lines.append("\n4. Attached Frame References:")
        for f in frames:
            lines.append(f"- Frame {f.frame_id} at {f.timestamp:.1f}s")

    lines.append(
        "\nEvaluate the situational context for this temporal window. "
        "Output valid JSON with keys: category, confidence, reasoning, evidence_references."
    )
    return "\n".join(lines)


def enforce_token_budget(
    window: TemporalWindow,
    summaries: list[DetectionSummary],
    transcripts: list[TranscriptSegment],
    signals: list[TextModerationSignal],
    frames: list[TimestampedFrame],
    encoded_images: list[str],
    config: TemporalPipelineConfig,
) -> tuple[str, list[str], int]:
    """Proactively adjust evidence to strictly ensure input size is below max_input_tokens."""
    active_summaries = list(summaries)
    active_transcripts = list(transcripts)
    active_images = list(encoded_images)
    active_frames = list(frames)

    prompt = build_window_prompt(window, active_summaries, active_transcripts, signals, active_frames)
    est = estimate_tokens(prompt, len(active_images), config.image_token_cost)

    # Stage 1: Reduce image count if over budget
    while est > config.max_input_tokens and len(active_images) > 1:
        active_images.pop()
        if active_frames:
            active_frames.pop()
        prompt = build_window_prompt(window, active_summaries, active_transcripts, signals, active_frames)
        est = estimate_tokens(prompt, len(active_images), config.image_token_cost)

    # Stage 2: Reduce detection summaries to top 5
    if est > config.max_input_tokens and len(active_summaries) > 5:
        active_summaries = active_summaries[:5]
        prompt = build_window_prompt(window, active_summaries, active_transcripts, signals, active_frames)
        est = estimate_tokens(prompt, len(active_images), config.image_token_cost)

    # Stage 3: Reduce transcripts to top 2
    if est > config.max_input_tokens and len(active_transcripts) > 2:
        active_transcripts = active_transcripts[:2]
        prompt = build_window_prompt(window, active_summaries, active_transcripts, signals, active_frames)
        est = estimate_tokens(prompt, len(active_images), config.image_token_cost)

    # Stage 4: Drop all images if still exceeding budget
    if est > config.max_input_tokens and active_images:
        active_images = []
        active_frames = []
        prompt = build_window_prompt(window, active_summaries, active_transcripts, signals, active_frames)
        est = estimate_tokens(prompt, 0, config.image_token_cost)

    return prompt, active_images, est


# ---------------------------------------------------------------------------
# 4. Temporal Context Aggregation & Observability
# ---------------------------------------------------------------------------

def merge_overlapping_events(
    window_results: Sequence[ContextWindowInterpretation],
) -> list[MergedTemporalEvent]:
    """Merge adjacent or overlapping windows with matching/similar context into continuous events."""
    if not window_results:
        return []

    # Filter successful interpretations
    valid = [w for w in window_results if w.status == "success"]
    if not valid:
        return []

    merged: list[MergedTemporalEvent] = []
    current_event: MergedTemporalEvent | None = None

    def _normalize(cat: str) -> str:
        return re.sub(r"[^a-z0-9]", "", cat.lower().strip())

    for idx, w in enumerate(valid):
        w_norm = _normalize(w.category)
        if current_event is None:
            current_event = MergedTemporalEvent(
                category=w.category,
                start_timestamp=w.start_timestamp,
                end_timestamp=w.end_timestamp,
                confidence=w.confidence,
                reasoning=w.reasoning,
                evidence_references=w.evidence_references,
                window_indices=(idx,),
            )
        else:
            curr_norm = _normalize(current_event.category)
            # Check for temporal continuity and category similarity
            is_overlap_or_adjacent = w.start_timestamp <= current_event.end_timestamp + 2.0
            is_same_category = (curr_norm in w_norm) or (w_norm in curr_norm)

            if is_overlap_or_adjacent and is_same_category:
                # Merge into existing event
                combined_refs = tuple(dict.fromkeys(current_event.evidence_references + w.evidence_references))
                current_event = MergedTemporalEvent(
                    category=current_event.category,
                    start_timestamp=min(current_event.start_timestamp, w.start_timestamp),
                    end_timestamp=max(current_event.end_timestamp, w.end_timestamp),
                    confidence=max(current_event.confidence, w.confidence),
                    reasoning=f"{current_event.reasoning} | [{w.start_timestamp:.1f}s-{w.end_timestamp:.1f}s]: {w.reasoning}",
                    evidence_references=combined_refs,
                    window_indices=current_event.window_indices + (idx,),
                )
            else:
                merged.append(current_event)
                current_event = MergedTemporalEvent(
                    category=w.category,
                    start_timestamp=w.start_timestamp,
                    end_timestamp=w.end_timestamp,
                    confidence=w.confidence,
                    reasoning=w.reasoning,
                    evidence_references=w.evidence_references,
                    window_indices=(idx,),
                )

    if current_event is not None:
        merged.append(current_event)

    return merged


def aggregate_window_interpretations(
    window_results: Sequence[ContextWindowInterpretation],
    total_duration: float,
    diagnostics_meta: Mapping[str, Any] | None = None,
) -> ContextualInterpretation:
    """Aggregate individual window interpretations into a coherent platform contextual assessment."""
    if not window_results:
        return ContextualInterpretation(
            category="neutral_scene",
            confidence=1.0,
            reasoning="No visual objects, spoken dialogue, or text signals were detected in the media.",
            evidence_references=(),
            window_interpretations=(),
            diagnostics=dict(diagnostics_meta or {}),
        )

    # Identify failures
    failed_windows = [w for w in window_results if w.status == "failed"]
    success_windows = [w for w in window_results if w.status == "success"]

    # Merge events
    merged_events = merge_overlapping_events(window_results)

    # 1. Determine primary category
    # Check if any event has hostile or high-risk context
    hostile_event = next(
        (e for e in merged_events if any(h in e.category.lower() for h in HOSTILE_KEYWORDS)),
        None,
    )

    if hostile_event:
        primary_category = hostile_event.category
        primary_confidence = hostile_event.confidence
    elif failed_windows and not success_windows:
        # All windows failed
        primary_category = "inconclusive"
        primary_confidence = 0.5
    elif failed_windows and any(len(w.evidence_references) > 0 for w in failed_windows):
        # Some windows failed that had active evidence
        primary_category = "inconclusive"
        primary_confidence = 0.5
    elif success_windows:
        # Select highest-confidence event or most frequent
        best_event = max(merged_events, key=lambda e: e.confidence) if merged_events else None
        primary_category = best_event.category if best_event else success_windows[0].category
        primary_confidence = round(
            sum(w.confidence for w in success_windows) / len(success_windows),
            2,
        )
    else:
        primary_category = "neutral_scene"
        primary_confidence = 1.0

    # 2. Synthesize chronological reasoning
    reasoning_parts: list[str] = []
    if merged_events:
        for ev in merged_events:
            reasoning_parts.append(
                f"[{ev.start_timestamp:.1f}s - {ev.end_timestamp:.1f}s] Context '{ev.category}' (conf: {ev.confidence:.2f}): {ev.reasoning}"
            )
    elif success_windows:
        for w in success_windows:
            reasoning_parts.append(f"[{w.start_timestamp:.1f}s - {w.end_timestamp:.1f}s] '{w.category}': {w.reasoning}")

    if failed_windows:
        fail_spans = ", ".join(f"[{w.start_timestamp:.1f}s-{w.end_timestamp:.1f}s]" for w in failed_windows)
        reasoning_parts.append(f"Notice: Context analysis failed for window(s) {fail_spans}; treated as unverified/inconclusive.")

    synthesized_reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Timeline context evaluated as neutral."

    # 3. Collect combined evidence references
    all_refs: list[str] = []
    for w in window_results:
        all_refs.extend(w.evidence_references)
    unique_refs = tuple(dict.fromkeys(all_refs))

    # Diagnostics
    diag = dict(diagnostics_meta or {})
    diag["total_events_merged"] = len(merged_events)
    diag["total_windows_processed"] = len(window_results)
    diag["successful_windows"] = len(success_windows)
    diag["failed_windows"] = len(failed_windows)

    return ContextualInterpretation(
        category=primary_category,
        confidence=primary_confidence,
        reasoning=synthesized_reasoning,
        evidence_references=unique_refs,
        window_interpretations=tuple(window_results),
        diagnostics=diag,
    )


def format_diagnostics_report(diagnostics: Mapping[str, Any]) -> str:
    """Format structured diagnostics summary as specified in project observability requirements."""
    lines = [
        "=" * 50,
        "TEMPORAL CONTEXT PIPELINE DIAGNOSTICS",
        "=" * 50,
        "VIDEO",
        f"Duration:                  {diagnostics.get('video_duration', 0.0):.1f}s",
        "",
        "SAMPLING",
        f"Frames:                    {diagnostics.get('total_sampled_frames', 0)}",
        "",
        "SIGNALS",
        f"Detections:                {diagnostics.get('total_detections', 0):,}",
        f"Transcript segments:       {diagnostics.get('total_transcript_segments', 0)}",
        "",
        "CONTEXT",
        f"Candidate windows:         {diagnostics.get('candidate_windows', 0)}",
        f"Windows analyzed:          {diagnostics.get('context_windows_analyzed', 0)}",
        f"Windows skipped:           {diagnostics.get('context_windows_skipped', 0)}",
        f"Qwen requests:             {diagnostics.get('qwen_requests', 0)}",
        f"Max estimated tokens:      {diagnostics.get('max_estimated_input_tokens', 0)}",
        f"Context failures:          {diagnostics.get('context_failures', 0)}",
        "",
        "AGGREGATION",
        f"Events:                    {diagnostics.get('total_events_merged', 0)}",
        f"Primary Category:          {diagnostics.get('primary_category', 'N/A')}",
        f"Total Context Time:        {diagnostics.get('total_context_analysis_time', 0.0):.2f}s",
        "=" * 50,
    ]
    return "\n".join(lines)
