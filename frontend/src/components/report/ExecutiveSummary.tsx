import React from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { FileText } from 'lucide-react';
import type { ModerationReportResponse } from '../../types/api';

interface ExecutiveSummaryProps {
  report: ModerationReportResponse;
}

export const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ report }) => {
  return (
    <Card className="p-6 space-y-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          Executive Summary & AI Justification
        </h3>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          Backend Synthesis
        </span>
      </div>

      {/* Actual AI Explanation string verbatim from backend */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
        {report.explanation || (
          <span className="text-slate-400 italic">No textual explanation provided by the backend moderation engine.</span>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
        <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">
            Final Policy Outcome
          </span>
          <span className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5 block">
            {report.decision}
          </span>
          <span className="text-[11px] text-slate-400">Deterministic synthesis</span>
        </div>

        <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">
            Risk Score / Band
          </span>
          <span className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-0.5 block">
            {(report.risk_score * 100).toFixed(1)}% ({report.risk_level})
          </span>
          <span className="text-[11px] text-slate-400">Weighted policy impact</span>
        </div>

        <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">
            Overall Confidence
          </span>
          <span className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-0.5 block">
            {(report.overall_confidence * 100).toFixed(0)}%
          </span>
          <span className="text-[11px] text-slate-400">Multi-modal signal alignment</span>
        </div>
      </div>

      {/* Detected categories */}
      <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          Flagged Categories:
        </span>
        {report.detected_categories.length > 0 ? (
          report.detected_categories.map((c) => (
            <Badge key={c} variant="warning" size="sm">
              {c}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-slate-400 italic">None</span>
        )}
      </div>
    </Card>
  );
};
