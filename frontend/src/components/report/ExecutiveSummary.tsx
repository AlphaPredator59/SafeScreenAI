import React from 'react';
import { Card } from '../common/Card';
import { Badge, DecisionBadge, RiskBadge } from '../common/Badge';
import {
  FileText,
  Sparkles,
  Eye,
  MessageSquare,
  Compass,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import type { ModerationReportResponse } from '../../types/api';

interface ExecutiveSummaryProps {
  report: ModerationReportResponse;
}

export const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ report }) => {
  const summaryText = report.executive_summary || report.explanation || '';
  const justification = report.ai_justification;
  const isFallback = justification?.is_fallback ?? true;

  const visualEvidence = justification?.visual_evidence ?? [];
  const audioEvidence = justification?.audio_text_evidence ?? [];
  const contextualAnalysis = justification?.contextual_analysis ?? '';
  const policyRationale = justification?.policy_rationale ?? [];
  const uncertainty = justification?.uncertainty ?? [];

  return (
    <Card className="p-6 space-y-6">
      {/* 1. Component Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Executive Summary & AI Justification
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Multi-modal synthesis and policy rationale grounded in verified evidence
            </p>
          </div>
        </div>

        <div>
          {!isFallback ? (
            <Badge variant="purple" size="sm" icon={<Sparkles className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />}>
              Gemini-Formatted
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              Deterministic Synthesis
            </Badge>
          )}
        </div>
      </div>

      {/* 2. Executive Summary Box */}
      <div className="space-y-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          Executive Summary
        </span>
        <div className="p-4 rounded-xl bg-gradient-to-br from-slate-50 to-blue-50/30 dark:from-slate-800/60 dark:to-slate-800/20 border border-slate-200/90 dark:border-slate-700/80 text-sm text-slate-800 dark:text-slate-100 leading-relaxed font-sans shadow-sm">
          {summaryText ? (
            <p className="whitespace-pre-wrap">{summaryText}</p>
          ) : (
            <p className="text-slate-400 italic">No summary provided by the moderation engine.</p>
          )}
        </div>
      </div>

      {/* 3. Authoritative Policy Outcome & Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 pt-1">
        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
            Final Policy Outcome
          </span>
          <div className="mt-2 flex items-center gap-2">
            <DecisionBadge decision={report.decision} size="sm" />
          </div>
          <span className="text-[11px] text-slate-400 mt-2 block">
            Authoritative platform decision
          </span>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
            Risk Score & Level
          </span>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-lg font-bold font-mono text-slate-900 dark:text-slate-100">
              {(report.risk_score * 100).toFixed(1)}%
            </span>
            <RiskBadge riskLevel={report.risk_level} size="sm" />
          </div>
          <span className="text-[11px] text-slate-400 mt-2 block">
            Calibrated multi-modal risk score
          </span>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
            Signal Confidence
          </span>
          <div className="mt-2">
            <span className="text-lg font-bold font-mono text-slate-900 dark:text-slate-100">
              {(report.overall_confidence * 100).toFixed(0)}%
            </span>
          </div>
          <span className="text-[11px] text-slate-400 mt-2 block">
            Multi-modal evidence alignment
          </span>
        </div>
      </div>

      {/* 4. Flagged Policy Categories */}
      <div className="pt-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          Flagged Policy Categories:
        </span>
        {report.detected_categories.length > 0 ? (
          report.detected_categories.map((c) => (
            <Badge key={c} variant="warning" size="sm">
              {c}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-slate-400 italic">None (Safe content)</span>
        )}
      </div>

      {/* 5. AI Justification Subsections */}
      <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
            Evidence-Grounded AI Justification
          </h4>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Subsection A: Visual Evidence */}
          <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-200 font-medium text-xs uppercase tracking-wider">
              <Eye className="w-4 h-4 text-blue-500" />
              <span>A. Visual Evidence</span>
            </div>
            {visualEvidence.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300 list-disc list-inside">
                {visualEvidence.map((item, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">
                No visual detections or objects flagged in sampled frames.
              </p>
            )}
          </div>

          {/* Subsection B: Audio & Text Evidence */}
          <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-200 font-medium text-xs uppercase tracking-wider">
              <MessageSquare className="w-4 h-4 text-emerald-500" />
              <span>B. Audio & Text Evidence</span>
            </div>
            {audioEvidence.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300 list-disc list-inside">
                {audioEvidence.map((item, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">
                No dialogue transcripts or text moderation flags detected.
              </p>
            )}
          </div>

          {/* Subsection C: Contextual Analysis */}
          <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2 md:col-span-2">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-200 font-medium text-xs uppercase tracking-wider">
              <Compass className="w-4 h-4 text-indigo-500" />
              <span>C. Contextual Analysis</span>
            </div>
            {contextualAnalysis ? (
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {contextualAnalysis}
              </p>
            ) : (
              <p className="text-xs text-slate-400 italic">
                Contextual analysis was not required or available for this evaluation.
              </p>
            )}
          </div>

          {/* Subsection D: Policy Rationale */}
          <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-200 font-medium text-xs uppercase tracking-wider">
              <ShieldAlert className="w-4 h-4 text-amber-500" />
              <span>D. Policy Rationale</span>
            </div>
            {policyRationale.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300 list-disc list-inside">
                {policyRationale.map((item, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                All observed behaviors satisfied platform safety policies.
              </p>
            )}
          </div>

          {/* Subsection E: Uncertainty & Limitations */}
          <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-200 font-medium text-xs uppercase tracking-wider">
              <AlertCircle className="w-4 h-4 text-slate-500" />
              <span>E. Uncertainty & Limitations</span>
            </div>
            {uncertainty.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300 list-disc list-inside">
                {uncertainty.map((item, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">
                No significant data limitations or ambiguities identified.
              </p>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};
