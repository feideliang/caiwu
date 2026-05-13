import { get } from './request';
import type { DrillSummary, DrillDepartment, DrillProduct, DrillRecord } from '@/types/drilldown';

export function getDrillSummary(reportId: string) {
  return get<DrillSummary>(`/drilldowns/${reportId}/summary`);
}

export function getDrillDepartments(reportId: string, params?: Record<string, unknown>) {
  return get<DrillDepartment[]>(`/drilldowns/${reportId}/departments`, { params });
}

export function getDrillProducts(reportId: string, params?: Record<string, unknown>) {
  return get<DrillProduct[]>(`/drilldowns/${reportId}/products`, { params });
}

export function getDrillProductsByDept(reportId: string, deptId: number) {
  return get<DrillProduct[]>(`/drilldowns/${reportId}/departments/${deptId}/products`);
}

export function getDrillRecords(reportId: string, params?: Record<string, unknown>) {
  return get<DrillRecord[]>(`/drilldowns/${reportId}/records`, { params });
}

export function getDrillRecordsByProduct(reportId: string, deptId: number, productId: number, params?: Record<string, unknown>) {
  return get<DrillRecord[]>(`/drilldowns/${reportId}/departments/${deptId}/products/${productId}/records`, { params });
}

export function getRecord(recordId: number) {
  return get(`/drilldowns/records/${recordId}`);
}
