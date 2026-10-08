import React from 'react';
import { Card } from '../common/Card';
import { Eye, Mic, FileText, Brain, ShieldAlert, FileCheck2, Info } from 'lucide-react';

export const PipelineOverview: React.FC = () => {
  const conceptualStages = [
    {
      step: '01',
      title: 'Frame & Audio Sampling',
      subtitle: 'Deterministic 1.0s extraction',
      icon: <Eye className="w-4 h-4 text-blue-500" />,
      description: 'Extracts timestamped frames via OpenCV and strips audio tracks to standard WAV format via FFmpeg.',
    },
    {
      step: '02',
      title: 'Visual Object Detection',
      subtitle: 'YOLOv8 Computer Vision',
      icon: <Eye className="w-4 h-4 text-indigo-500" />,
      description: 'Scans frame artifacts for dual-use objects, explicit weapons, and potential physical hazards.',
    },
    {
      step: '03',
      title: 'Speech Transcription',
      subtitle: 'Whisper Audio Model',
      icon: <Mic className="w-4 h-4 text-emerald-500" />,
      description: 'Transcribes spoken dialogue into timestamped segments synchronized with video playtime.',
    },
    {
      step: '04',
      title: 'Text & Language Moderation',
      subtitle: 'Toxic-BERT Classifier',
      icon: <FileText className="w-4 h-4 text-amber-500" />,
      description: 'Evaluates spoken dialogue segments for profanity, hate speech, threats, and toxic language.',
    },
    {
      step: '05',
      title: 'Temporal Context Reasoning',
      subtitle: 'Qwen 2.5-VL Multimodal',
      icon: <Brain className="w-4 h-4 text-purple-500" />,
      description: 'Disambiguates benign actions (e.g. cooking, sports, acting) from hostile incidents across time windows.',
    },
    {
      step: '06',
      title: 'Policy Decision & Report',
      subtitle: 'Deterministic ModerationEngine',
      icon: <ShieldAlert className="w-4 h-4 text-rose-500" />,
      description: 'Synthesizes multi-modal signals into calibrated risk scores, policy findings, and explainable justifications.',
    },
  ];

  return (
    <Card className="p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <FileCheck2 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            System Pipeline Overview (Conceptual)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Architectural representation of SafeScreen AI's multi-modal moderation pipeline
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-600 dark:text-slate-400">
          <Info className="w-3.5 h-3.5 text-blue-500" />
          <span>Stage telemetry internal to backend</span>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {conceptualStages.map((stage) => (
          <div
            key={stage.step}
            className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold text-slate-400 dark:text-slate-500">
                  {stage.step}
                </span>
                <div className="p-1.5 rounded-lg bg-white dark:bg-slate-800 shadow-2xs border border-slate-100 dark:border-slate-700/60">
                  {stage.icon}
                </div>
              </div>

              <h4 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                {stage.title}
              </h4>
              <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                {stage.subtitle}
              </p>

              <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {stage.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
        <Info className="w-3.5 h-3.5 shrink-0" />
        <span>
          Note: Individual stage progress is executed on the backend server. The live status card above reflects the verified backend status.
        </span>
      </div>
    </Card>
  );
};
