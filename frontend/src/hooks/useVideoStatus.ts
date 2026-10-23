import { useEffect, useRef, useState } from 'react';
import { getVideoStatus } from '../services/api/videos';
import { useSession } from '../store/sessionContext';
import type { VideoStatus } from '../types/api';

interface UseVideoStatusResult {
  status: VideoStatus | null;
  isLoading: boolean;
  error: string | null;
  isPolling: boolean;
  pollCount: number;
}

export function useVideoStatus(videoId: string | undefined): UseVideoStatusResult {
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(videoId));
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [pollCount, setPollCount] = useState<number>(0);

  const { updateSessionVideo } = useSession();
  const pollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!videoId) {
      return;
    }

    let isMounted = true;

    const checkStatus = async () => {
      try {
        const response = await getVideoStatus(videoId);
        if (!isMounted) return;

        setStatus(response.status);
        setIsLoading(false);
        setError(null);
        setPollCount((prev) => prev + 1);

        // Update session store with fresh status
        updateSessionVideo(videoId, { status: response.status });

        // If completed or failed, stop polling
        if (response.status === 'COMPLETED' || response.status === 'FAILED') {
          setIsPolling(false);
          return;
        }

        // Otherwise, continue polling in 2 seconds
        setIsPolling(true);
        pollTimerRef.current = window.setTimeout(checkStatus, 2000);
      } catch (err) {
        if (!isMounted) return;
        setIsLoading(false);
        setIsPolling(false);
        setError(err instanceof Error ? err.message : 'Failed to retrieve video status');
      }
    };

    setIsLoading(true);
    setIsPolling(true);
    checkStatus();

    return () => {
      isMounted = false;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
    };
  }, [videoId, updateSessionVideo]);

  return {
    status,
    isLoading,
    error,
    isPolling,
    pollCount,
  };
}
