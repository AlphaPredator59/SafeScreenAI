"""Transformer-based text moderation adapter for transcript policy signal extraction."""

from collections.abc import Sequence
from typing import Any

from app.services.ai.contracts import AIServiceError, TextModerationSignal, TranscriptSegment


class TransformerTextModerator:
    """TextModerator adapter using Hugging Face transformers classification pipelines."""

    def __init__(
        self,
        model_name: str = "unitary/toxic-bert",
        device: str = "cpu",
        confidence_threshold: float = 0.5,
        pipeline: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._pipeline = pipeline

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from transformers import pipeline

            device_id = 0 if str(self.device).lower().startswith("cuda") else -1
            self._pipeline = pipeline(
                "text-classification",
                model=self.model_name,
                device=device_id,
                top_k=None,
            )
            return self._pipeline
        except Exception as error:
            raise AIServiceError(f"Failed to load text moderation model '{self.model_name}': {error}") from error

    def moderate(self, segments: Sequence[TranscriptSegment]) -> list[TextModerationSignal]:
        """Analyze a sequence of transcript segments and extract moderation signals."""
        if not segments:
            return []

        pipe = self._get_pipeline()
        signals: list[TextModerationSignal] = []

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue

            try:
                raw_output = pipe(text)
            except Exception as error:
                raise AIServiceError(f"Text moderation inference failed for '{text[:50]}...': {error}") from error

            # Normalize HuggingFace outputs (can be list of dicts, list of list of dicts, or dict)
            items: list[dict[str, Any]] = []
            if isinstance(raw_output, list):
                for element in raw_output:
                    if isinstance(element, list):
                        items.extend(item for item in element if isinstance(item, dict))
                    elif isinstance(element, dict):
                        items.append(element)
            elif isinstance(raw_output, dict):
                items.append(raw_output)

            for item in items:
                try:
                    label = str(item.get("label", "unknown")).lower()
                    score = float(item.get("score", 0.0))
                    score = min(max(score, 0.0), 1.0)

                    # Filter benign labels or below-threshold scores
                    # If the model has standard binary labels like non-toxic / neutral, we ignore them if score is for non-toxic
                    if label in {"non-toxic", "neutral", "clean", "benign", "normal"}:
                        continue

                    if score >= self.confidence_threshold:
                        signals.append(
                            TextModerationSignal(
                                category=label,
                                confidence=score,
                                start_timestamp=segment.start,
                                end_timestamp=segment.end,
                                source_text=segment.text,
                            )
                        )
                except Exception as error:
                    raise AIServiceError(f"Failed to parse text moderation output: {error}") from error

        return signals
