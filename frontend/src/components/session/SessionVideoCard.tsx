import React from 'react';
import { Link } from 'react-router-dom';
import { Film, Clock, AlertTriangle, ArrowRight, FileText, Trash2, AlertCircle } from 'lucide-react';
import type { SessionVideoRecord } from '../../types/session';
import { Card } from '../common/Card';
import { Badge, DecisionBadge, RiskBadge, StatusBadge } from '../common/Badge';
import { useSession } from '../../store/sessionContext';

interface SessionVideoCardProps {
  video: SessionVideoRecord;
}

export const SessionVideoCard: React.FC<SessionVideoCardProps> = ({ video }) => {
  const { removeSessionVideo } = useSession();

  const formatTime = (seconds?: number) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const formatDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  // Robustness requirement: If an individual session video failed backend sync (404 / 422 / stale ID),
  // display it as an error/unavailable card while allowing all other session cards to render normally.
  if (video.fetchError) {
    return (
      <Card
        elevated
        className="p-5 border-amber-200 dark:border-amber-900/60 bg-amber-50/30 dark:bg-amber-950/20 flex flex-col justify-between"
      >
        <div>
          <div className="flex items-center justify-between gap-2 mb-3">
            <Badge variant="warning" size="sm">
              <AlertCircle className="w-3 h-3" />
              Unavailable
            </Badge>

            <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
              {formatDate(video.uploadedAt)}
            </span>
          </div>

          <div className="flex items-start gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
              <Film className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate" title={video.filename}>
                {video.filename}
              </h4>
              <p className="text-xs text-slate-400 font-mono truncate">
                ID: {video.videoId}
              </p>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-amber-100/60 dark:bg-amber-900/30 text-xs text-amber-800 dark:text-amber-200 space-y-1">
            <p className="font-medium">Backend sync unavailable</p>
            <p className="text-[11px] opacity-90 truncate" title={video.fetchError}>
              {video.fetchError}
            </p>
          </div>
        </div>

        <div className="pt-3 border-t border-amber-200/60 dark:border-amber-900/40 flex items-center justify-between gap-2 mt-3">
          <button
            onClick={() => removeSessionVideo(video.videoId)}
            className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:underline"
            title="Remove stale reference from session"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Remove
          </button>

          <Link
            to={`/videos/${video.videoId}`}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
          >
            Try Workspace
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card elevated className="p-5 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between">
      <div>
        {/* Card Header with Badges */}
        <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {video.decision ? (
              <DecisionBadge decision={video.decision} size="sm" />
            ) : (
              <StatusBadge status={video.status || 'UPLOADED'} size="sm" />
            )}

            {video.riskLevel && (
              <RiskBadge riskLevel={video.riskLevel} size="sm" />
            )}
          </div>

          <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
            {formatDate(video.uploadedAt)}
          </span>
        </div>

        {/* Video Title and Icon */}
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 flex items-center justify-center shrink-0">
            <Film className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate" title={video.filename}>
              {video.filename}
            </h4>
            <p className="text-xs text-slate-400 font-mono truncate" title={video.videoId}>
              ID: {video.videoId.substring(0, 16)}...
            </p>
          </div>
        </div>

        {/* Technical Metadata */}
        <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400 py-2 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Duration: {formatTime(video.duration)}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span>Violations: {video.violationCount !== undefined ? video.violationCount : '--'}</span>
          </div>
        </div>
      </div>

      {/* Card Action Links */}
      <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2 mt-2">
        <Link
          to={`/videos/${video.videoId}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
        >
          View Details
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>

        {video.status === 'COMPLETED' && (
          <Link
            to={`/videos/${video.videoId}/report`}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <FileText className="w-3.5 h-3.5" />
            View Report
          </Link>
        )}
      </div>
    </Card>
  );
};
