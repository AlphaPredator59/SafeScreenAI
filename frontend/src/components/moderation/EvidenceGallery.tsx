import React, { useState } from 'react';
import type { EvidenceItemResponse } from '../../types/api';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Clock, Eye, Mic, FileText, Layers, Play } from 'lucide-react';

interface EvidenceGalleryProps {
  evidence: EvidenceItemResponse[];
  onSeek: (seconds: number) => void;
}

export const EvidenceGallery: React.FC<EvidenceGalleryProps> = ({ evidence, onSeek }) => {
  const [selectedItem, setSelectedItem] = useState<EvidenceItemResponse | null>(null);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}.${ms}s`;
  };

  const getModalityIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'visual':
      case 'frame':
        return <Eye className="w-3.5 h-3.5 text-blue-500" />;
      case 'transcript':
        return <Mic className="w-3.5 h-3.5 text-emerald-500" />;
      case 'text_signal':
        return <FileText className="w-3.5 h-3.5 text-amber-500" />;
      default:
        return <Layers className="w-3.5 h-3.5 text-slate-500" />;
    }
  };

  if (evidence.length === 0) {
    return (
      <Card className="p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mx-auto mb-3">
          <Layers className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
          No Traceable Evidence Recorded
        </h4>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
          No discrete multi-modal evidence items were recorded for this analysis.
        </p>
      </Card>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {evidence.map((item) => (
          <Card
            key={item.id}
            onClick={() => setSelectedItem(item)}
            className="p-4 cursor-pointer hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-xs transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <Badge variant="default" size="sm" icon={getModalityIcon(item.type)}>
                  {item.type}
                </Badge>
                <span className="text-xs font-mono font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTime(item.timestamp)}
                </span>
              </div>

              {item.content ? (
                <p className="text-xs text-slate-700 dark:text-slate-300 line-clamp-3 leading-relaxed mt-1">
                  {item.content}
                </p>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500 italic mt-1">
                  No textual summary available.
                </p>
              )}
            </div>

            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400 dark:text-slate-500">
              <span className="truncate max-w-[120px] font-mono" title={item.reference || item.id}>
                {item.reference ? item.reference.split(/[\\/]/).pop() : item.id.substring(0, 8)}
              </span>

              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onSeek(item.timestamp);
                }}
                icon={<Play className="w-3 h-3 fill-current" />}
                className="text-[11px] h-6 px-2 text-blue-600 dark:text-blue-400"
              >
                Seek
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Modal Detail for Evidence Item */}
      <Modal
        isOpen={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
        title="Evidence Trace Detail"
        maxWidth="lg"
      >
        {selectedItem && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="flex items-center gap-2">
                <Badge variant="info" size="md" icon={getModalityIcon(selectedItem.type)}>
                  Modality: {selectedItem.type}
                </Badge>
              </div>
              <span className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300">
                Timestamp: {formatTime(selectedItem.timestamp)}
              </span>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5">
                Content & Description
              </h5>
              <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 leading-relaxed">
                {selectedItem.content || 'No textual content recorded.'}
              </div>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5">
                Backend Reference ID
              </h5>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 font-mono text-xs text-slate-600 dark:text-slate-300 break-all select-all">
                {selectedItem.reference || selectedItem.id}
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  onSeek(selectedItem.timestamp);
                  setSelectedItem(null);
                }}
                icon={<Play className="w-3.5 h-3.5 fill-current" />}
              >
                Jump to Video Timestamp ({formatTime(selectedItem.timestamp)})
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
};
