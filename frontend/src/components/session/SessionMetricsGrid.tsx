import React from 'react';
import { Film, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react';
import { StatCard } from '../common/StatCard';
import type { SessionMetrics } from '../../hooks/useSessionVideos';

interface SessionMetricsGridProps {
  metrics: SessionMetrics;
}

export const SessionMetricsGrid: React.FC<SessionMetricsGridProps> = ({ metrics }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        label="Videos in Session"
        value={metrics.totalVideos}
        icon={<Film className="w-5 h-5" />}
        description="Uploaded during current browser session"
        variant="default"
      />

      <StatCard
        label="Completed Analyses"
        value={metrics.completedCount}
        icon={<CheckCircle2 className="w-5 h-5" />}
        description="Videos with finished AI evaluation"
        variant="success"
      />

      <StatCard
        label="Review Required"
        value={metrics.reviewRequiredCount}
        icon={<AlertTriangle className="w-5 h-5" />}
        description="Ambiguous items needing supervisor review"
        variant="warning"
      />

      <StatCard
        label="Violations Detected"
        value={metrics.violationsDetectedCount}
        icon={<ShieldAlert className="w-5 h-5" />}
        description="Videos flagged with policy violations"
        variant="danger"
      />
    </div>
  );
};
