import type {
  DrivingLogDetail,
  DrivingLogListResponse,
} from './types';

const DEFAULT_BASE_URL = 'http://localhost:8000/api';

function buildUrl(path: string, params?: Record<string, string | number | boolean>) {
  const base = import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE_URL;
  const url = new URL(path.replace(/^\//, ''), `${base.replace(/\/$/, '')}/`);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface FetchLogsOptions {
  includeDetails?: boolean;
  limit?: number;
  offset?: number;
}

export async function fetchLogs(options: FetchLogsOptions = {}): Promise<DrivingLogListResponse> {
  const { includeDetails, limit, offset } = options;
  const params: Record<string, string | number | boolean> = {};
  if (includeDetails) {
    params.include_details = true;
  }
  if (typeof limit === 'number') {
    params.limit = limit;
  }
  if (typeof offset === 'number') {
    params.offset = offset;
  }
  const url = buildUrl('/logs', Object.keys(params).length > 0 ? params : undefined);
  const response = await fetch(url);
  return handleResponse<DrivingLogListResponse>(response);
}

export async function fetchLogDetail(logId: string): Promise<DrivingLogDetail> {
  const url = buildUrl(`/logs/${logId}`);
  const response = await fetch(url);
  return handleResponse<DrivingLogDetail>(response);
}

export async function fetchLogImage(logId: string): Promise<string> {
  const url = buildUrl(`/logs/${logId}/image`);
  const response = await fetch(url);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to fetch preview for ${logId}`);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
