import { get } from './request';
import type { CoreMetricsResponse, BreakdownItem } from '@/types/metrics';
import type { AxiosResponse } from 'axios';
import type { ApiResponse } from '@/types/api';

export async function getCoreMetrics(params?: {
  period?: string;
  dimension?: string;
  entity?: string;
  compare?: string;
  period_dimension?: string;
  compare_period?: string;
  period_start?: string;
  period_end?: string;
  high_margin_threshold?: number;
  product?: string;
  department?: string;
  customer?: string;
}): Promise<AxiosResponse<ApiResponse<CoreMetricsResponse>>> {
  return get<CoreMetricsResponse>('/metrics/core', { params });
}

export function getMetricsBreakdown(params: {
  metric: string;
  period: string;
  dimension: string;
  entity?: string;
}) {
  return get<{ items: BreakdownItem[] }>('/metrics/breakdown', { params });
}
