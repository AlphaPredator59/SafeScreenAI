import type { ModerationDecision, RiskLevel, VideoStatus } from './api';

export interface SessionVideoRecord {
  videoId: string;
  filename: string;
  uploadedAt: string; // ISO string
  fileSize?: number;
  duration?: number;
  // Live metadata/report cached from backend
  status?: VideoStatus;
  decision?: ModerationDecision;
  riskLevel?: RiskLevel;
  riskScore?: number;
  violationCount?: number;
}

export interface SessionContextType {
  sessionId: string;
  sessionVideos: SessionVideoRecord[];
  addSessionVideo: (video: SessionVideoRecord, blobUrl?: string) => void;
  updateSessionVideo: (videoId: string, partial: Partial<SessionVideoRecord>) => void;
  removeSessionVideo: (videoId: string) => void;
  clearSession: () => void;
  getBlobUrl: (videoId: string) => string | undefined;
}
