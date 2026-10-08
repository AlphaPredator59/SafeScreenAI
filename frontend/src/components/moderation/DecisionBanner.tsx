import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Shield } from 'lucide-react';
import type { ModerationDecision, RiskLevel } from '../../types/api';
import { RiskBadge } from '../common/Badge';

interface DecisionBannerProps {
  decision: ModerationDecision;
  riskLevel: RiskLevel;
  riskScore: number;
  overallConfidence: number;
}

export const DecisionBanner: React.FC<DecisionBannerProps> = ({
  decision,
  riskLevel,
  riskScore,
  overallConfidence,
}) => {
  const getBannerDetails = () => {
    switch (decision) {
      case 'APPROVED':
        return {
          icon: <CheckCircle2 className="w-8 h-8 text-emerald-500 shrink-0" />,
          title: 'Content Approved (Safe for Publication)',
          description:
            'No severe policy violations detected. The multi-modal analysis identified standard benign interactions.',
          border: 'border-emerald-200 dark:border-emerald-900',
          bg: 'bg-emerald-50/70 dark:bg-emerald-950/30',
          textTitle: 'text-emerald-900 dark:text-emerald-100',
          textDesc: 'text-emerald-700 dark:text-emerald-300',
        };
      case 'REVIEW_REQUIRED':
        return {
          icon: <AlertTriangle className="w-8 h-8 text-amber-500 shrink-0" />,
          title: 'Human Review Required',
          description:
            'Potential policy ambiguity or sensitive items detected. Contextual factors warrant human supervisor confirmation.',
          border: 'border-amber-200 dark:border-amber-900',
          bg: 'bg-amber-50/70 dark:bg-amber-950/30',
          textTitle: 'text-amber-900 dark:text-amber-100',
          textDesc: 'text-amber-700 dark:text-amber-300',
        };
      case 'REJECTED':
        return {
          icon: <XCircle className="w-8 h-8 text-red-500 shrink-0" />,
          title: 'Policy Violations Detected (Rejected)',
          description:
            'Severe policy violations identified by the moderation engine. Action is recommended before release.',
          border: 'border-red-200 dark:border-red-900',
          bg: 'bg-red-50/70 dark:bg-red-950/30',
          textTitle: 'text-red-900 dark:text-red-100',
          textDesc: 'text-red-700 dark:text-red-300',
        };
      default:
        return {
          icon: <Shield className="w-8 h-8 text-slate-500 shrink-0" />,
          title: `Assessment Outcome: ${decision}`,
          description: 'Moderation assessment completed.',
          border: 'border-slate-200 dark:border-slate-800',
          bg: 'bg-slate-50 dark:bg-slate-900',
          textTitle: 'text-slate-900 dark:text-slate-100',
          textDesc: 'text-slate-600 dark:text-slate-400',
        };
    }
  };

  const details = getBannerDetails();

  return (
    <div className={`p-6 rounded-2xl border ${details.border} ${details.bg} flex flex-col sm:flex-row sm:items-center justify-between gap-6`}>
      <div className="flex items-start gap-4">
        {details.icon}
        <div>
          <h2 className={`text-xl font-bold ${details.textTitle}`}>
            {details.title}
          </h2>
          <p className={`mt-1 text-sm ${details.textDesc} max-w-2xl`}>
            {details.description}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap sm:flex-col items-start sm:items-end gap-2 shrink-0 border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-200 dark:border-slate-800">
        <RiskBadge riskLevel={riskLevel} size="md" />
        <div className="text-xs text-slate-600 dark:text-slate-300 space-x-2 sm:space-x-0 sm:text-right">
          <span>Risk Score: <strong className="font-mono">{(riskScore * 100).toFixed(1)}%</strong></span>
          <span className="text-slate-400 hidden sm:inline">•</span>
          <span>Confidence: <strong className="font-mono">{(overallConfidence * 100).toFixed(0)}%</strong></span>
        </div>
      </div>
    </div>
  );
};
