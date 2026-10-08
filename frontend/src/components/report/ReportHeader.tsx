import React from 'react';
import { Printer, Download, ArrowLeft, Shield } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ModerationReportResponse } from '../../types/api';
import { DecisionBadge, RiskBadge } from '../common/Badge';
import { Button } from '../common/Button';

interface ReportHeaderProps {
  report: ModerationReportResponse;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({ report }) => {
  const handlePrint = () => {
    window.print();
  };

  const handleExportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `SafeScreen_Report_${report.video_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const formatDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString(undefined, {
        dateStyle: 'full',
        timeStyle: 'medium',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="pb-6 border-b border-slate-200 dark:border-slate-800 space-y-4">
      {/* Back button and actions */}
      <div className="flex items-center justify-between no-print">
        <Link
          to={`/videos/${report.video_id}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Video Workspace
        </Link>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportJson}
            icon={<Download className="w-3.5 h-3.5" />}
          >
            Export JSON
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handlePrint}
            icon={<Printer className="w-3.5 h-3.5" />}
          >
            Print Report
          </Button>
        </div>
      </div>

      {/* Main Header Content */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1 rounded bg-blue-600 text-white">
              <Shield className="w-3.5 h-3.5" />
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
              SafeScreen AI Platform Assessment
            </span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            {report.filename}
          </h1>

          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 font-mono">
            Report ID: {report.video_id} • Generated: {formatDate(report.created_at)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <DecisionBadge decision={report.decision} size="md" />
          <RiskBadge riskLevel={report.risk_level} size="md" />
        </div>
      </div>
    </div>
  );
};
