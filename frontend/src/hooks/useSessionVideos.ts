import { useMemo } from 'react';
import { useSession } from '../store/sessionContext';

export interface SessionMetrics {
  totalVideos: number;
  completedCount: number;
  reviewRequiredCount: number;
  violationsDetectedCount: number;
}

export function useSessionVideos() {
  const session = useSession();

  const metrics: SessionMetrics = useMemo(() => {
    let completedCount = 0;
    let reviewRequiredCount = 0;
    let violationsDetectedCount = 0;

    session.sessionVideos.forEach((v) => {
      if (v.status === 'COMPLETED') {
        completedCount++;
      }
      if (v.decision === 'REVIEW_REQUIRED') {
        reviewRequiredCount++;
      }
      if (v.decision === 'REJECTED' || (v.violationCount && v.violationCount > 0)) {
        violationsDetectedCount++;
      }
    });

    return {
      totalVideos: session.sessionVideos.length,
      completedCount,
      reviewRequiredCount,
      violationsDetectedCount,
    };
  }, [session.sessionVideos]);

  return {
    ...session,
    metrics,
  };
}
