"""Qwen-based multimodal context analysis engine for video moderation."""

import base64
from collections.abc import Sequence
import json
import logging
from pathlib import Path
import re
import time
from typing import Any

from app.services.ai.contracts import (
    AIServiceError,
    ContextWindowInterpretation,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)
from app.services.ai.temporal import (
    DetectionSummary,
    TemporalPipelineConfig,
    TemporalWindow,
    aggregate_window_interpretations,
    calculate_video_timeline_duration,
    compress_visual_detections,
    enforce_token_budget,
    format_diagnostics_report,
    generate_temporal_windows,
    select_representative_frames,
    select_window_transcripts,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SafeScreen AI's Multimodal Context Analysis Engine.
Your task is to analyze the situational context and meaning of an uploaded video by synthesizing:
1. Visual object detections and attached video frames
2. Audio transcripts of spoken dialogue
3. Text policy moderation signals

Guidelines:
- Evaluate the context and scenario (e.g. cooking tutorial, sports match, carpentry/crafts, educational lecture, movie acting, threatening altercation, violent interaction).
- Distinguish between benign interactions (e.g. using a knife to chop food) and harmful interactions (e.g. using a knife to threaten someone).
- Do NOT make platform-level moderation decisions (such as APPROVED or REJECTED).
- Base reasoning only on the provided evidence; do not fabricate evidence or detections.
- Cite the relevant evidence references (frame IDs, detection items, or transcript segment indices).
- Output valid JSON with keys:
  "category": str (a concise description of the contextual scenario),
  "confidence": float (between 0.0 and 1.0),
  "reasoning": str (concise explanation of why the evidence indicates this context),
  "evidence_references": list[str] (list of cited evidence references).
"""


class QwenContextAnalyzer:
    """Temporal multimodal ContextAnalyzer adapter using local Qwen 2.5 VL via Ollama."""

    def __init__(
        self,
        model_name: str = "qwen2.5vl:7b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        max_frames: int = 3,
        num_ctx: int = 8192,
        max_input_tokens: int = 6000,
        window_seconds: float = 30.0,
        overlap_seconds: float = 5.0,
        max_windows: int = 15,
        max_detections_per_window: int = 20,
        max_transcript_tokens_per_window: int = 400,
        allow_partial_failures: bool = False,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_frames = max_frames
        self.num_ctx = num_ctx
        self.max_input_tokens = max_input_tokens
        self.window_seconds = window_seconds
        self.overlap_seconds = overlap_seconds
        self.max_windows = max_windows
        self.max_detections_per_window = max_detections_per_window
        self.max_transcript_tokens_per_window = max_transcript_tokens_per_window
        self.allow_partial_failures = allow_partial_failures
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import httpx

            self._client = httpx.Client(timeout=self.timeout_seconds)
            return self._client
        except Exception as error:
            raise AIServiceError(f"Failed to initialize HTTP client for Qwen: {error}") from error

    def _encode_image(self, path_str: str, max_dimension: int = 768) -> str:
        path = Path(path_str)
        if not path.exists():
            return ""
        try:
            import io
            from PIL import Image

            with Image.open(path) as img:
                if max(img.size) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img_format = img.format or "JPEG"
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    img_format = "JPEG"
                img.save(buffer, format=img_format, quality=85)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception:
            try:
                return base64.b64encode(path.read_bytes()).decode("utf-8")
            except OSError:
                return ""

    @staticmethod
    def _parse_confidence(val: Any) -> float:
        if isinstance(val, (int, float)):
            return min(max(float(val), 0.0), 1.0)
        if isinstance(val, str):
            val_clean = val.strip().lower()
            if val_clean == "high":
                return 0.9
            if val_clean == "medium":
                return 0.6
            if val_clean == "low":
                return 0.3
            try:
                parsed = float(val_clean)
                return min(max(parsed, 0.0), 1.0)
            except ValueError:
                pass
        return 0.8  # Default sensible confidence if unspecified

    def _analyze_single_window(
        self,
        window: TemporalWindow,
        summaries: list[DetectionSummary],
        transcripts: list[TranscriptSegment],
        signals: list[TextModerationSignal],
        frames: list[TimestampedFrame],
        config: TemporalPipelineConfig,
    ) -> tuple[ContextWindowInterpretation, int]:
        """Send a single bounded temporal window to Qwen and parse the interpretation."""
        client = self._get_client()

        # Encode frame images
        base64_images: list[str] = []
        for frame in frames:
            encoded = self._encode_image(frame.storage_path)
            if encoded:
                base64_images.append(encoded)

        # Proactively enforce token budget
        user_content, active_images, est_tokens = enforce_token_budget(
            window=window,
            summaries=summaries,
            transcripts=transcripts,
            signals=signals,
            frames=frames,
            encoded_images=base64_images,
            config=config,
        )

        effective_num_ctx = config.num_ctx if (config and getattr(config, "num_ctx", None)) else self.num_ctx
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content, "images": active_images},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": effective_num_ctx, "num_predict": 1024},
        }


        try:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            if response.status_code != 200:
                raise AIServiceError(
                    f"Ollama Qwen context API returned status {response.status_code}: {response.text}"
                )
            res_data = response.json()
        except Exception as error:
            if not self.allow_partial_failures:
                if isinstance(error, AIServiceError):
                    raise
                raise AIServiceError(f"Failed to communicate with Qwen context model: {error}") from error

            # Gracefully handle single-window failure in resilient mode
            logger.warning("Qwen context request failed for window [%.1f-%.1f]: %s", window.start_timestamp, window.end_timestamp, error)
            fallback_refs = tuple(
                [f.frame_id for f in frames]
                + [ref for s in summaries for ref in s.key_references]
            )
            return ContextWindowInterpretation(
                start_timestamp=window.start_timestamp,
                end_timestamp=window.end_timestamp,
                category="inconclusive",
                confidence=0.5,
                reasoning=f"Context request failed: {error}",
                evidence_references=fallback_refs,
                status="failed",
            ), est_tokens

        raw_content = res_data.get("message", {}).get("content", "")
        if not raw_content:
            if not self.allow_partial_failures:
                raise AIServiceError("Empty response received from Qwen context model.")
            return ContextWindowInterpretation(
                start_timestamp=window.start_timestamp,
                end_timestamp=window.end_timestamp,
                category="inconclusive",
                confidence=0.5,
                reasoning="Empty response received from Qwen context model.",
                evidence_references=(),
                status="failed",
            ), est_tokens

        # Clean markdown wrappers if present
        clean_json = raw_content.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
            clean_json = re.sub(r"\n?```$", "", clean_json).strip()

        parsed: dict[str, Any] | None = None
        try:
            parsed = json.loads(clean_json)
        except Exception:
            # Resilient regex fallback extraction
            cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', raw_content)
            conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', raw_content)
            reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', raw_content)
            refs_match = re.findall(r'"(frame_[a-zA-Z0-9_]+|transcript:[0-9]+)"', raw_content)
            if cat_match:
                parsed = {
                    "category": cat_match.group(1),
                    "confidence": float(conf_match.group(1)) if conf_match else 0.8,
                    "reasoning": reasoning_match.group(1) if reasoning_match else "Extracted contextual reasoning.",
                    "evidence_references": refs_match,
                }
            else:
                if not self.allow_partial_failures:
                    raise AIServiceError(f"Failed to parse Qwen JSON response. Raw content: {raw_content[:200]}")
                return ContextWindowInterpretation(
                    start_timestamp=window.start_timestamp,
                    end_timestamp=window.end_timestamp,
                    category="inconclusive",
                    confidence=0.5,
                    reasoning=f"Malformed JSON from Qwen: {raw_content[:150]}",
                    evidence_references=(),
                    status="failed",
                ), est_tokens

        category = str(parsed.get("category", "unspecified_context")).strip()
        confidence = self._parse_confidence(parsed.get("confidence", 0.8))
        reasoning = str(parsed.get("reasoning", "No detailed reasoning provided.")).strip()

        raw_refs = parsed.get("evidence_references", [])
        if isinstance(raw_refs, list):
            evidence_refs = tuple(str(ref).strip() for ref in raw_refs if str(ref).strip())
        elif isinstance(raw_refs, str) and raw_refs.strip():
            evidence_refs = (raw_refs.strip(),)
        else:
            evidence_refs = tuple(ref for s in summaries for ref in s.key_references)

        return ContextWindowInterpretation(
            start_timestamp=window.start_timestamp,
            end_timestamp=window.end_timestamp,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            evidence_references=evidence_refs,
            status="success",
        ), est_tokens

    def analyze(
        self,
        detections: Sequence[VisualDetection],
        transcripts: Sequence[TranscriptSegment],
        signals: Sequence[TextModerationSignal],
        frames: Sequence[TimestampedFrame] | None = None,
    ) -> ContextualInterpretation:
        """Analyze multimodal video signals across temporal windows and aggregate context."""
        start_time = time.perf_counter()

        # Handle empty inputs gracefully
        if not detections and not transcripts and not signals and not frames:
            return ContextualInterpretation(
                category="neutral_scene",
                confidence=1.0,
                reasoning="No visual objects, spoken dialogue, or text signals were detected in the media.",
                evidence_references=(),
            )

        pipeline_config = TemporalPipelineConfig(
            window_seconds=self.window_seconds,
            overlap_seconds=self.overlap_seconds,
            max_windows=self.max_windows,
            max_frames_per_window=self.max_frames,
            max_detections_per_window=self.max_detections_per_window,
            max_transcript_tokens_per_window=self.max_transcript_tokens_per_window,
            num_ctx=self.num_ctx,
            max_input_tokens=self.max_input_tokens,
            allow_partial_failures=self.allow_partial_failures,
        )

        total_duration = calculate_video_timeline_duration(frames, detections, transcripts, signals)
        windows = generate_temporal_windows(
            duration=total_duration,
            detections=detections,
            transcripts=transcripts,
            signals=signals,
            config=pipeline_config,
        )

        candidate_windows = [w for w in windows if w.is_candidate]
        skipped_windows = [w for w in windows if not w.is_candidate]

        window_results: list[ContextWindowInterpretation] = []
        qwen_requests = 0
        max_estimated_tokens = 0
        context_failures = 0

        for win in windows:
            if not win.is_candidate or win.activity_score == 0.0:
                # Resolve non-candidate / zero-activity windows without calling Qwen
                # If there are truly no signals in this window, treat as neutral
                win_dets = [d for d in detections if win.start_timestamp <= d.timestamp <= win.end_timestamp]
                win_trans = [t for t in transcripts if t.end >= win.start_timestamp and t.start <= win.end_timestamp]
                win_sigs = [s for s in signals if s.end_timestamp >= win.start_timestamp and s.start_timestamp <= win.end_timestamp]

                if not win_dets and not win_trans and not win_sigs:
                    window_results.append(
                        ContextWindowInterpretation(
                            start_timestamp=win.start_timestamp,
                            end_timestamp=win.end_timestamp,
                            category="neutral_scene",
                            confidence=1.0,
                            reasoning="No visual objects, spoken dialogue, or text signals detected in this interval.",
                            evidence_references=(),
                            status="skipped",
                        )
                    )
                    continue

            # Active candidate window: prepare bounded evidence
            rep_frames = select_representative_frames(win, frames, detections, max_frames=self.max_frames)
            win_summaries = compress_visual_detections(win, detections, max_categories=self.max_detections_per_window)
            win_transcripts = select_window_transcripts(win, transcripts, max_tokens=self.max_transcript_tokens_per_window)
            win_signals = [s for s in signals if s.end_timestamp >= win.start_timestamp and s.start_timestamp <= win.end_timestamp]

            qwen_requests += 1
            win_interp, est_toks = self._analyze_single_window(
                window=win,
                summaries=win_summaries,
                transcripts=win_transcripts,
                signals=win_signals,
                frames=rep_frames,
                config=pipeline_config,
            )
            max_estimated_tokens = max(max_estimated_tokens, est_toks)
            if win_interp.status == "failed":
                context_failures += 1

            window_results.append(win_interp)

        elapsed = time.perf_counter() - start_time

        # Diagnostics telemetry
        diagnostics = {
            "video_duration": round(total_duration, 2),
            "total_sampled_frames": len(frames or ()),
            "total_detections": len(detections),
            "total_transcript_segments": len(transcripts),
            "candidate_windows": len(candidate_windows),
            "context_windows_analyzed": qwen_requests,
            "context_windows_skipped": len(windows) - qwen_requests,
            "qwen_requests": qwen_requests,
            "max_estimated_input_tokens": max_estimated_tokens,
            "context_failures": context_failures,
            "total_context_analysis_time": round(elapsed, 2),
        }

        aggregated = aggregate_window_interpretations(
            window_results=window_results,
            total_duration=total_duration,
            diagnostics_meta=diagnostics,
        )

        diagnostics["primary_category"] = aggregated.category
        logger.info("\n%s", format_diagnostics_report(diagnostics))

        return aggregated
