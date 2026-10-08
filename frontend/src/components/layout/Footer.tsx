import React, { useEffect, useState } from 'react';
import { Shield, CheckCircle2, AlertTriangle } from 'lucide-react';
import { getHealth } from '../../services/api/health';
import type { HealthResponse } from '../../types/api';

export const Footer: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    getHealth()
      .then((data) => {
        if (isMounted) {
          setHealth(data);
          setIsHealthy(data.status === 'ok');
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsHealthy(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <footer className="w-full border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-6 text-xs text-slate-500 dark:text-slate-400 no-print">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Left: Branding & Disclaimer */}
        <div className="flex items-center gap-2.5 text-center md:text-left">
          <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
          <p>
            <span className="font-semibold text-slate-700 dark:text-slate-300">SafeScreen AI</span> — Explainable Video Moderation Engine.
            <span className="ml-2 text-slate-400 dark:text-slate-500 hidden sm:inline">
              Session visibility is client-managed. Videos are tracked in this browser tab.
            </span>
          </p>
        </div>

        {/* Right: Live Backend Service Indicator */}
        <div className="flex items-center gap-2">
          {isHealthy === true ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>Backend: {health?.service || 'SafeScreen AI'} (Operational)</span>
            </span>
          ) : isHealthy === false ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-400 border border-red-200 dark:border-red-800">
              <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              <span>Backend Offline</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
              <span className="w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
              <span>Checking Backend...</span>
            </span>
          )}
        </div>
      </div>
    </footer>
  );
};
