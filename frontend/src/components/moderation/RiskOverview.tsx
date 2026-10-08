import React from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { ShieldCheck, Target, Tag, Calendar } from 'lucide-react';
import type { RiskLevel } from '../../types/api';

interface RiskOverviewProps {
  riskLevel: RiskLevel;
  riskScore: number;
  overallConfidence: number;
  detectedCategories: string[];
  createdAt: string;
}

export const RiskOverview: React.FC<RiskOverviewProps> = ({
  riskScore,
  overallConfidence,
  detectedCategories,
  createdAt,
}) => {
  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
    } catch {
      return isoString;
    }
  };

  const getRiskColor = (score: number) => {
    if (score >= 0.85) return 'bg-red-500';
    if (score >= 0.4) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  return (
    <Card className="p-6 space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          Risk & Confidence Profile
        </h3>
        <span className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1.5 font-mono">
          <Calendar className="w-3.5 h-3.5" />
          {formatDate(createdAt)}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Risk Score Progress Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
              Calculated Risk Score
            </span>
            <span className="text-sm font-bold font-mono text-slate-900 dark:text-slate-100">
              {(riskScore * 100).toFixed(1)}%
            </span>
          </div>
          <div className="h-2.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full ${getRiskColor(riskScore)} transition-all duration-500`}
              style={{ width: `${Math.min(100, Math.max(0, riskScore * 100))}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-slate-400 dark:text-slate-500">
            Weighted assessment based on visual, auditory, and contextual severity flags.
          </p>
        </div>

        {/* Overall Confidence Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-blue-500" />
              Signal Confidence
            </span>
            <span className="text-sm font-bold font-mono text-slate-900 dark:text-slate-100">
              {(overallConfidence * 100).toFixed(0)}%
            </span>
          </div>
          <div className="h-2.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 dark:bg-blue-500 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, overallConfidence * 100))}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-slate-400 dark:text-slate-500">
            Statistical certainty across detected vision objects, speech, and scene classification.
          </p>
        </div>
      </div>

      {/* Flagged Categories */}
      <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
          <Tag className="w-3.5 h-3.5" />
          Detected Policy Categories ({detectedCategories.length})
        </div>

        {detectedCategories.length > 0 ? (
          <div className="flex flex-wrap gap-2 mt-2">
            {detectedCategories.map((category) => (
              <Badge key={category} variant="warning" size="md">
                {category}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 dark:text-slate-400 italic">
            None — No policy categories exceeded the minimum confidence threshold.
          </p>
        )}
      </div>
    </Card>
  );
};
