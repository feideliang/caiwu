import { post, get } from './request';
import type { CorrelationAnalysisResult, CorrelationRecord, CalibrationRequest, CorrelationListResponse } from '@/types/correlation';

export function analyzeCorrelations(data: Record<string, unknown> = {}) {
  return post<CorrelationAnalysisResult>('/correlations/analyze', data);
}

export function getCorrelations(params?: Record<string, unknown>) {
  return get<CorrelationListResponse>('/correlations', { params });
}

export function calibrateCorrelation(id: number, data: CalibrationRequest) {
  return post<CorrelationRecord>(`/correlations/${id}/calibrate`, data);
}
