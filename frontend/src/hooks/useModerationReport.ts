import { useCallback, useEffect, useState } from 'react';
import { getEvidence, getModerationReport } from '../services/api/moderation';
import { getVideo } from '../services/api/videos';
import { useSession } from '../store/sessionContext';
import type { EvidenceListResponse, ModerationReportResponse, VideoResponse } from '../types/api';

interface UseModerationReportResult {
  report: ModerationReportResponse | null;
  video: VideoResponse | null;
  evidenceList: EvidenceListResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useModerationReport(videoId: string | undefined): UseModerationReportResult {
  const [report, setReport] = useState<ModerationReportResponse | null>(null);
  const [video, setVideo] = useState<VideoResponse | null>(null);
  const [evidenceList, setEvidenceList] = useState<EvidenceListResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const { updateSessionVideo } = useSession();

  const fetchData = useCallback(async () => {
    if (!videoId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch video metadata
      const videoData = await getVideo(videoId);
      setVideo(videoData);

      // 2. Fetch moderation report (may return 404 if not completed)
      let reportData: ModerationReportResponse | null = null;
      try {
        reportData = await getModerationReport(videoId);
        setReport(reportData);
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status === 404) {
          // Report not ready yet or not completed
          setReport(null);
        } else {
          throw err;
        }
      }

      // 3. Fetch evidence list if available
      try {
        const evData = await getEvidence(videoId);
        setEvidenceList(evData);
      } catch {
        setEvidenceList(null);
      }

      // Update session store with rich report details
      if (reportData) {
        updateSessionVideo(videoId, {
          status: videoData.status,
          decision: reportData.decision,
          riskLevel: reportData.risk_level,
          riskScore: reportData.risk_score,
          violationCount: reportData.findings.length,
          duration: videoData.duration,
          fileSize: videoData.file_size,
        });
      } else {
        updateSessionVideo(videoId, {
          status: videoData.status,
          duration: videoData.duration,
          fileSize: videoData.file_size,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load video moderation assessment');
    } finally {
      setIsLoading(false);
    }
  }, [videoId, updateSessionVideo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    report,
    video,
    evidenceList,
    isLoading,
    error,
    refetch: fetchData,
  };
}
