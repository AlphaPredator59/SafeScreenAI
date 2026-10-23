/**
 * Public API response and entity types matching the SafeScreen FastAPI backend schemas.
 *
 * Source of truth:
 * - backend/app/db/enums.py
 * - backend/app/schemas/health.py
 * - backend/app/schemas/video.py
 * - backend/app/schemas/moderation.py
 */

// 1. Controlled domain enums
export type VideoStatus =
  | 'UPLOADED'
  | 'QUEUED'
  | 'PROCESSING'
  | 'ANALYZING'
  | 'COMPLETED'
  | 'FAILED';

export type ModerationDecision =
  | 'APPROVED'
  | 'REVIEW_REQUIRED'
  | 'REJECTED';

export type RiskLevel =
  | 'LOW'
  | 'MEDIUM'
  | 'HIGH'
  | 'CRITICAL';

// 2. Health schemas
export interface HealthResponse {
  status: string;
  service: string;
}

// 3. Video schemas
export interface VideoUploadResponse {
  video_id: string;
  status: VideoStatus;
}

export interface VideoStatusResponse {
  video_id: string;
  status: VideoStatus;
}

export interface VideoResponse {
  video_id: string;
  status: VideoStatus;
  filename: string;
  duration: number;
  file_size: number;
  width: number;
  height: number;
  fps: number;
  created_at: string; // ISO 8601 string
}

// 4. Moderation & Evidence schemas
export interface EvidenceItemResponse {
  id: string;
  type: string;
  timestamp: number;
  content: string | null;
  reference: string | null;
}

export interface PolicyEventResponse {
  id?: string | null;
  start_time: number;
  end_time: number;
  confidence: number;
  evidence_ids?: string[];
  evidence_types?: string[];
  description?: string;
}

export interface FindingResponse {
  id: string;
  category: string;
  severity?: number;
  confidence: number;
  summary?: string | null;
  start_timestamp: number;
  end_timestamp: number | null;
  explanation: string | null;
  evidence_references: string[];
  events?: PolicyEventResponse[];
}

export type PolicyFindingResponse = FindingResponse;

export interface TranscriptSegmentResponse {
  start_timestamp: number;
  end_timestamp: number;
  text: string;
}

export interface AIJustificationResponse {
  visual_evidence: string[];
  audio_text_evidence: string[];
  contextual_analysis: string;
  policy_rationale: string[];
  uncertainty: string[];
  is_fallback?: boolean;
}

export interface ModerationReportResponse {
  video_id: string;
  filename: string;
  created_at: string; // ISO 8601 string
  decision: ModerationDecision;
  risk_level: RiskLevel;
  risk_score: number;
  overall_confidence: number;
  detected_categories: string[];
  explanation: string;
  findings: FindingResponse[];
  evidence: EvidenceItemResponse[];
  transcripts: TranscriptSegmentResponse[];
  executive_summary?: string;
  ai_justification?: AIJustificationResponse;
}

export interface EvidenceListResponse {
  video_id: string;
  total_count: number;
  evidence: EvidenceItemResponse[];
}

// 5. Client API Error structure
export interface ApiError {
  status: number;
  detail: string;
}
