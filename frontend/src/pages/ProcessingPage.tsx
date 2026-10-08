import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { StatusCard } from '../components/processing/StatusCard';
import { PipelineOverview } from '../components/processing/PipelineOverview';
import { Button } from '../components/common/Button';
import { getVideo } from '../services/api/videos';
import { useVideoStatus } from '../hooks/useVideoStatus';
import type { VideoResponse } from '../types/api';
import { ArrowRight, Film, UploadCloud } from 'lucide-react';

export const ProcessingPage: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();

  const { status, error, isPolling, pollCount } = useVideoStatus(videoId);
  const [video, setVideo] = useState<VideoResponse | null>(null);

  useEffect(() => {
    if (videoId) {
      getVideo(videoId)
        .then((data) => setVideo(data))
        .catch(() => {
          // Metadata might load once ingestion completes
        });
    }
  }, [videoId, status]);

  // When status becomes COMPLETED, auto-navigate to the VideoDetailPage
  useEffect(() => {
    if (status === 'COMPLETED' && videoId) {
      const timer = window.setTimeout(() => {
        navigate(`/videos/${videoId}`);
      }, 1200);
      return () => window.clearTimeout(timer);
    }
  }, [status, videoId, navigate]);

  if (!videoId) {
    return (
      <PageContainer>
        <div className="text-center py-12 space-y-4">
          <p className="text-sm text-slate-500">No video ID provided.</p>
          <Link to="/upload">
            <Button variant="primary">Upload a Video</Button>
          </Link>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="6xl">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
              Analysis Lifecycle
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 mt-0.5">
              Video Moderation Processing
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              Real-time synchronization with the SafeScreen backend moderation pipeline.
            </p>
          </div>

          {status === 'COMPLETED' && (
            <Link to={`/videos/${videoId}`}>
              <Button
                variant="primary"
                size="md"
                icon={<ArrowRight className="w-4 h-4" />}
                className="bg-emerald-600 hover:bg-emerald-700 animate-pulse"
              >
                View Assessment Workspace
              </Button>
            </Link>
          )}
        </div>

        {/* Live Backend Status Card */}
        <StatusCard
          videoId={videoId}
          status={status}
          video={video}
          isPolling={isPolling}
          pollCount={pollCount}
          error={error}
        />

        {/* Next step CTA if completed */}
        {status === 'COMPLETED' && (
          <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center justify-between text-xs text-emerald-800 dark:text-emerald-200">
            <span>Analysis has finished! Redirecting to the Moderation Workspace...</span>
            <Link to={`/videos/${videoId}`}>
              <Button variant="outline" size="sm" className="border-emerald-400 text-emerald-800 dark:text-emerald-200">
                Open Now
              </Button>
            </Link>
          </div>
        )}

        {/* Error state CTA */}
        {status === 'FAILED' && (
          <div className="flex items-center gap-3">
            <Link to="/upload">
              <Button variant="primary" size="md" icon={<UploadCloud className="w-4 h-4" />}>
                Upload Another Video
              </Button>
            </Link>
            <Link to="/videos">
              <Button variant="outline" size="md" icon={<Film className="w-4 h-4" />}>
                View Session Videos
              </Button>
            </Link>
          </div>
        )}

        {/* Conceptual Pipeline Architectural Overview */}
        <PipelineOverview />
      </div>
    </PageContainer>
  );
};
