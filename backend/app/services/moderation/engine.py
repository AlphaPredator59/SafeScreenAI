"""ModerationEngine for multi-modal evidence synthesis and policy decisioning."""

from typing import Sequence

from app.db.enums import ModerationDecision, RiskLevel
from app.services.ai.contracts import (
    ContextualInterpretation,
    TextModerationSignal,
    TranscriptSegment,
    VisualDetection,
)
from app.services.moderation.config import (
    BENIGN_CONTEXT_CATEGORIES,
    DUAL_USE_OBJECTS,
    EXPLICIT_WEAPONS,
    HOSTILE_CONTEXT_CATEGORIES,
    ModerationConfig,
)
from app.services.moderation.contracts import EvidenceItem, ModerationResult, PolicyFinding
from app.services.moderation.temporal_grouping import build_policy_findings


class ModerationEngine:
    """Combines visual, audio/transcript, text moderation, and contextual signals into a final policy decision."""

    def __init__(self, config: ModerationConfig | None = None) -> None:
        self.config = config or ModerationConfig()

    def evaluate(
        self,
        detections: Sequence[VisualDetection] = (),
        transcripts: Sequence[TranscriptSegment] = (),
        text_signals: Sequence[TextModerationSignal] = (),
        context: ContextualInterpretation | None = None,
    ) -> ModerationResult:
        """Evaluate multi-modal inputs and produce an explainable ModerationResult."""
        # 1. Filter valid signals by minimum confidence
        valid_detections = [d for d in detections if d.confidence >= self.config.min_signal_confidence]
        valid_text_signals = [s for s in text_signals if s.confidence >= self.config.min_signal_confidence]

        # 2. Extract and structure supporting evidence
        evidence_items: list[EvidenceItem] = []
        flagged_policy_categories: set[str] = set()

        for d in valid_detections:
            evidence_items.append(
                EvidenceItem(
                    modality="visual",
                    category=d.category,
                    confidence=d.confidence,
                    timestamp=d.timestamp,
                    end_timestamp=d.timestamp,
                    reference=d.evidence_reference,
                    description=f"Visual detection of '{d.category}' at {d.timestamp:.2f}s (conf: {d.confidence:.2f})",
                )
            )

        for s in valid_text_signals:
            evidence_items.append(
                EvidenceItem(
                    modality="text_signal",
                    category=s.category,
                    confidence=s.confidence,
                    timestamp=s.start_timestamp,
                    end_timestamp=s.end_timestamp,
                    reference=f"text_{s.start_timestamp:.1f}s_{s.end_timestamp:.1f}s",
                    description=f"Text moderation flag '{s.category}' on '{s.source_text}' (conf: {s.confidence:.2f})",
                )
            )

        if context is not None and context.confidence >= self.config.min_signal_confidence:
            evidence_items.append(
                EvidenceItem(
                    modality="context",
                    category=context.category,
                    confidence=context.confidence,
                    reference=",".join(context.evidence_references) if context.evidence_references else "context_analysis",
                    description=f"Contextual interpretation: '{context.category}' — {context.reasoning} (conf: {context.confidence:.2f})",
                )
            )
            # Add multi-window temporal evidence items if present
            if len(getattr(context, "window_interpretations", ())) > 1:
                for win in context.window_interpretations:
                    ref_str = ",".join(win.evidence_references) if win.evidence_references else f"win_{win.start_timestamp:.0f}_{win.end_timestamp:.0f}"
                    evidence_items.append(
                        EvidenceItem(
                            modality="context",
                            category=win.category,
                            confidence=win.confidence,
                            timestamp=win.start_timestamp,
                            end_timestamp=win.end_timestamp,
                            reference=ref_str,
                            description=f"Context [{win.start_timestamp:.1f}s - {win.end_timestamp:.1f}s]: '{win.category}' (status: {win.status}) — {win.reasoning}",
                        )
                    )

        # 3. Context Analysis Classification
        is_benign_context = False
        is_hostile_context = False
        context_category_norm = context.category.strip().lower() if context else ""
        mapped_context_cats: tuple[str, ...] = ()
        has_failed_window = False
        if context is not None:
            has_failed_window = any(w.status == "failed" for w in getattr(context, "window_interpretations", ()))
        is_inconclusive = (
            context is not None
            and (
                has_failed_window
                or any(inc in context_category_norm for inc in ("inconclusive", "unknown", "failed", "unverified"))
            )
        )

        if context and context.confidence >= self.config.min_signal_confidence and not is_inconclusive:
            if any(b in context_category_norm for b in self.config.benign_context_categories):
                is_benign_context = True
            else:
                mapped_context_cats = self.config.map_context_category(context.category)
                if mapped_context_cats or any(h in context_category_norm for h in self.config.hostile_context_categories):
                    is_hostile_context = True

        # Check multi-window interpretations for any hostile window
        if context is not None:
            for win in getattr(context, "window_interpretations", ()):
                if win.status == "success" and win.confidence >= self.config.min_signal_confidence:
                    win_norm = win.category.strip().lower()
                    if any(h in win_norm for h in self.config.hostile_context_categories) or self.config.map_context_category(win.category):
                        is_hostile_context = True
                        is_benign_context = False
                        break

        # 4. Assess Individual Policy Risks
        signal_risks: list[tuple[str, float, float]] = []  # (policy_category, individual_risk, confidence)

        # Distinguish explicit physical threats / violence in speech from general verbal toxicity
        has_threat_or_violence_text = any(
            any(h in s.category.lower() for h in ("threat", "threats", "violence", "extreme_violence"))
            for s in valid_text_signals
        )
        has_conflicting_signals = False

        # Visual detections evaluation:
        # Group valid visual detections by effective policy category
        policy_visual_dets: dict[str, list[VisualDetection]] = {}
        for d in valid_detections:
            cat_lower = d.category.strip().lower()
            is_dual_use = any(obj in cat_lower for obj in DUAL_USE_OBJECTS)
            is_explicit_weapon = any(w in cat_lower for w in EXPLICIT_WEAPONS)
            is_policy_direct = self.config.get_policy_severity(cat_lower) > 0.0

            if is_dual_use:
                if is_benign_context and not has_threat_or_violence_text:
                    # Benign culinary/craft/sports context fully mitigates dual-use object to zero policy risk
                    continue
                elif is_hostile_context or has_threat_or_violence_text:
                    # Dual-use object in hostile context or accompanied by physical threat text is treated as weapon
                    policy_visual_dets.setdefault("weapons", []).append(d)
                    flagged_policy_categories.add("weapons")
                else:
                    # Unverified context: potentially dangerous weapon requiring review
                    policy_visual_dets.setdefault("weapons", []).append(d)
                    flagged_policy_categories.add("weapons")
                    has_conflicting_signals = True

            elif is_explicit_weapon:
                policy_visual_dets.setdefault("weapons", []).append(d)
                flagged_policy_categories.add("weapons")
                if not context or is_inconclusive:
                    has_conflicting_signals = True

            elif is_policy_direct:
                policy_visual_dets.setdefault(cat_lower, []).append(d)
                flagged_policy_categories.add(cat_lower)

            # Note: Harmless everyday objects (bowl, broccoli, person, spoon, fork) have severity 0.0 and are ignored here

        # Cluster visual detections into discrete temporal events so frame sampling frequency does not multiply risk
        for cat, cat_dets in policy_visual_dets.items():
            events = self._cluster_detections_into_events(cat_dets, max_gap_seconds=5.0)
            severity = self.config.get_policy_severity(cat)
            for _, _, peak_conf in events:
                item_risk = severity * peak_conf
                if is_hostile_context:
                    item_risk *= self.config.hostile_aggravation_multiplier
                signal_risks.append((cat, min(1.0, item_risk), peak_conf))

        # Text signals evaluation: cluster nearby transcript segments of the same category
        text_signals_by_cat: dict[str, list[TextModerationSignal]] = {}
        for s in valid_text_signals:
            severity = self.config.get_policy_severity(s.category)
            if severity > 0.0:
                text_signals_by_cat.setdefault(s.category, []).append(s)
                flagged_policy_categories.add(s.category)

        for cat, cat_sigs in text_signals_by_cat.items():
            events = self._cluster_text_signals_into_events(cat_sigs, max_gap_seconds=5.0)
            severity = self.config.get_policy_severity(cat)
            for _, _, peak_conf in events:
                item_risk = severity * peak_conf
                if is_hostile_context:
                    item_risk *= self.config.hostile_aggravation_multiplier
                signal_risks.append((cat, min(1.0, item_risk), peak_conf))

        # Context evaluation
        if context and context.confidence >= self.config.min_signal_confidence and not is_benign_context:
            if mapped_context_cats:
                for policy_cat in mapped_context_cats:
                    severity = self.config.get_policy_severity(policy_cat)
                    if severity > 0.0:
                        ctx_risk = severity * context.confidence
                        signal_risks.append((policy_cat, min(1.0, ctx_risk), context.confidence))
                        flagged_policy_categories.add(policy_cat)
            elif is_hostile_context:
                ctx_severity = self.config.get_policy_severity(context.category)
                if ctx_severity > 0.0:
                    ctx_risk = ctx_severity * context.confidence
                    signal_risks.append((context.category, min(1.0, ctx_risk), context.confidence))
                    flagged_policy_categories.add(context.category)

        # 5. Calculate Aggregate Risk Score
        if not signal_risks:
            risk_score = 0.0
        else:
            sorted_risks = sorted([r[1] for r in signal_risks], reverse=True)
            max_risk = sorted_risks[0]
            secondary_sum = sum(sorted_risks[1:])
            risk_score = max_risk + (0.10 * secondary_sum)

            # Check cross-modal corroboration (requires both elevated visual AND text signals)
            has_elevated_visual = any(
                d.confidence >= 0.5
                and (
                    self.config.get_policy_severity(d.category.strip().lower()) >= 0.5
                    or any(w in d.category.strip().lower() for w in EXPLICIT_WEAPONS)
                    or (is_hostile_context and any(du in d.category.strip().lower() for du in DUAL_USE_OBJECTS))
                )
                for d in valid_detections
            )
            has_elevated_text = any(
                self.config.get_policy_severity(s.category) >= 0.5
                for s in valid_text_signals
                if s.confidence >= 0.5
            )

            if has_elevated_visual and has_elevated_text:
                risk_score *= self.config.cross_modal_corroboration_multiplier

            # Critical safety override
            for cat, risk, conf in signal_risks:
                if cat.lower() in ("child_safety", "self_harm") and conf >= 0.70:
                    risk_score = max(risk_score, 0.95)

            # Conflict: credible threat/violence text vs explicit benign context
            if has_threat_or_violence_text and is_benign_context and context and context.confidence >= 0.7:
                has_conflicting_signals = True

            # Inconclusive/failed context with active signals requires human review
            if is_inconclusive and (valid_detections or valid_text_signals):
                has_conflicting_signals = True

            risk_score = min(1.0, max(0.0, risk_score))

        # 6. Calculate Overall Moderation Confidence
        overall_confidence = self._compute_overall_confidence(
            valid_detections=valid_detections,
            valid_text_signals=valid_text_signals,
            context=context,
        )

        # 7. Map Risk Level
        risk_level = self._determine_risk_level(risk_score)

        # 8. Determine Moderation Decision
        decision = self._determine_decision(
            risk_score=risk_score,
            has_conflicting_signals=has_conflicting_signals,
        )

        # 9. Generate Grounded Explanation
        explanation = self._generate_explanation(
            decision=decision,
            risk_level=risk_level,
            risk_score=risk_score,
            overall_confidence=overall_confidence,
            valid_detections=valid_detections,
            valid_text_signals=valid_text_signals,
            context=context,
            is_benign_context=is_benign_context,
            is_hostile_context=is_hostile_context,
            has_conflicting_signals=has_conflicting_signals,
            flagged_categories=flagged_policy_categories,
        )

        findings = build_policy_findings(
            detected_categories=sorted(flagged_policy_categories),
            evidence_items=evidence_items,
            config=self.config,
        )

        return ModerationResult(
            decision=decision,
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            overall_confidence=round(overall_confidence, 4),
            detected_categories=tuple(sorted(flagged_policy_categories)),
            supporting_evidence=tuple(evidence_items),
            explanation=explanation,
            findings=tuple(findings),
        )

    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        if risk_score < self.config.low_risk_threshold:
            return RiskLevel.LOW
        elif risk_score < self.config.medium_risk_threshold:
            return RiskLevel.MEDIUM
        elif risk_score < self.config.high_risk_threshold:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    def _determine_decision(
        self,
        risk_score: float,
        has_conflicting_signals: bool,
    ) -> ModerationDecision:
        if has_conflicting_signals:
            return ModerationDecision.REVIEW_REQUIRED
        if risk_score >= self.config.auto_reject_threshold:
            return ModerationDecision.REJECTED
        elif risk_score >= self.config.review_threshold:
            return ModerationDecision.REVIEW_REQUIRED
        return ModerationDecision.APPROVED

    def _compute_overall_confidence(
        self,
        valid_detections: Sequence[VisualDetection],
        valid_text_signals: Sequence[TextModerationSignal],
        context: ContextualInterpretation | None,
    ) -> float:
        """Derive overall moderation confidence from multi-modal evidence completeness and alignment."""
        conf_scores: list[tuple[float, float]] = []  # (confidence, weight)

        for d in valid_detections:
            conf_scores.append((d.confidence, 1.0))
        for s in valid_text_signals:
            conf_scores.append((s.confidence, 1.2))
        if context is not None:
            conf_scores.append((context.confidence, 2.0))

        if not conf_scores:
            return 1.0  # High confidence in clean/unflagged content

        total_weight = sum(w for _, w in conf_scores)
        weighted_sum = sum(c * w for c, w in conf_scores)
        base_confidence = weighted_sum / total_weight

        # Bonus if context aligns with detections or confirms analysis
        if context and context.confidence >= 0.70:
            base_confidence = min(1.0, base_confidence * 1.05)

        return min(1.0, max(0.0, base_confidence))

    def _generate_explanation(
        self,
        decision: ModerationDecision,
        risk_level: RiskLevel,
        risk_score: float,
        overall_confidence: float,
        valid_detections: Sequence[VisualDetection],
        valid_text_signals: Sequence[TextModerationSignal],
        context: ContextualInterpretation | None,
        is_benign_context: bool,
        is_hostile_context: bool,
        has_conflicting_signals: bool,
        flagged_categories: set[str],
    ) -> str:
        """Generate a deterministic, grounded explanation summarizing findings and policy rationale."""
        sections: list[str] = []

        # 1. Signal Summary
        det_summary = f"{len(valid_detections)} visual detection(s)"
        if valid_detections:
            det_cats = ", ".join(f"'{d.category}' ({d.confidence:.2f})" for d in valid_detections[:3])
            det_summary += f" including [{det_cats}]"

        text_summary = f"{len(valid_text_signals)} text signal(s)"
        if valid_text_signals:
            txt_cats = ", ".join(f"'{s.category}' ({s.confidence:.2f})" for s in valid_text_signals[:3])
            text_summary += f" including [{txt_cats}]"

        ctx_summary = "no context analysis provided"
        if context:
            ctx_summary = f"context inferred as '{context.category}' (conf: {context.confidence:.2f}) with reasoning: \"{context.reasoning}\""

        sections.append(f"Evidence Analyzed: {det_summary}; {text_summary}; {ctx_summary}.")

        # 2. Contextual Rationale
        if is_benign_context and valid_detections:
            sections.append(
                f"Contextual Impact: Verified benign context ('{context.category}') confirms objects are non-harmful tools/props, mitigating policy risk."
            )
        elif is_hostile_context:
            sections.append(
                f"Contextual Impact: Identified threatening/hostile context ('{context.category}') reinforced and aggravated policy risk."
            )
        elif has_conflicting_signals:
            sections.append(
                "Contextual Impact: Unverified or conflicting signals detected across modalities requiring human review."
            )

        # 3. Decision Rationale
        flagged_str = f"Flagged policy categories: {list(sorted(flagged_categories))}." if flagged_categories else "No policy categories flagged."
        sections.append(
            f"Assessment: {flagged_str} Risk score calculated at {risk_score:.2f} ({risk_level.value}) with overall confidence {overall_confidence:.2f}. "
            f"Final moderation outcome is {decision.value}."
        )

        return " ".join(sections)

    @staticmethod
    def _cluster_detections_into_events(
        detections: Sequence[VisualDetection],
        max_gap_seconds: float = 5.0,
    ) -> list[tuple[float, float, float]]:
        """Group detections of a single category into discrete temporal events.

        Returns list of (start_time, end_time, peak_confidence) for each event.
        Consecutive frame detections within max_gap_seconds are coalesced so that
        high frame sampling rates or camera dwell time do not artificially inflate risk.
        """
        if not detections:
            return []

        sorted_dets = sorted(detections, key=lambda d: getattr(d, "timestamp", 0.0) or 0.0)
        clusters: list[list[VisualDetection]] = []
        current_cluster: list[VisualDetection] = [sorted_dets[0]]
        current_end = getattr(sorted_dets[0], "timestamp", 0.0) or 0.0

        for d in sorted_dets[1:]:
            t = getattr(d, "timestamp", 0.0) or 0.0
            if t <= current_end + max_gap_seconds:
                current_end = max(current_end, t)
                current_cluster.append(d)
            else:
                clusters.append(current_cluster)
                current_cluster = [d]
                current_end = t

        if current_cluster:
            clusters.append(current_cluster)

        events: list[tuple[float, float, float]] = []
        for c in clusters:
            st = getattr(c[0], "timestamp", 0.0) or 0.0
            et = max((getattr(d, "timestamp", 0.0) or 0.0) for d in c)
            peak_conf = max(d.confidence for d in c)
            events.append((st, et, peak_conf))
        return events

    @staticmethod
    def _cluster_text_signals_into_events(
        signals: Sequence[TextModerationSignal],
        max_gap_seconds: float = 5.0,
    ) -> list[tuple[float, float, float]]:
        """Group text signals of a single category into discrete temporal events.

        Returns list of (start_time, end_time, peak_confidence) for each event.
        """
        if not signals:
            return []

        sorted_sigs = sorted(signals, key=lambda s: getattr(s, "start_timestamp", 0.0) or 0.0)
        clusters: list[list[TextModerationSignal]] = []
        current_cluster: list[TextModerationSignal] = [sorted_sigs[0]]
        current_end = getattr(sorted_sigs[0], "end_timestamp", 0.0) or (getattr(sorted_sigs[0], "start_timestamp", 0.0) or 0.0)

        for s in sorted_sigs[1:]:
            st = getattr(s, "start_timestamp", 0.0) or 0.0
            et = getattr(s, "end_timestamp", 0.0) or st
            if st <= current_end + max_gap_seconds:
                current_end = max(current_end, et)
                current_cluster.append(s)
            else:
                clusters.append(current_cluster)
                current_cluster = [s]
                current_end = et

        if current_cluster:
            clusters.append(current_cluster)

        events: list[tuple[float, float, float]] = []
        for c in clusters:
            st = getattr(c[0], "start_timestamp", 0.0) or 0.0
            et = max((getattr(s, "end_timestamp", 0.0) or getattr(s, "start_timestamp", 0.0) or 0.0) for s in c)
            peak_conf = max(s.confidence for s in c)
            events.append((st, et, peak_conf))
        return events

