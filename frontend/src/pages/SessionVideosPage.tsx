import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { SessionVideoCard } from '../components/session/SessionVideoCard';
import { EmptyState } from '../components/common/EmptyState';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { useSessionVideos } from '../hooks/useSessionVideos';
import { Film, UploadCloud, Search, Trash2, Info, AlertTriangle } from 'lucide-react';

export const SessionVideosPage: React.FC = () => {
  const { sessionVideos, clearSession } = useSessionVideos();
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'review' | 'rejected' | 'uploaded'>('all');
  const [isResetModalOpen, setIsResetModalOpen] = useState<boolean>(false);

  const filteredVideos = useMemo(() => {
    return sessionVideos.filter((video) => {
      // 1. Text search
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = video.filename.toLowerCase().includes(query);
        const matchesId = video.videoId.toLowerCase().includes(query);
        if (!matchesName && !matchesId) return false;
      }

      // 2. Filter
      if (statusFilter === 'completed') {
        return video.status === 'COMPLETED';
      }
      if (statusFilter === 'review') {
        return video.decision === 'REVIEW_REQUIRED';
      }
      if (statusFilter === 'rejected') {
        return video.decision === 'REJECTED' || (video.violationCount && video.violationCount > 0);
      }
      if (statusFilter === 'uploaded') {
        return video.status === 'UPLOADED' || video.status === 'PROCESSING' || video.status === 'QUEUED';
      }

      return true;
    });
  }, [sessionVideos, searchQuery, statusFilter]);

  const handleConfirmReset = () => {
    clearSession();
    setIsResetModalOpen(false);
  };

  return (
    <PageContainer>
      <div className="space-y-6">
        {/* Header & Session Notice */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="p-1 rounded bg-blue-600 text-white">
                <Film className="w-3.5 h-3.5" />
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                Workspace Scope
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
              Current Session Videos
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              Videos uploaded during your active reviewer session ({sessionVideos.length} recorded).
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Link to="/upload">
              <Button variant="primary" size="md" icon={<UploadCloud className="w-4 h-4" />}>
                Upload Video
              </Button>
            </Link>

            {sessionVideos.length > 0 && (
              <Button
                variant="outline"
                size="md"
                onClick={() => setIsResetModalOpen(true)}
                icon={<Trash2 className="w-4 h-4 text-slate-400" />}
                className="hover:border-red-300 dark:hover:border-red-900 hover:text-red-600"
              >
                Reset Session
              </Button>
            )}
          </div>
        </div>

        {/* Client-side visibility explanation notice */}
        <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-slate-800 dark:text-slate-200">Client-Side Session Visibility Notice</p>
            <p className="mt-0.5">
              The MVP backend does not provide user authentication or server-side tenant isolation. Session visibility is managed strictly within this browser tab. Closing this tab or clicking Reset Session purges the local session records.
            </p>
          </div>
        </div>

        {/* Controls: Search & Status Filters */}
        {sessionVideos.length > 0 && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search videos by filename or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 rounded-xl text-xs sm:text-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  statusFilter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                All ({sessionVideos.length})
              </button>

              <button
                onClick={() => setStatusFilter('completed')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  statusFilter === 'completed'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                Completed
              </button>

              <button
                onClick={() => setStatusFilter('review')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  statusFilter === 'review'
                    ? 'bg-amber-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                Review Required
              </button>

              <button
                onClick={() => setStatusFilter('rejected')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  statusFilter === 'rejected'
                    ? 'bg-red-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                Violations
              </button>

              <button
                onClick={() => setStatusFilter('uploaded')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  statusFilter === 'uploaded'
                    ? 'bg-slate-700 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }`}
              >
                In Progress
              </button>
            </div>
          </div>
        )}

        {/* Video Cards Grid */}
        {filteredVideos.length === 0 ? (
          <EmptyState
            icon={<Film className="w-7 h-7" />}
            title={sessionVideos.length === 0 ? 'No session videos yet' : 'No matching videos found'}
            description={
              sessionVideos.length === 0
                ? 'Videos you upload during this browser tab session will appear here.'
                : 'Try adjusting your search terms or status filters.'
            }
            action={
              sessionVideos.length === 0 ? (
                <Link to="/upload">
                  <Button variant="primary" size="md" icon={<UploadCloud className="w-4 h-4" />}>
                    Upload Video
                  </Button>
                </Link>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}>
                  Clear Filters
                </Button>
              )
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredVideos.map((video) => (
              <SessionVideoCard key={video.videoId} video={video} />
            ))}
          </div>
        )}

        {/* Confirmation Modal for Reset Session */}
        <Modal
          isOpen={isResetModalOpen}
          onClose={() => setIsResetModalOpen(false)}
          title="Reset Active Session?"
          maxWidth="md"
        >
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs">
              <AlertTriangle className="w-5 h-5 shrink-0 text-amber-600" />
              <div>
                <p className="font-semibold">Clear local session visibility?</p>
                <p className="mt-0.5">
                  This will remove all {sessionVideos.length} video references and in-memory playback handles from this browser tab. Backend database records remain unaffected.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setIsResetModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="danger" size="sm" onClick={handleConfirmReset}>
                Yes, Reset Session
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </PageContainer>
  );
};
