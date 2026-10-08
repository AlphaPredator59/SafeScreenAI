import React from 'react';
import { Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { SessionMetricsGrid } from '../components/session/SessionMetricsGrid';
import { SessionVideoCard } from '../components/session/SessionVideoCard';
import { EmptyState } from '../components/common/EmptyState';
import { Button } from '../components/common/Button';
import { useSessionVideos } from '../hooks/useSessionVideos';
import { UploadCloud, Film, ArrowRight, ShieldCheck, Sparkles, Layers } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { sessionVideos, metrics } = useSessionVideos();

  return (
    <PageContainer>
      <div className="space-y-10">
        {/* Hero Section */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-900 via-slate-900 to-slate-950 text-white p-8 sm:p-12 border border-slate-800 shadow-xl">
          <div className="relative z-10 max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-400/20 text-blue-400 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Multi-Modal Trust & Safety Assessment</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
              Analyze your video before you publish.
            </h1>

            <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
              Upload video content to evaluate potential policy violations across computer vision, audio dialogue, and contextual reasoning. SafeScreen generates an explainable, transparent moderation report.
            </p>

            <div className="pt-4 flex flex-wrap items-center gap-3">
              <Link to="/upload">
                <Button
                  variant="primary"
                  size="lg"
                  icon={<UploadCloud className="w-5 h-5" />}
                  className="bg-blue-500 hover:bg-blue-600 shadow-lg shadow-blue-500/25"
                >
                  Upload Video
                </Button>
              </Link>

              {sessionVideos.length > 0 && (
                <Link to="/videos">
                  <Button
                    variant="outline"
                    size="lg"
                    icon={<Film className="w-5 h-5" />}
                    className="border-slate-700 text-slate-200 hover:bg-slate-800/80"
                  >
                    View Session Videos ({sessionVideos.length})
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* Decorative geometric background elements */}
          <div className="absolute right-0 top-0 bottom-0 w-1/3 opacity-10 pointer-events-none hidden lg:flex items-center justify-center">
            <ShieldCheck className="w-96 h-96 text-blue-400 -mr-16" />
          </div>
        </div>

        {/* Real Session Metrics */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Active Session Telemetry
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Metrics calculated from videos uploaded in this browser tab
              </p>
            </div>
          </div>

          <SessionMetricsGrid metrics={metrics} />
        </section>

        {/* Recent Session Videos */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Film className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                Recent Session Uploads
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Videos processed in this tab session
              </p>
            </div>

            {sessionVideos.length > 0 && (
              <Link
                to="/videos"
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
              >
                All Session Videos
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>

          {sessionVideos.length === 0 ? (
            <EmptyState
              icon={<UploadCloud className="w-7 h-7" />}
              title="No videos analyzed in this session yet"
              description="Upload your first video to start an AI-powered moderation analysis across computer vision, audio, and scene context."
              action={
                <Link to="/upload">
                  <Button variant="primary" size="md" icon={<UploadCloud className="w-4 h-4" />}>
                    Upload First Video
                  </Button>
                </Link>
              }
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessionVideos.slice(0, 6).map((video) => (
                <SessionVideoCard key={video.videoId} video={video} />
              ))}
            </div>
          )}
        </section>

        {/* Platform Architecture Highlights */}
        <section className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                SafeScreen Multi-Modal Architecture
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Integrated vision models, audio transcription, toxic text classification, and contextual reasoning
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-600 dark:text-slate-300">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
              <span className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                Computer Vision & YOLO
              </span>
              Deterministic 1.0s frame sampling detecting physical objects, hazard classifications, and potential weapons.
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
              <span className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                Audio & Toxic-BERT
              </span>
              Speech transcription via Whisper combined with Toxic-BERT to evaluate dialogue for threats and hate speech.
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
              <span className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                Context Reasoner & Qwen
              </span>
              Temporal multi-window reasoning to distinguish benign contexts (cooking, stunts) from true policy violations.
            </div>
          </div>
        </section>
      </div>
    </PageContainer>
  );
};
