"""Qwen-based multimodal context analysis engine for video moderation."""

import base64
from collections.abc import Sequence
import json
from pathlib import Path
import re
from typing import Any

from app.services.ai.contracts import (
    AIServiceError,
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)

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
    """ContextAnalyzer adapter using the local Qwen 2.5 VL multimodal model via Ollama."""

    def __init__(
        self,
        model_name: str = "qwen2.5vl:7b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        max_frames: int = 6,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_frames = max_frames
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

    def _select_key_frames(
        self,
        frames: Sequence[TimestampedFrame] | None,
        detections: Sequence[VisualDetection],
    ) -> list[TimestampedFrame]:
        if not frames:
            return []

        # Find frames that have associated visual detections
        detection_timestamps = {round(d.timestamp, 1) for d in detections}
        matched_frames: list[TimestampedFrame] = []
        other_frames: list[TimestampedFrame] = []

        for f in frames:
            if round(f.timestamp, 1) in detection_timestamps:
                matched_frames.append(f)
            else:
                other_frames.append(f)

        selected = matched_frames[: self.max_frames]
        if len(selected) < self.max_frames:
            remaining = self.max_frames - len(selected)
            # Sample evenly from remaining frames
            if other_frames:
                step = max(1, len(other_frames) // remaining)
                selected.extend(other_frames[::step][:remaining])

        return selected[: self.max_frames]

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

    def _build_user_prompt(
        self,
        detections: Sequence[VisualDetection],
        transcripts: Sequence[TranscriptSegment],
        signals: Sequence[TextModerationSignal],
        selected_frames: Sequence[TimestampedFrame],
    ) -> str:
        lines = ["[MULTIMODAL TIMELINE EVIDENCE]"]

        # 1. Visual detections
        lines.append("\n1. Visual Detections (YOLO):")
        if detections:
            for d in detections:
                box_str = f" | Box: {d.metadata.get('box')}" if d.metadata.get("box") else ""
                lines.append(
                    f"- [t={d.timestamp:.1f}s] Category: {d.category} | Confidence: {d.confidence:.2f} | Evidence: {d.evidence_reference}{box_str}"
                )
        else:
            lines.append("- None detected.")

        # 2. Audio transcripts
        lines.append("\n2. Audio Transcript (Whisper):")
        if transcripts:
            for idx, t in enumerate(transcripts):
                lines.append(f"- [{t.start:.1f}s - {t.end:.1f}s] (transcript:{idx}) \"{t.text}\"")
        else:
            lines.append("- No spoken dialogue extracted.")

        # 3. Text policy signals
        lines.append("\n3. Text Moderation Signals:")
        if signals:
            for s in signals:
                lines.append(
                    f"- [{s.start_timestamp:.1f}s - {s.end_timestamp:.1f}s] Category: {s.category} | Confidence: {s.confidence:.2f} | Text: \"{s.source_text}\""
                )
        else:
            lines.append("- No policy violations detected in text.")

        # 4. Attached frame references
        if selected_frames:
            lines.append("\n4. Attached Frame Timestamps:")
            for f in selected_frames:
                lines.append(f"- Frame {f.frame_id} at {f.timestamp:.1f}s")

        lines.append(
            "\nPlease evaluate the situational context and provide your interpretation as valid JSON with keys: category, confidence, reasoning, evidence_references."
        )
        return "\n".join(lines)

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

    def analyze(
        self,
        detections: Sequence[VisualDetection],
        transcripts: Sequence[TranscriptSegment],
        signals: Sequence[TextModerationSignal],
        frames: Sequence[TimestampedFrame] | None = None,
    ) -> ContextualInterpretation:
        """Analyze multimodal video signals and return contextual interpretation."""
        # Handle empty inputs gracefully
        if not detections and not transcripts and not signals and not frames:
            return ContextualInterpretation(
                category="neutral_scene",
                confidence=1.0,
                reasoning="No visual objects, spoken dialogue, or text signals were detected in the media.",
                evidence_references=(),
            )

        client = self._get_client()
        selected_frames = self._select_key_frames(frames, detections)

        # Encode frame images
        base64_images: list[str] = []
        for frame in selected_frames:
            encoded = self._encode_image(frame.storage_path)
            if encoded:
                base64_images.append(encoded)

        user_content = self._build_user_prompt(detections, transcripts, signals, selected_frames)

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content, "images": base64_images},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192},
        }

        try:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            if response.status_code != 200:
                raise AIServiceError(
                    f"Ollama Qwen context API returned status {response.status_code}: {response.text}"
                )
            res_data = response.json()
        except Exception as error:
            if isinstance(error, AIServiceError):
                raise
            raise AIServiceError(f"Failed to communicate with Qwen context model: {error}") from error

        raw_content = res_data.get("message", {}).get("content", "")
        if not raw_content:
            raise AIServiceError("Empty response received from Qwen context model.")

        # Clean markdown wrappers if present
        clean_json = raw_content.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
            clean_json = re.sub(r"\n?```$", "", clean_json).strip()

        try:
            parsed = json.loads(clean_json)
        except Exception as error:
            raise AIServiceError(f"Failed to parse Qwen JSON response: {error}. Raw content: {raw_content[:200]}") from error

        category = str(parsed.get("category", "unspecified_context")).strip()
        confidence = self._parse_confidence(parsed.get("confidence", 0.8))
        reasoning = str(parsed.get("reasoning", "No detailed reasoning provided.")).strip()

        raw_refs = parsed.get("evidence_references", [])
        if isinstance(raw_refs, list):
            evidence_refs = tuple(str(ref).strip() for ref in raw_refs if str(ref).strip())
        elif isinstance(raw_refs, str) and raw_refs.strip():
            evidence_refs = (raw_refs.strip(),)
        else:
            # Fallback to all detection evidence references
            evidence_refs = tuple(d.evidence_reference for d in detections)

        return ContextualInterpretation(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            evidence_references=evidence_refs,
        )
