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
                    {finding.events && finding.events.length > 1 && (
                      <span className="text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-0.5 rounded-full">
                        {finding.events.length} events
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-slate-600 dark:text-slate-400">
                  Confidence: <strong className="font-bold">{(finding.confidence * 100).toFixed(0)}%</strong>
                </span>

                {(!finding.events || finding.events.length <= 1) && (
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
                )}
              </div>
            </div>

            {(finding.summary || finding.explanation) && (
              <p className="mt-3 text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                {finding.summary || finding.explanation}
              </p>
            )}

            {/* Event-level discrete intervals */}
            {finding.events && finding.events.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Detected Policy Events ({finding.events.length})
                </div>
                <div className="grid gap-2">
                  {finding.events.map((ev, idx) => (
                    <div
                      key={idx}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-50/70 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/60"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                            <Clock className="w-3 h-3 text-amber-500" />
                            {formatTime(ev.start_time)} – {formatTime(ev.end_time)}
                          </span>
                          <span className="text-[11px] font-mono text-slate-500">
                            Confidence: <strong>{(ev.confidence * 100).toFixed(0)}%</strong>
                          </span>
                        </div>
                        {ev.description && (
                          <p className="text-[11px] text-slate-600 dark:text-slate-400">
                            {ev.description}
                          </p>
                        )}
                      </div>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSeek(ev.start_time);
                          onSelectFinding(finding);
                        }}
                        icon={<Play className="w-2.5 h-2.5 fill-current" />}
                        className="text-xs shrink-0 self-start sm:self-auto"
                      >
                        Jump to {formatTime(ev.start_time)}
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
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
