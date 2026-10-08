import React, { useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { VideoPlayer } from '../components/video/VideoPlayer';
import type { VideoPlayerRef } from '../components/video/VideoPlayer';
import { ModerationTimeline } from '../components/video/ModerationTimeline';
import { DecisionBanner } from '../components/moderation/DecisionBanner';
import { RiskOverview } from '../components/moderation/RiskOverview';
import { FindingsList } from '../components/moderation/FindingsList';
import { EvidenceGallery } from '../components/moderation/EvidenceGallery';
import { TranscriptsView } from '../components/report/TranscriptsView';
import { ExecutiveSummary } from '../components/report/ExecutiveSummary';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { ReportSkeleton } from '../components/common/LoadingSkeleton';
import { Button } from '../components/common/Button';
import { useModerationReport } from '../hooks/useModerationReport';
import { useSession } from '../store/sessionContext';
import type { FindingResponse } from '../types/api';
import { FileText, AlertTriangle, Layers, Mic, Info, ArrowLeft, ArrowUpRight } from 'lucide-react';

export const VideoDetailPage: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const playerRef = useRef<VideoPlayerRef>(null);

  const { report, video, evidenceList, isLoading, error, refetch } = useModerationReport(videoId);
  const { getBlobUrl } = useSession();

  const [activeTab, setActiveTab] = useState<'findings' | 'evidence' | 'transcripts' | 'summary'>('findings');
  const [selectedFinding, setSelectedFinding] = useState<FindingResponse | null>(null);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState<number>(0);

  // Retrieve local blob URL if uploaded during active tab session
  const blobUrl = videoId ? getBlobUrl(videoId) : undefined;

  const handleSeek = (seconds: number) => {
    setCurrentPlaybackTime(seconds);
    playerRef.current?.seekTo(seconds);
  };

  const handleSelectFinding = (finding: FindingResponse) => {
    setSelectedFinding(finding);
    setActiveTab('findings');
    handleSeek(finding.start_timestamp);
  };

  if (isLoading) {
    return (
      <PageContainer>
        <ReportSkeleton />
      </PageContainer>
    );
  }

  if (error || !video) {
    return (
      <PageContainer>
        <div className="space-y-4 max-w-2xl mx-auto py-10">
          <ErrorAlert
            title="Video Moderation Data Unavailable"
            message={error || 'Video record was not found on the backend.'}
            onRetry={refetch}
          />
          <Link to="/videos">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-3.5 h-3.5" />}>
              Back to Session Videos
            </Button>
          </Link>
        </div>
      </PageContainer>
    );
  }

  const duration = video.duration || (report?.evidence.length ? Math.max(...report.evidence.map(e => e.timestamp)) : 0);
  const findings = report?.findings || [];
  const evidence = evidenceList?.evidence || report?.evidence || [];
  const transcripts = report?.transcripts || [];

  return (
    <PageContainer>
      <div className="space-y-8">
        {/* Navigation & Header Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link
                to="/videos"
                className="text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 flex items-center gap-1"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Session Videos
              </Link>
              <span className="text-slate-400">•</span>
              <span className="text-xs text-blue-600 dark:text-blue-400 font-mono">
                {video.video_id}
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 truncate max-w-xl" title={video.filename}>
              {video.filename}
            </h1>
          </div>

          <div className="flex items-center gap-2.5">
            {report && (
              <Link to={`/videos/${video.video_id}/report`}>
                <Button
                  variant="primary"
                  size="md"
                  icon={<FileText className="w-4 h-4" />}
                >
                  View Full Report
                  <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </Link>
            )}
          </div>
        </div>

        {/* Decision Banner */}
        {report ? (
          <DecisionBanner
            decision={report.decision}
            riskLevel={report.risk_level}
            riskScore={report.risk_score}
            overallConfidence={report.overall_confidence}
          />
        ) : (
          <div className="p-5 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-xs text-blue-800 dark:text-blue-300 flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-500" />
            <span>This video is currently in state <strong>{video.status}</strong>. Full moderation assessment report is generating.</span>
          </div>
        )}

        {/* Workspace Grid: Video Player + Risk Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Player & Timeline (7 cols) */}
          <div className="lg:col-span-7 space-y-5">
            <VideoPlayer
              ref={playerRef}
              src={blobUrl}
              video={video}
              onTimeUpdate={setCurrentPlaybackTime}
            />

            <ModerationTimeline
              duration={duration}
              currentTime={currentPlaybackTime}
              findings={findings}
              selectedFindingId={selectedFinding?.id}
              onSelectFinding={handleSelectFinding}
              onSeek={handleSeek}
            />
          </div>

          {/* Right Column: Risk & Signal Profile (5 cols) */}
          <div className="lg:col-span-5 space-y-5">
            {report && (
              <RiskOverview
                riskLevel={report.risk_level}
                riskScore={report.risk_score}
                overallConfidence={report.overall_confidence}
                detectedCategories={report.detected_categories}
                createdAt={report.created_at}
              />
            )}
          </div>
        </div>

        {/* Workspace Tabs Section */}
        <div className="space-y-4 pt-4">
          <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-1 sm:space-x-4">
            <button
              onClick={() => setActiveTab('findings')}
              className={`py-3 px-3 text-xs sm:text-sm font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
                activeTab === 'findings'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              Policy Findings ({findings.length})
            </button>

            <button
              onClick={() => setActiveTab('evidence')}
              className={`py-3 px-3 text-xs sm:text-sm font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
                activeTab === 'evidence'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <Layers className="w-4 h-4 text-blue-500" />
              Traceable Evidence ({evidence.length})
            </button>

            <button
              onClick={() => setActiveTab('transcripts')}
              className={`py-3 px-3 text-xs sm:text-sm font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
                activeTab === 'transcripts'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <Mic className="w-4 h-4 text-emerald-500" />
              Transcripts ({transcripts.length})
            </button>

            <button
              onClick={() => setActiveTab('summary')}
              className={`py-3 px-3 text-xs sm:text-sm font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
                activeTab === 'summary'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <FileText className="w-4 h-4 text-purple-500" />
              AI Reasoning
            </button>
          </div>

          <div className="pt-2">
            {activeTab === 'findings' && (
              <FindingsList
                findings={findings}
                selectedFindingId={selectedFinding?.id}
                onSelectFinding={handleSelectFinding}
                onSeek={handleSeek}
              />
            )}

            {activeTab === 'evidence' && (
              <EvidenceGallery evidence={evidence} onSeek={handleSeek} />
            )}

            {activeTab === 'transcripts' && (
              <TranscriptsView transcripts={transcripts} onSeek={handleSeek} />
            )}

            {activeTab === 'summary' && report && (
              <ExecutiveSummary report={report} />
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
};
