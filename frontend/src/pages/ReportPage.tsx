import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { ReportHeader } from '../components/report/ReportHeader';
import { ExecutiveSummary } from '../components/report/ExecutiveSummary';
import { FindingsMatrix } from '../components/report/FindingsMatrix';
import { TranscriptsView } from '../components/report/TranscriptsView';
import { EvidenceGallery } from '../components/moderation/EvidenceGallery';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { ReportSkeleton } from '../components/common/LoadingSkeleton';
import { Button } from '../components/common/Button';
import { useModerationReport } from '../hooks/useModerationReport';
import { ArrowLeft, Layers, ShieldCheck } from 'lucide-react';

export const ReportPage: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const { report, isLoading, error, refetch } = useModerationReport(videoId);

  if (isLoading) {
    return (
      <PageContainer maxWidth="5xl">
        <ReportSkeleton />
      </PageContainer>
    );
  }

  if (error || !report) {
    return (
      <PageContainer maxWidth="5xl">
        <div className="space-y-4 max-w-2xl mx-auto py-10">
          <ErrorAlert
            title="Moderation Report Unavailable"
            message={error || 'The formal report for this video could not be retrieved.'}
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

  return (
    <PageContainer maxWidth="5xl">
      <div className="space-y-8 print:space-y-6">
        {/* Report Header (Print & Export Actions) */}
        <ReportHeader report={report} />

        {/* Executive Summary & AI Justification */}
        <ExecutiveSummary report={report} />

        {/* Discrete Policy Findings Matrix */}
        <FindingsMatrix findings={report.findings} />

        {/* Traceable Evidence Items */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Traceable Evidence Artifacts ({report.evidence.length})
            </h3>
          </div>
          <EvidenceGallery evidence={report.evidence} onSeek={() => {}} />
        </div>

        {/* Spoken Audio Transcripts */}
        <TranscriptsView transcripts={report.transcripts} />

        {/* Formal Report Footer */}
        <div className="pt-8 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-400 dark:text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Authenticated SafeScreen AI Moderation Assessment</span>
          </div>
          <span className="font-mono">Assessment ID: {report.video_id}</span>
        </div>
      </div>
    </PageContainer>
  );
};
