"""Orchestrator for executing SafeScreen AI pipeline evaluations and ablation studies."""

from collections import defaultdict
from pathlib import Path
import time
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.db.enums import ModerationDecision, RiskLevel
from app.db.models import Video
from app.services.ai.contracts import (
    ContextualInterpretation,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    VisualDetection,
)
from app.services.ai.factory import (
    get_context_analyzer,
    get_text_moderator,
    get_transcriber,
    get_vision_analyzer,
)
from app.services.evaluation.dataset import EvaluationDataset, EvaluationSample, GroundTruth
from app.services.evaluation.metrics import (
    BinaryMetrics,
    CategoryMetric,
    ConfusionMatrix,
    ContextMetrics,
    ErrorAnalysisItem,
    EvaluationSummaryMetrics,
    LatencyMetrics,
    ModelDisagreement,
    calculate_binary_metrics,
    calculate_latency_stat,
    is_unsafe,
    match_context_category,
)
from app.services.moderation import ModerationConfig, ModerationEngine, ModerationResult
from app.services.video.metadata import VideoMetadata, VideoMetadataService
from app.services.video.processing import (
    AudioArtifact,
    AudioProcessingService,
    FrameArtifact,
    FrameProcessingService,
)
from app.services.video.storage import LocalStorageService


class SampleEvaluationResult(BaseModel):
    """Detailed prediction record for an evaluation sample."""

    model_config = ConfigDict(from_attributes=True)

    sample_id: str
    scenario_name: str
    video_path: str | None = None
    status: str = "EVALUATED"  # EVALUATED, UNAVAILABLE, FAILED
    ablation_mode: str = "full"
    ground_truth: GroundTruth
    predicted_decision: ModerationDecision | None = None
    predicted_risk_level: RiskLevel | None = None
    predicted_risk_score: float | None = None
    predicted_overall_confidence: float | None = None
    predicted_context: str | None = None
    predicted_context_confidence: float | None = None
    predicted_policy_categories: list[str] = Field(default_factory=list)
    yolo_categories: list[str] = Field(default_factory=list)
    transcripts: list[str] = Field(default_factory=list)
    text_signals: list[str] = Field(default_factory=list)
    explanation: str | None = None
    stage_latencies: dict[str, float] = Field(default_factory=dict)
    total_latency: float = 0.0
    video_metadata: dict[str, Any] = Field(default_factory=dict)
    is_correct_decision: bool = False
    is_correct_context: bool = False
    is_correct_policy: bool = False
    error_message: str | None = None


class EvaluationRunner:
    """Runs evaluation benchmark suites and ablation tests across the SafeScreen AI pipeline."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage_dir = storage_dir or (Path(__file__).resolve().parents[3] / "storage")
        self.storage = LocalStorageService(root_path=self.storage_dir)

    def run_sample(
        self,
        sample: EvaluationSample,
        ablation_mode: str = "full",
        base_dir: Path | None = None,
    ) -> SampleEvaluationResult:
        """Run a single sample through the pipeline in the specified ablation mode."""
        resolved_path = sample.resolve_video_path(base_dir)
        if not sample.available or resolved_path is None or not resolved_path.exists():
            return SampleEvaluationResult(
                sample_id=sample.id,
                scenario_name=sample.scenario_name,
                video_path=sample.local_path,
                status="UNAVAILABLE",
                ablation_mode=ablation_mode,
                ground_truth=sample.ground_truth,
                error_message="Media file not found or marked unavailable.",
            )

        stage_times: dict[str, float] = {}
        t_total_start = time.perf_counter()

        try:
            # 1. Metadata extraction
            t0 = time.perf_counter()
            metadata_service = VideoMetadataService()
            metadata = metadata_service.extract(resolved_path)
            stage_times["metadata"] = round(time.perf_counter() - t0, 4)

            # Build in-memory video record
            video_model = Video(
                id=f"eval_{sample.id}",
                filename=resolved_path.name,
                storage_path=str(resolved_path.resolve()),
                duration=metadata.duration,
                file_size=resolved_path.stat().st_size,
                width=metadata.width,
                height=metadata.height,
                fps=metadata.fps,
            )

            # 2. Frame sampling & processing
            t0 = time.perf_counter()
            frame_service = FrameProcessingService(
                storage=self.storage,
                interval_seconds=self.settings.frame_sampling_interval_seconds,
                image_format=self.settings.frame_image_format,
                quality=self.settings.frame_image_quality,
            )
            frame_artifacts = frame_service.extract(video_model)
            timestamped_frames = [
                TimestampedFrame(
                    frame_id=fa.frame_id,
                    timestamp=fa.timestamp,
                    storage_path=str(fa.storage_path.resolve()),
                )
                for fa in frame_artifacts
            ]
            stage_times["frame_processing"] = round(time.perf_counter() - t0, 4)

            # 3. Vision analysis (YOLO)
            t0 = time.perf_counter()
            vision_analyzer = get_vision_analyzer(self.settings)
            detections = vision_analyzer.analyze(timestamped_frames)
            stage_times["vision_yolo"] = round(time.perf_counter() - t0, 4)
            yolo_classes = sorted(list({d.category for d in detections}))

            # 4. Audio extraction & transcription (Whisper)
            transcripts: list[TranscriptSegment] = []
            if ablation_mode in ("full", "visual_audio"):
                t0 = time.perf_counter()
                audio_service = AudioProcessingService(storage=self.storage, output_format=self.settings.audio_output_format)
                audio_artifact = audio_service.extract(video_model)
                stage_times["audio_extraction"] = round(time.perf_counter() - t0, 4)

                t0 = time.perf_counter()
                transcriber = get_transcriber(self.settings)
                transcripts = transcriber.transcribe(audio_artifact)
                stage_times["transcription_whisper"] = round(time.perf_counter() - t0, 4)
            else:
                stage_times["audio_extraction"] = 0.0
                stage_times["transcription_whisper"] = 0.0

            # 5. Text moderation
            text_signals: list[TextModerationSignal] = []
            if ablation_mode in ("full", "visual_audio") and transcripts:
                t0 = time.perf_counter()
                text_moderator = get_text_moderator(self.settings)
                text_signals = text_moderator.moderate(transcripts)
                stage_times["text_moderation"] = round(time.perf_counter() - t0, 4)
            else:
                stage_times["text_moderation"] = 0.0

            # 6. Context analysis (Qwen 2.5 VL)
            context: ContextualInterpretation | None = None
            if ablation_mode in ("full", "visual_qwen"):
                t0 = time.perf_counter()
                context_analyzer = get_context_analyzer(self.settings)
                context = context_analyzer.analyze(
                    detections=detections,
                    transcripts=transcripts,
                    signals=text_signals,
                    frames=timestamped_frames,
                )
                stage_times["context_qwen"] = round(time.perf_counter() - t0, 4)
            else:
                # Deterministic fallback for missing context in ablation mode
                context = ContextualInterpretation(
                    category="unspecified_scene",
                    confidence=0.0,
                    reasoning=f"Context disabled in ablation mode '{ablation_mode}'.",
                    evidence_references=(),
                )
                stage_times["context_qwen"] = 0.0

            # 7. Moderation decision engine
            t0 = time.perf_counter()
            mod_config = ModerationConfig(
                low_risk_threshold=self.settings.moderation_low_risk_threshold,
                medium_risk_threshold=self.settings.moderation_medium_risk_threshold,
                high_risk_threshold=self.settings.moderation_high_risk_threshold,
                auto_reject_threshold=self.settings.moderation_auto_reject_threshold,
                review_threshold=self.settings.moderation_review_threshold,
                min_signal_confidence=self.settings.moderation_min_signal_confidence,
            )
            engine = ModerationEngine(config=mod_config)
            result = engine.evaluate(
                detections=detections,
                transcripts=transcripts,
                text_signals=text_signals,
                context=context,
            )
            stage_times["moderation_engine"] = round(time.perf_counter() - t0, 4)

            total_lat = round(time.perf_counter() - t_total_start, 4)

            # Ground truth evaluation
            is_correct_dec = (result.decision == sample.ground_truth.expected_decision)
            pred_ctx = context.category if context else "None"
            is_correct_ctx = match_context_category(sample.ground_truth.expected_context, pred_ctx)

            # Policy matching check
            exp_policies = set(sample.ground_truth.expected_policy_categories)
            pred_policies = set(result.detected_categories)
            is_correct_pol = (exp_policies == pred_policies)
            if not is_correct_pol and sample.ground_truth.acceptable_policy_alternatives:
                for alt in sample.ground_truth.acceptable_policy_alternatives:
                    if set(alt) == pred_policies:
                        is_correct_pol = True
                        break

            return SampleEvaluationResult(
                sample_id=sample.id,
                scenario_name=sample.scenario_name,
                video_path=str(resolved_path),
                status="EVALUATED",
                ablation_mode=ablation_mode,
                ground_truth=sample.ground_truth,
                predicted_decision=result.decision,
                predicted_risk_level=result.risk_level,
                predicted_risk_score=result.risk_score,
                predicted_overall_confidence=result.overall_confidence,
                predicted_context=pred_ctx,
                predicted_context_confidence=context.confidence if context else 0.0,
                predicted_policy_categories=list(result.detected_categories),
                yolo_categories=yolo_classes,
                transcripts=[t.text for t in transcripts],
                text_signals=[s.category for s in text_signals],
                explanation=result.explanation,
                stage_latencies=stage_times,
                total_latency=total_lat,
                video_metadata={
                    "duration": metadata.duration,
                    "resolution": f"{metadata.width}x{metadata.height}",
                    "fps": metadata.fps,
                    "frame_count": metadata.frame_count,
                    "sampled_frames": len(timestamped_frames),
                },
                is_correct_decision=is_correct_dec,
                is_correct_context=is_correct_ctx,
                is_correct_policy=is_correct_pol,
            )

        except Exception as exc:
            total_lat = round(time.perf_counter() - t_total_start, 4)
            return SampleEvaluationResult(
                sample_id=sample.id,
                scenario_name=sample.scenario_name,
                video_path=str(resolved_path) if resolved_path else sample.local_path,
                status="FAILED",
                ablation_mode=ablation_mode,
                ground_truth=sample.ground_truth,
                stage_latencies=stage_times,
                total_latency=total_lat,
                error_message=f"Evaluation failed during pipeline execution: {exc}",
            )

    def evaluate_dataset(
        self,
        dataset: EvaluationDataset,
        ablation_mode: str = "full",
        base_dir: Path | None = None,
    ) -> tuple[list[SampleEvaluationResult], EvaluationSummaryMetrics]:
        """Run all samples in the dataset and compile headline metrics."""
        results: list[SampleEvaluationResult] = []
        for sample in dataset.samples:
            res = self.run_sample(sample, ablation_mode=ablation_mode, base_dir=base_dir)
            results.append(res)

        summary = self.calculate_summary(dataset, results)
        return results, summary

    def calculate_summary(
        self,
        dataset: EvaluationDataset,
        results: Sequence[SampleEvaluationResult],
    ) -> EvaluationSummaryMetrics:
        """Compute headline evaluation metrics strictly over available evaluated samples."""
        total_samples = len(dataset.samples)
        evaluated_results = [r for r in results if r.status == "EVALUATED"]
        unavailable_results = [r for r in results if r.status == "UNAVAILABLE"]

        eval_pairs: list[tuple[ModerationDecision | str, ModerationDecision | str]] = []
        multiclass_pairs: list[tuple[str, str]] = []
        binary_pairs: list[tuple[str, str]] = []

        context_correct = 0
        context_evaluated = 0
        disagreements: list[ModelDisagreement] = []
        errors: list[ErrorAnalysisItem] = []

        # Stage latency lists
        stage_times_map: dict[str, list[float]] = defaultdict(list)
        total_times: list[float] = []

        # Policy category tracking
        policy_all_categories = {"violence", "threats", "weapons", "toxic_language", "hate_speech", "child_safety"}
        tp_cat = defaultdict(int)
        fp_cat = defaultdict(int)
        fn_cat = defaultdict(int)
        supp_cat = defaultdict(int)

        for r in evaluated_results:
            exp_dec = r.ground_truth.expected_decision
            pred_dec = r.predicted_decision or ModerationDecision.APPROVED
            eval_pairs.append((exp_dec, pred_dec))

            multiclass_pairs.append((exp_dec.value, pred_dec.value))
            binary_pairs.append(
                ("UNSAFE" if is_unsafe(exp_dec) else "SAFE", "UNSAFE" if is_unsafe(pred_dec) else "SAFE")
            )

            # Context accuracy
            if r.predicted_context and r.predicted_context != "unspecified_scene":
                context_evaluated += 1
                if r.is_correct_context:
                    context_correct += 1

            # Latencies
            total_times.append(r.total_latency)
            for st_name, st_val in r.stage_latencies.items():
                stage_times_map[st_name].append(st_val)

            # Policy categories evaluation
            exp_pols = set(r.ground_truth.expected_policy_categories)
            pred_pols = set(r.predicted_policy_categories)
            for c in policy_all_categories:
                if c in exp_pols and c in pred_pols:
                    tp_cat[c] += 1
                elif c not in exp_pols and c in pred_pols:
                    fp_cat[c] += 1
                elif c in exp_pols and c not in pred_pols:
                    fn_cat[c] += 1
                if c in exp_pols:
                    supp_cat[c] += 1

            # Disagreement check
            # Example: YOLO detected knife or weapon, but Qwen recognized benign Cooking / Shooting Range
            has_yolo_object = bool(set(r.yolo_categories) & {"knife", "gun", "scissors", "fork", "baseball bat"})
            ctx_lower = (r.predicted_context or "").lower()
            if has_yolo_object and any(b in ctx_lower for b in ["cooking", "shooting range", "target practice", "sports"]):
                disagreements.append(
                    ModelDisagreement(
                        sample_id=r.sample_id,
                        scenario_name=r.scenario_name,
                        yolo_categories=r.yolo_categories,
                        qwen_context=r.predicted_context or "",
                        whisper_text=" ".join(r.transcripts),
                        text_signals=r.text_signals,
                        policy_findings=r.predicted_policy_categories,
                        disagreement_type="YOLO Object vs Benign Context",
                        description=f"YOLO detected potentially hazardous objects {r.yolo_categories}, while Qwen synthesized benign scenario '{r.predicted_context}'.",
                        resolved_by_context=True,
                        caused_false_positive=False,
                        caused_false_negative=False,
                    )
                )

            # Error analysis
            if not r.is_correct_decision:
                errors.append(
                    ErrorAnalysisItem(
                        sample_id=r.sample_id,
                        scenario_name=r.scenario_name,
                        expected_decision=r.ground_truth.expected_decision.value,
                        predicted_decision=r.predicted_decision.value if r.predicted_decision else "NONE",
                        expected_risk=r.ground_truth.expected_risk_level.value,
                        predicted_risk=r.predicted_risk_level.value if r.predicted_risk_level else "NONE",
                        expected_policy=r.ground_truth.expected_policy_categories,
                        predicted_policy=r.predicted_policy_categories,
                        likely_responsible_stage="moderation_engine" if not r.is_correct_policy else "context_analysis",
                        available_modalities=["visual", "audio"] if r.transcripts else ["visual"],
                        model_disagreement_occurred=bool(has_yolo_object),
                        context_policy_mapping_contributed=True,
                        failure_reason=f"Predicted decision {r.predicted_decision} did not match expected {r.ground_truth.expected_decision}.",
                        possible_mitigation="Adjust risk thresholds or context mapping heuristics.",
                    )
                )

        decision_metrics = calculate_binary_metrics(eval_pairs)
        multiclass_cm = ConfusionMatrix.create(
            labels=["APPROVED", "REVIEW_REQUIRED", "REJECTED"],
            pairs=multiclass_pairs,
        )
        binary_cm = ConfusionMatrix.create(
            labels=["SAFE", "UNSAFE"],
            pairs=binary_pairs,
        )

        ctx_acc = (context_correct / context_evaluated) if context_evaluated > 0 else 0.0
        context_metrics = ContextMetrics(
            total_evaluated=context_evaluated,
            correct_matches=context_correct,
            accuracy=round(ctx_acc, 4),
            disagreement_count=len(disagreements),
        )

        # Policy category metrics
        cat_metrics: dict[str, CategoryMetric] = {}
        for c in sorted(policy_all_categories):
            tp = tp_cat[c]
            fp = fp_cat[c]
            fn = fn_cat[c]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            cat_metrics[c] = CategoryMetric(
                category=c,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=round(prec, 4),
                recall=round(rec, 4),
                f1_score=round(f1, 4),
                support=supp_cat[c],
            )

        # Latency statistics
        per_stage_stats: dict[str, LatencyStat] = {}
        for st_name, st_vals in stage_times_map.items():
            per_stage_stats[st_name] = calculate_latency_stat(st_vals)

        latency_metrics = LatencyMetrics(
            total_pipeline=calculate_latency_stat(total_times),
            per_stage=per_stage_stats,
            hardware_device=self.settings.ai_device,
            sample_count=len(evaluated_results),
        )

        return EvaluationSummaryMetrics(
            total_dataset_samples=total_samples,
            available_samples_count=len(evaluated_results),
            unavailable_samples_count=len(unavailable_results),
            evaluated_samples_count=len(evaluated_results),
            is_statistically_representative=False,
            decision_metrics=decision_metrics,
            multiclass_confusion_matrix=multiclass_cm,
            binary_confusion_matrix=binary_cm,
            context_metrics=context_metrics,
            policy_category_metrics=cat_metrics,
            model_disagreements=disagreements,
            latency_metrics=latency_metrics,
            errors=errors,
        )
