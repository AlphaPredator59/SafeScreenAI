import type { HealthResponse } from '../../types/api';
import { apiClient } from './client';

export async function getHealth(): Promise<HealthResponse> {
  return apiClient<HealthResponse>('/health');
}
