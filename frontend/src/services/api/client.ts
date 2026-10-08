const BASE_URL = '/api/v1';

export class SafeScreenApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'SafeScreenApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Perform a typed HTTP request against the SafeScreen backend API.
 */
export async function apiClient<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  const headers: HeadersInit = {
    ...options?.headers,
  };

  // If body is NOT FormData, default to application/json
  if (options?.body && !(options.body instanceof FormData)) {
    (headers as Record<string, string>)['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new SafeScreenApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed. Is the backend server running?'
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const errorJson = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof errorJson.detail === 'string') {
        detail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        detail = errorJson.detail.map((d) => (typeof d === 'string' ? d : d.msg || '')).join(', ');
      }
    } catch {
      // Fallback to text status if not JSON
      detail = response.statusText || detail;
    }
    throw new SafeScreenApiError(response.status, detail);
  }

  // Handle 204 or empty responses
  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
