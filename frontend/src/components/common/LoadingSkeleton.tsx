import React from 'react';

export const LoadingSkeleton: React.FC<{ className?: string }> = ({ className = 'h-4 w-full' }) => {
  return (
    <div
      className={`animate-pulse bg-slate-200 dark:bg-slate-800 rounded-md ${className}`}
    />
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
      <div className="flex justify-between items-center">
        <LoadingSkeleton className="h-4 w-28" />
        <LoadingSkeleton className="h-8 w-8 rounded-lg" />
      </div>
      <LoadingSkeleton className="h-8 w-20" />
      <LoadingSkeleton className="h-3 w-40" />
    </div>
  );
};

export const ReportSkeleton: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
        <LoadingSkeleton className="h-6 w-48" />
        <LoadingSkeleton className="h-4 w-3/4" />
        <LoadingSkeleton className="h-4 w-1/2" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
        <LoadingSkeleton className="h-5 w-32" />
        <div className="space-y-2">
          <LoadingSkeleton className="h-10 w-full" />
          <LoadingSkeleton className="h-10 w-full" />
          <LoadingSkeleton className="h-10 w-full" />
        </div>
      </div>
    </div>
  );
};
