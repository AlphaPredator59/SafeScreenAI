import React from 'react';
import type { FindingResponse } from '../../types/api';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { AlertTriangle, Clock, Layers, Play } from 'lucide-react';

interface FindingsListProps {
  findings: FindingResponse[];
  selectedFindingId?: string | null;
  onSelectFinding: (finding: FindingResponse) => void;
  onSeek: (seconds: number) => void;
}

export const FindingsList: React.FC<FindingsListProps> = ({
  findings,
  selectedFindingId,
  onSelectFinding,
  onSeek,
}) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  if (findings.length === 0) {
    return (
      <Card className="p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto mb-3">
          <Clock className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
          No Policy Violations Detected
        </h4>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
          The moderation engine did not identify any actionable safety violations in this video.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {findings.map((finding) => {
        const isSelected = finding.id === selectedFindingId;
        const timeStr = finding.end_timestamp
          ? `${formatTime(finding.start_timestamp)} – ${formatTime(finding.end_timestamp)}`
          : formatTime(finding.start_timestamp);

        return (
          <Card
            key={finding.id}
            onClick={() => onSelectFinding(finding)}
            className={`p-5 cursor-pointer transition-all ${
              isSelected
                ? 'ring-2 ring-blue-500 border-blue-400 dark:border-blue-600 shadow-md bg-blue-50/20 dark:bg-blue-950/10'
                : 'hover:border-slate-300 dark:hover:border-slate-700'
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant="warning" size="md">
                      {finding.category}
                    </Badge>
                    <span className="text-xs font-mono font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {timeStr}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-slate-600 dark:text-slate-400">
                  Confidence: <strong className="font-bold">{(finding.confidence * 100).toFixed(0)}%</strong>
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(finding.start_timestamp);
                    onSelectFinding(finding);
                  }}
                  icon={<Play className="w-3 h-3 fill-current" />}
                  className="text-xs"
                >
                  Jump to {formatTime(finding.start_timestamp)}
                </Button>
              </div>
            </div>

            {finding.explanation && (
              <p className="mt-3 text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                {finding.explanation}
              </p>
            )}

            {finding.evidence_references.length > 0 && (
              <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-400 dark:text-slate-500">
                <Layers className="w-3.5 h-3.5" />
                <span>
                  Supported by {finding.evidence_references.length} traceable evidence {finding.evidence_references.length === 1 ? 'item' : 'items'}
                </span>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};
