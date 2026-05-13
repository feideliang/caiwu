import { post, get } from './request';
import type { Report, ReportRequest } from '@/types/report';
import type { PaginatedResult } from '@/types/api';

export function createReport(data: ReportRequest) {
  return post<Report>('/reports', data);
}

export function getReports(params?: Record<string, unknown>) {
  return get<PaginatedResult<Report>>('/reports', { params });
}

export function getReport(id: number) {
  return get<Report>(`/reports/${id}`);
}

export function cancelReport(id: number) {
  return post(`/reports/${id}/cancel`);
}

export function retryReport(id: number) {
  return post(`/reports/${id}/retry`);
}

export function downloadReport(id: number) {
  return get<string>(`/reports/${id}/download`);
}
