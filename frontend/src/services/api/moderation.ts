import type { EvidenceListResponse, ModerationReportResponse } from '../../types/api';
import { apiClient } from './client';

/**
 * Fetch the complete, explainable platform moderation report for an analyzed video.
 * Returns 404 via ApiError if moderation has not yet completed or was not persisted.
 */
export async function getModerationReport(videoId: string): Promise<ModerationReportResponse> {
  return apiClient<ModerationReportResponse>(`/videos/${encodeURIComponent(videoId)}/moderation`);
}

/**
 * Fetch all traceable multi-modal evidence items supporting policy findings.
 */
export async function getEvidence(videoId: string): Promise<EvidenceListResponse> {
  return apiClient<EvidenceListResponse>(`/videos/${encodeURIComponent(videoId)}/evidence`);
}
