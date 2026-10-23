import React from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import type { FindingResponse } from '../../types/api';
import { AlertTriangle, Clock, Layers } from 'lucide-react';

interface FindingsMatrixProps {
  findings: FindingResponse[];
}

export const FindingsMatrix: React.FC<FindingsMatrixProps> = ({ findings }) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            Policy Findings Matrix ({findings.length})
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Discrete detections evaluated against community safety policies
          </p>
        </div>
      </div>

      {findings.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-500 dark:text-slate-400 italic">
          No policy findings were flagged for this video.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400">
                <th className="py-3 px-3 font-semibold uppercase tracking-wider">Category</th>
                <th className="py-3 px-3 font-semibold uppercase tracking-wider">Timestamp</th>
                <th className="py-3 px-3 font-semibold uppercase tracking-wider">Confidence</th>
                <th className="py-3 px-3 font-semibold uppercase tracking-wider">Explanation</th>
                <th className="py-3 px-3 font-semibold uppercase tracking-wider text-right">Evidence Items</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {findings.map((f) => (
                <tr key={f.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-3 whitespace-nowrap font-medium text-slate-900 dark:text-slate-100">
                    <Badge variant="warning" size="sm">
                      {f.category}
                    </Badge>
                  </td>
                  <td className="py-3.5 px-3 font-mono text-slate-600 dark:text-slate-300">
                    {f.events && f.events.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {f.events.map((ev, idx) => (
                          <div
                            key={idx}
                            className="inline-flex items-center gap-1.5 text-[11px] bg-slate-100 dark:bg-slate-800/70 px-2 py-0.5 rounded text-slate-700 dark:text-slate-200 w-fit"
                          >
                            <Clock className="w-3 h-3 text-slate-400 shrink-0" />
                            <span>
                              {formatTime(ev.start_time)} – {formatTime(ev.end_time)}
                            </span>
                            <span className="text-[10px] text-slate-400 font-semibold">
                              ({(ev.confidence * 100).toFixed(0)}%)
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {f.end_timestamp
                          ? `${formatTime(f.start_timestamp)} – ${formatTime(f.end_timestamp)}`
                          : formatTime(f.start_timestamp)}
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-3 whitespace-nowrap font-mono font-bold text-slate-700 dark:text-slate-300">
                    {(f.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="py-3.5 px-3 text-slate-700 dark:text-slate-300 max-w-md">
                    {f.summary || f.explanation || <span className="text-slate-400 italic">No explanation recorded</span>}
                  </td>
                  <td className="py-3.5 px-3 whitespace-nowrap text-right font-mono text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="w-3 h-3 text-slate-400" />
                      {f.evidence_references.length}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};
