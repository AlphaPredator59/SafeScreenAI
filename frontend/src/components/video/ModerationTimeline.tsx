import React from 'react';
import type { FindingResponse } from '../../types/api';
import { Card } from '../common/Card';
import { AlertTriangle, Clock } from 'lucide-react';

interface ModerationTimelineProps {
  duration: number;
  currentTime?: number;
  findings: FindingResponse[];
  selectedFindingId?: string | null;
  onSelectFinding: (finding: FindingResponse) => void;
  onSeek: (seconds: number) => void;
}

export const ModerationTimeline: React.FC<ModerationTimelineProps> = ({
  duration,
  currentTime = 0,
  findings,
  selectedFindingId,
  onSelectFinding,
  onSeek,
}) => {
  const safeDuration = Math.max(
    duration || 1,
    ...findings.map((f) => f.end_timestamp || f.start_timestamp || 1)
  );

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const playheadPercent = Math.min(100, (currentTime / safeDuration) * 100);

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickPercent = Math.max(0, Math.min(1, clickX / rect.width));
    const targetSeconds = clickPercent * safeDuration;
    onSeek(targetSeconds);
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            Moderation Timeline
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Click markers to jump to detected events • {findings.length} findings recorded
          </p>
        </div>

        <div className="text-xs font-mono font-medium text-slate-600 dark:text-slate-400">
          <span>{formatSeconds(currentTime)}</span> / <span>{formatSeconds(safeDuration)}</span>
        </div>
      </div>

      {/* Interactive Track Area */}
      <div className="mt-5 relative pt-4 pb-2">
        {/* Track Bar */}
        <div
          onClick={handleTrackClick}
          className="relative h-4 bg-slate-100 dark:bg-slate-800 rounded-full cursor-pointer overflow-hidden border border-slate-200 dark:border-slate-700/60 shadow-inner"
        >
          {/* Progress fill */}
          <div
            className="absolute top-0 bottom-0 left-0 bg-blue-500/25 dark:bg-blue-500/35 transition-all duration-75"
            style={{ width: `${playheadPercent}%` }}
          />

          {/* Finding highlight segments on track */}
          {findings.map((f) => {
            const startPct = Math.min(100, (f.start_timestamp / safeDuration) * 100);
            const endPct = f.end_timestamp
              ? Math.min(100, (f.end_timestamp / safeDuration) * 100)
              : startPct + 2;
            const widthPct = Math.max(1.5, endPct - startPct);

            return (
              <div
                key={f.id}
                style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                className={`absolute top-0 bottom-0 rounded-xs pointer-events-none ${
                  f.id === selectedFindingId
                    ? 'bg-red-500 shadow-xs'
                    : 'bg-amber-500/80 dark:bg-amber-400/80'
                }`}
              />
            );
          })}
        </div>

        {/* Current Playhead indicator needle */}
        <div
          className="absolute top-1 bottom-1 w-0.5 bg-blue-600 dark:bg-blue-400 pointer-events-none transition-all duration-75 z-20"
          style={{ left: `${playheadPercent}%` }}
        >
          <div className="w-2.5 h-2.5 -ml-1 -top-1 bg-blue-600 dark:bg-blue-400 rounded-full shadow-xs" />
        </div>

        {/* Clickable Event Markers */}
        <div className="relative h-7 mt-2">
          {findings.map((finding) => {
            const markerPercent = Math.min(98, Math.max(2, (finding.start_timestamp / safeDuration) * 100));
            const isSelected = finding.id === selectedFindingId;

            return (
              <button
                key={finding.id}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSeek(finding.start_timestamp);
                  onSelectFinding(finding);
                }}
                style={{ left: `${markerPercent}%` }}
                title={`${finding.category} at ${formatSeconds(finding.start_timestamp)} (Conf: ${(finding.confidence * 100).toFixed(0)}%)`}
                className={`absolute -translate-x-1/2 p-1 rounded-full transition-transform hover:scale-125 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isSelected
                    ? 'bg-red-600 text-white scale-110 z-30 ring-2 ring-red-400'
                    : 'bg-amber-500 hover:bg-amber-600 text-white z-10'
                }`}
                aria-label={`Jump to ${finding.category} at ${formatSeconds(finding.start_timestamp)}`}
              >
                <AlertTriangle className="w-3 h-3" />
              </button>
            );
          })}
        </div>

        {/* Time bounds labels */}
        <div className="flex justify-between text-[11px] font-mono text-slate-400 dark:text-slate-500 pt-1">
          <span>0:00</span>
          <span>{formatSeconds(safeDuration / 2)}</span>
          <span>{formatSeconds(safeDuration)}</span>
        </div>
      </div>
    </Card>
  );
};
