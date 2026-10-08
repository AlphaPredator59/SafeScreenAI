import React, { useRef, useState } from 'react';
import { UploadCloud, Film, AlertCircle } from 'lucide-react';

const SUPPORTED_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv'];
const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024; // 500 MB limit from backend config

interface DropzoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export const Dropzone: React.FC<DropzoneProps> = ({ onFileSelect, disabled = false }) => {
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndSelectFile = (file: File) => {
    setValidationError(null);

    // 1. Validate file extension
    const extension = `.${file.name.split('.').pop()?.toLowerCase()}`;
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      setValidationError(
        `Unsupported video format (${extension}). Supported formats are: ${SUPPORTED_EXTENSIONS.join(', ')}`
      );
      return;
    }

    // 2. Validate file size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setValidationError(
        `Video size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 500 MB limit.`
      );
      return;
    }

    onFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (disabled) return;
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  return (
    <div className="w-full space-y-3">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 select-none ${
          disabled ? 'opacity-50 cursor-not-allowed bg-slate-50 dark:bg-slate-900/40' : ''
        } ${
          isDragOver
            ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/30 scale-[1.01]'
            : 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-blue-400 hover:bg-slate-50/50 dark:hover:bg-slate-800/40'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(',')}
          onChange={handleFileInputChange}
          disabled={disabled}
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div
            className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${
              isDragOver
                ? 'bg-blue-600 text-white'
                : 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400'
            }`}
          >
            <UploadCloud className="w-8 h-8" />
          </div>

          <div>
            <h3 className="text-base sm:text-lg font-semibold text-slate-900 dark:text-slate-100">
              Drop your video here
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              or <span className="text-blue-600 dark:text-blue-400 font-medium underline underline-offset-2">browse files</span> from your device
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-slate-400 dark:text-slate-500 pt-2">
            <span className="inline-flex items-center gap-1">
              <Film className="w-3.5 h-3.5" /> MP4, MOV, AVI, MKV
            </span>
            <span>•</span>
            <span>Max 500 MB</span>
            <span>•</span>
            <span>Max 30 minutes</span>
          </div>
        </div>
      </div>

      {validationError && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
};
