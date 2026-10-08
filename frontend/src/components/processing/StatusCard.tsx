import React from 'react';
import { RefreshCw, Film, Clock, MonitorPlay, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { VideoResponse, VideoStatus } from '../../types/api';
import { Card } from '../common/Card';
import { StatusBadge } from '../common/Badge';

interface StatusCardProps {
  videoId: string;
  status: VideoStatus | null;
  video: VideoResponse | null;
  isPolling: boolean;
  pollCount: number;
  error: string | null;
}

export const StatusCard: React.FC<StatusCardProps> = ({
  videoId,
  status,
  video,
  isPolling,
  pollCount,
  error,
}) => {
  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '--';
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  return (
    <Card elevated className="p-6">
      {/* Header with Title and Real Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100 dark:border-slate-800">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Current Backend Status
          </span>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2 mt-0.5">
            {video?.filename || 'Analyzing Video...'}
          </h2>
          <p className="text-xs text-slate-400 dark:text-slate-500 font-mono mt-0.5">
            ID: {videoId}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {status && <StatusBadge status={status} size="md" />}
          {isPolling && (
            <span
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400"
              title={`Polling heartbeat: ${pollCount} checks performed`}
            >
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-500" />
              <span className="hidden sm:inline">Checking</span>
            </span>
          )}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mt-4 p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-xs flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Status check encountered an error:</p>
            <p className="mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Video Technical Specs if available */}
      {video && (
        <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <Clock className="w-3.5 h-3.5" />
              Duration
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
              {formatDuration(video.duration)}
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <MonitorPlay className="w-3.5 h-3.5" />
              Resolution
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
              {video.width > 0 ? `${video.width} × ${video.height}` : 'Processing'}
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <Film className="w-3.5 h-3.5" />
              Frame Rate
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
              {video.fps > 0 ? `${video.fps.toFixed(1)} FPS` : 'Processing'}
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              File Size
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
              {formatFileSize(video.file_size)}
            </p>
          </div>
        </div>
      )}

      {/* Backend Ingestion Status Description */}
      <div className="mt-5 p-4 rounded-xl bg-blue-50/60 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 text-xs text-blue-900 dark:text-blue-200">
        <p className="font-medium">
          {status === 'UPLOADED' && 'Video uploaded and safely registered in backend storage. Processing state will update as analysis proceeds.'}
          {status === 'QUEUED' && 'Video is in backend processing queue awaiting worker evaluation.'}
          {status === 'PROCESSING' && 'Backend processing active: Extracting frames, sampling audio, and executing computer vision detectors.'}
          {status === 'ANALYZING' && 'AI Context analysis in progress: Evaluating speech transcripts and multi-modal scene context.'}
          {status === 'COMPLETED' && 'Assessment complete. Moderation results and explainable findings are ready.'}
          {status === 'FAILED' && 'Backend processing failed. Please check backend server logs or upload a compatible video.'}
        </p>
      </div>
    </Card>
  );
};
