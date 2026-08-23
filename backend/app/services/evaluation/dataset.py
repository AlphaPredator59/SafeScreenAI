"""Evaluation dataset models and loaders for SafeScreen AI benchmarking."""

import json
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ModerationDecision, RiskLevel


class ModalityAvailability(BaseModel):
    """Flags indicating which modalities are present in the evaluation sample."""

    model_config = ConfigDict(from_attributes=True)

    visual: bool = True
    audio: bool = False
    transcript: bool = False


class GroundTruth(BaseModel):
    """Ground truth expectations for a benchmark scenario."""

    model_config = ConfigDict(from_attributes=True)

    expected_context: str
    expected_decision: ModerationDecision
    expected_risk_level: RiskLevel
    expected_policy_categories: list[str] = Field(default_factory=list)
    acceptable_policy_alternatives: list[list[str]] = Field(default_factory=list)


class EvaluationSample(BaseModel):
    """An individual test sample within the evaluation dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_name: str
    local_path: str | None = None
    available: bool = False
    modalities: ModalityAvailability = Field(default_factory=ModalityAvailability)
    ground_truth: GroundTruth
    notes: str = ""

    def resolve_video_path(self, base_dir: Path | None = None) -> Path | None:
        """Resolve the local video path if available on disk."""
        if not self.local_path:
            return None
        candidate = Path(self.local_path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        if base_dir:
            joined = (base_dir / candidate).resolve()
            if joined.exists():
                return joined
        if candidate.exists():
            return candidate.resolve()
        return None


class EvaluationDataset(BaseModel):
    """Collection of evaluation samples with metadata."""

    model_config = ConfigDict(from_attributes=True)

    version: str = "1.0.0"
    description: str = "SafeScreen AI Benchmark Evaluation Dataset"
    samples: list[EvaluationSample] = Field(default_factory=list)

    @classmethod
    def load_from_file(cls, path: Path | str) -> "EvaluationDataset":
        """Load and validate an evaluation dataset from a JSON file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Evaluation dataset file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def save_to_file(self, path: Path | str) -> None:
        """Save the evaluation dataset to a JSON file."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)

    def get_available_samples(self, base_dir: Path | None = None) -> list[EvaluationSample]:
        """Return only samples whose media files are confirmed available on disk."""
        available: list[EvaluationSample] = []
        for s in self.samples:
            if s.available and s.resolve_video_path(base_dir) is not None:
                available.append(s)
        return available

    def get_unavailable_samples(self, base_dir: Path | None = None) -> list[EvaluationSample]:
        """Return placeholder or missing samples."""
        unavailable: list[EvaluationSample] = []
        for s in self.samples:
            if not s.available or s.resolve_video_path(base_dir) is None:
                unavailable.append(s)
        return unavailable
