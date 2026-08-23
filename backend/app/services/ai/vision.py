"""YOLO-based computer vision adapter for object and visual safety detection."""

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

from app.services.ai.contracts import AIServiceError, TimestampedFrame, VisualDetection


class YoloVisionAnalyzer:
    """VisionAnalyzer adapter using Ultralytics YOLO models."""

    def __init__(
        self,
        model_name_or_path: str = "yolov8n.pt",
        device: str = "cpu",
        confidence_threshold: float = 0.25,
        model: Any | None = None,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._model = model

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.model_name_or_path)
            return self._model
        except Exception as error:
            raise AIServiceError(f"Failed to load YOLO model '{self.model_name_or_path}': {error}") from error

    def analyze(self, frames: Sequence[TimestampedFrame]) -> list[VisualDetection]:
        """Analyze a sequence of timestamped video frames."""
        if not frames:
            return []

        for frame in frames:
            if not Path(frame.storage_path).exists():
                raise AIServiceError(f"Frame image not found at storage path: {frame.storage_path}")

        model = self._get_model()
        detections: list[VisualDetection] = []

        for frame in frames:
            frame_path = Path(frame.storage_path)
            try:
                results = model.predict(
                    source=str(frame_path),
                    conf=self.confidence_threshold,
                    device=self.device,
                    verbose=False,
                )
            except Exception as error:
                raise AIServiceError(f"Vision inference failed for frame {frame.frame_id}: {error}") from error

            for result in results:
                boxes = getattr(result, "boxes", None)
                if boxes is None:
                    continue

                for box in boxes:
                    try:
                        cls_id = int(box.cls[0].item() if hasattr(box.cls[0], "item") else box.cls[0])
                        names = getattr(model, "names", {})
                        category = names.get(cls_id, str(cls_id))
                        conf = float(box.conf[0].item() if hasattr(box.conf[0], "item") else box.conf[0])
                        conf = min(max(conf, 0.0), 1.0)

                        xyxy = box.xyxy[0].tolist() if hasattr(box.xyxy[0], "tolist") else list(box.xyxy[0])
                        metadata = {"box": json.dumps([round(float(coord), 2) for coord in xyxy])}

                        detections.append(
                            VisualDetection(
                                category=category,
                                confidence=conf,
                                timestamp=frame.timestamp,
                                evidence_reference=frame.frame_id,
                                metadata=metadata,
                            )
                        )
                    except Exception as error:
                        raise AIServiceError(f"Failed to parse vision model detection output: {error}") from error

        return detections
