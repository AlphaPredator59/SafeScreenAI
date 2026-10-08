import type { VideoResponse, VideoStatusResponse, VideoUploadResponse } from '../../types/api';
import { apiClient } from './client';

/**
 * Upload a video file to the backend ingestion endpoint.
 *
 * Supported formats: MP4, MOV, AVI, MKV (max 500MB, max 30 mins)
 */
export async function uploadVideo(file: File): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient<VideoUploadResponse>('/videos', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Fetch video public metadata and processing status.
 */
export async function getVideo(videoId: string): Promise<VideoResponse> {
  return apiClient<VideoResponse>(`/videos/${encodeURIComponent(videoId)}`);
}

/**
 * Retrieve current lifecycle status for a video.
 */
export async function getVideoStatus(videoId: string): Promise<VideoStatusResponse> {
  return apiClient<VideoStatusResponse>(`/videos/${encodeURIComponent(videoId)}/status`);
}
