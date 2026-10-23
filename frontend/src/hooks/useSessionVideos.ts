import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSession } from '../store/sessionContext';
import { getVideo } from '../services/api/videos';
import { getModerationReport } from '../services/api/moderation';
import type { SessionVideoRecord } from '../types/session';

export interface SessionMetrics {
  totalVideos: number;
  completedCount: number;
  reviewRequiredCount: number;
  violationsDetectedCount: number;
}

export function useSessionVideos() {
  const session = useSession();
  const { sessionVideos: rawVideos } = session;

  const [hydratedVideos, setHydratedVideos] = useState<SessionVideoRecord[]>(() => rawVideos);
  const [isLoading, setIsLoading] = useState<boolean>(() => rawVideos.length > 0);
  const [error, setError] = useState<string | null>(null);

  // Derive a stable string key from the current video IDs so we only re-trigger hydration
  // when the list of video IDs actually changes, preventing infinite render loops.
  const videoIdsKey = useMemo(() => {
    return rawVideos.map((v) => v.videoId).join(',');
  }, [rawVideos]);

  // Keep a reference to rawVideos so hydrate function has access without depending on rawVideos directly
  const rawVideosRef = useRef<SessionVideoRecord[]>(rawVideos);
  useEffect(() => {
    rawVideosRef.current = rawVideos;
  }, [rawVideos]);

  const hydrateVideos = useCallback(async () => {
    // Check key to determine if there are session videos
    if (!videoIdsKey) {
      setHydratedVideos([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    const currentVideos = rawVideosRef.current;
    if (currentVideos.length === 0) {
      setHydratedVideos([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    // Safeguard timeout to ensure loading never hangs indefinitely
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 8000);

    try {
      // Query backend for each video independently via Promise.allSettled
      // Robustness requirement: One bad/stale video ID must NOT prevent other videos from rendering.
      const settledResults = await Promise.allSettled(
        currentVideos.map(async (item) => {
          try {
            const videoData = await getVideo(item.videoId);
            let decision = item.decision;
            let riskLevel = item.riskLevel;
            let riskScore = item.riskScore;
            let violationCount = item.violationCount;

            // If backend video has completed, attempt to fetch the moderation report
            if (videoData.status === 'COMPLETED') {
              try {
                const report = await getModerationReport(item.videoId);
                decision = report.decision;
                riskLevel = report.risk_level;
                riskScore = report.risk_score;
                violationCount = report.findings?.length ?? 0;
              } catch {
                // Moderation report might still be generating or not yet persisted; do not fail the video
              }
            }

            const updatedRecord: SessionVideoRecord = {
              ...item,
              filename: videoData.filename || item.filename,
              status: videoData.status,
              duration: videoData.duration ?? item.duration,
              fileSize: videoData.file_size ?? item.fileSize,
              decision,
              riskLevel,
              riskScore,
              violationCount,
              fetchError: undefined,
            };

            return updatedRecord;
          } catch (itemErr: any) {
            // Individual video failure (404, 422, or stale sessionStorage record)
            const errorMsg = itemErr?.message || 'Video metadata unavailable';
            const failedRecord: SessionVideoRecord = {
              ...item,
              fetchError: errorMsg,
            };
            return failedRecord;
          }
        })
      );

      clearTimeout(timeoutId);

      const resolvedList: SessionVideoRecord[] = settledResults.map((result, index) => {
        if (result.status === 'fulfilled') {
          return result.value;
        }
        return {
          ...currentVideos[index],
          fetchError: result.reason?.message || 'Failed to retrieve video metadata',
        };
      });

      // Check if ALL videos failed due to network unavailability (e.g. backend server down)
      const allFailedNetwork =
        resolvedList.length > 0 &&
        resolvedList.every((v) => {
          const errLower = (v.fetchError || '').toLowerCase();
          return (
            errLower.includes('failed to fetch') ||
            errLower.includes('network') ||
            errLower.includes('connection refused') ||
            errLower.includes('offline')
          );
        });

      if (allFailedNetwork) {
        setError('Unable to connect to SafeScreen backend service. Please verify that the API is running.');
      } else {
        setHydratedVideos(resolvedList);
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setError('Session video synchronization timed out. Please try again.');
      } else {
        setError(err?.message || 'Failed to synchronize session videos with backend.');
      }
    } finally {
      clearTimeout(timeoutId);
      // Terminal state guarantee: loading is ALWAYS set to false in finally
      setIsLoading(false);
    }
  }, [videoIdsKey]);

  useEffect(() => {
    hydrateVideos();
  }, [hydrateVideos]);

  const metrics: SessionMetrics = useMemo(() => {
    let completedCount = 0;
    let reviewRequiredCount = 0;
    let violationsDetectedCount = 0;

    hydratedVideos.forEach((v) => {
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
      totalVideos: hydratedVideos.length,
      completedCount,
      reviewRequiredCount,
      violationsDetectedCount,
    };
  }, [hydratedVideos]);

  return {
    ...session,
    sessionVideos: hydratedVideos,
    rawSessionVideos: session.sessionVideos,
    metrics,
    isLoading,
    error,
    refetch: hydrateVideos,
  };
}
