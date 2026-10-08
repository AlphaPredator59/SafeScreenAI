import React from 'react';
import { Card } from '../common/Card';
import type { TranscriptSegmentResponse } from '../../types/api';
import { Mic, Clock, Play } from 'lucide-react';
import { Button } from '../common/Button';

interface TranscriptsViewProps {
  transcripts: TranscriptSegmentResponse[];
  onSeek?: (seconds: number) => void;
}

export const TranscriptsView: React.FC<TranscriptsViewProps> = ({ transcripts, onSeek }) => {
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
            <Mic className="w-5 h-5 text-emerald-500" />
            Spoken Dialogue Transcripts ({transcripts.length})
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Timestamped audio transcription extracted from video audio stream
          </p>
        </div>
      </div>

      {transcripts.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-500 dark:text-slate-400 italic">
          No spoken dialogue was detected or transcribed for this video.
        </div>
      ) : (
        <div className="mt-4 space-y-2.5 max-h-96 overflow-y-auto pr-1">
          {transcripts.map((t, idx) => (
            <div
              key={idx}
              className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-start justify-between gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
            >
              <div className="flex items-start gap-3">
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-slate-200/80 dark:bg-slate-700 text-slate-700 dark:text-slate-300 shrink-0 flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  {formatTime(t.start_timestamp)} – {formatTime(t.end_timestamp)}
                </span>
                <p className="text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                  "{t.text}"
                </p>
              </div>

              {onSeek && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSeek(t.start_timestamp)}
                  icon={<Play className="w-3 h-3 fill-current" />}
                  className="text-[11px] h-6 px-2 text-blue-600 dark:text-blue-400 shrink-0 no-print"
                >
                  Seek
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
