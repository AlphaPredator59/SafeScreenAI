import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { Dropzone } from '../components/upload/Dropzone';
import { FilePreview } from '../components/upload/FilePreview';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { uploadVideo } from '../services/api/videos';
import { useSession } from '../store/sessionContext';
import { UploadCloud, Shield, CheckCircle } from 'lucide-react';

export const UploadPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const navigate = useNavigate();
  const { addSessionVideo } = useSession();

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setUploadError(null);
  };

  const handleCancel = () => {
    setSelectedFile(null);
    setUploadError(null);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      // Create local object URL for instant, zero-latency playback in current tab
      const blobUrl = URL.createObjectURL(selectedFile);

      // Perform real upload to backend API
      const response = await uploadVideo(selectedFile);

      // Register video into client-side session store with local blob URL
      addSessionVideo(
        {
          videoId: response.video_id,
          filename: selectedFile.name,
          uploadedAt: new Date().toISOString(),
          fileSize: selectedFile.size,
          status: response.status,
        },
        blobUrl
      );

      // Navigate to live processing status page
      navigate(`/processing/${response.video_id}`);
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : 'Video upload failed. Is the backend server running?'
      );
      setIsUploading(false);
    }
  };

  return (
    <PageContainer maxWidth="5xl">
      <div className="space-y-8">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1 rounded bg-blue-600 text-white">
              <UploadCloud className="w-3.5 h-3.5" />
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
              Video Ingestion
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Upload Video for Moderation Analysis
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Submit an MP4, MOV, AVI, or MKV file (max 500 MB) to evaluate against SafeScreen trust and safety guidelines.
          </p>
        </div>

        {/* Upload Error Banner */}
        {uploadError && (
          <ErrorAlert
            title="Upload Failed"
            message={uploadError}
            onRetry={handleAnalyze}
          />
        )}

        {/* Dropzone or File Preview */}
        {!selectedFile ? (
          <Dropzone onFileSelect={handleFileSelect} disabled={isUploading} />
        ) : (
          <FilePreview
            file={selectedFile}
            onAnalyze={handleAnalyze}
            onCancel={handleCancel}
            isUploading={isUploading}
          />
        )}

        {/* Security & Validation Notice */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-500 dark:text-slate-400">
          <div className="flex items-start gap-2.5">
            <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5">
                Multi-Modal Inspection
              </span>
              Validates visual elements, dialogue text, and acoustic signals without publishing.
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5">
                File Integrity Validation
              </span>
              Backend strictly checks file headers, container MIME types, duration, and dimensions.
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <UploadCloud className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5">
                Session Isolation
              </span>
              Videos uploaded in this tab remain scoped to your active reviewer workspace.
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
};
