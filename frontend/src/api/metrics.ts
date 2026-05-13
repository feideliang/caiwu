import { get } from './request';
import type { CoreMetricsResponse, BreakdownItem } from '@/types/metrics';
import type { AxiosResponse } from 'axios';
import type { ApiResponse } from '@/types/api';

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function cacheKey(params?: Record<string, unknown>): string {
  return 'metrics_core_' + JSON.stringify(params || {});
}

export async function getCoreMetrics(params?: {
  period?: string;
  dimension?: string;
  entity?: string;
  compare?: string;
  high_margin_threshold?: number;
}): Promise<AxiosResponse<ApiResponse<CoreMetricsResponse>>> {
  const key = cacheKey(params as Record<string, unknown>);
  const raw = sessionStorage.getItem(key);
  if (raw) {
    try {
      const { data, ts } = JSON.parse(raw);
      if (Date.now() - ts < CACHE_TTL) {
        return { data, status: 200, statusText: 'OK', headers: {}, config: {} } as AxiosResponse<ApiResponse<CoreMetricsResponse>>;
      }
    } catch { /* ignore corrupt cache */ }
  }

  const resp = await get<CoreMetricsResponse>('/metrics/core', { params });
  sessionStorage.setItem(key, JSON.stringify({ data: resp.data, ts: Date.now() }));
  return resp;
}

export function getMetricsBreakdown(params: {
  metric: string;
  period: string;
  dimension: string;
  entity?: string;
}) {
  return get<{ items: BreakdownItem[] }>('/metrics/breakdown', { params });
}
