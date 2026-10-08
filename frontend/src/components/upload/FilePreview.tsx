import React, { useEffect, useState } from 'react';
import { Film, CheckCircle2, ArrowRight, X } from 'lucide-react';
import { Button } from '../common/Button';
import { Card } from '../common/Card';

interface FilePreviewProps {
  file: File;
  onAnalyze: () => void;
  onCancel: () => void;
  isUploading: boolean;
}

export const FilePreview: React.FC<FilePreviewProps> = ({
  file,
  onAnalyze,
  onCancel,
  isUploading,
}) => {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const formatFileSize = (bytes: number): string => {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  return (
    <Card elevated className="p-6 overflow-hidden">
      <div className="flex flex-col md:flex-row gap-6 items-start">
        {/* Local Video Preview Player */}
        <div className="w-full md:w-64 h-40 bg-slate-950 rounded-xl overflow-hidden relative shrink-0 border border-slate-200 dark:border-slate-800 flex items-center justify-center">
          {previewUrl ? (
            <video
              src={previewUrl}
              className="w-full h-full object-cover"
              controls
              muted
              playsInline
            />
          ) : (
            <Film className="w-8 h-8 text-slate-600" />
          )}
        </div>

        {/* File Information */}
        <div className="flex-1 min-w-0 space-y-3 w-full">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                <h4 className="text-base font-semibold text-slate-900 dark:text-slate-100 truncate" title={file.name}>
                  {file.name}
                </h4>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                File size: <span className="font-medium text-slate-700 dark:text-slate-300">{formatFileSize(file.size)}</span> • Type: {file.type || 'video/mp4'}
              </p>
            </div>
            <button
              onClick={onCancel}
              disabled={isUploading}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Cancel file selection"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            This video will be uploaded to SafeScreen AI for multi-modal policy assessment (visual detection, speech transcription, context reasoning).
          </p>

          <div className="pt-2 flex items-center gap-3">
            <Button
              variant="primary"
              size="md"
              onClick={onAnalyze}
              isLoading={isUploading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              {isUploading ? 'Uploading to SafeScreen...' : 'Analyze Video'}
            </Button>
            <Button
              variant="ghost"
              size="md"
              onClick={onCancel}
              disabled={isUploading}
            >
              Choose Another Video
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
};
