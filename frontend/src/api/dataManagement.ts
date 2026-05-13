import { get, post, put, del } from './request'

export interface DataSourceItem {
  id: number;
  name: string;
  source_type: string;
  connection_config?: Record<string, unknown> | null;
  is_active: boolean;
  priority: number;
  last_sync_at: string | null;
  created_at: string;
}
export function getDataSources(params?: Record<string, unknown>) { return get('/data-sources', { params }) }
export function getDataSource(id: number) { return get(`/data-sources/${id}`) }
export function createDataSource(data: Record<string, unknown>) { return post('/data-sources', data) }
export function updateDataSource(id: number, data: Record<string, unknown>) { return put(`/data-sources/${id}`, data) }
export function deleteDataSource(id: number) { return del(`/data-sources/${id}`) }
export function getDataQualitySummary() { return get('/data-quality/summary') }
export function getDataQualityErrors(params?: Record<string, unknown>) { return get('/data-quality/errors', { params }) }
export function uploadExcel(file: File, sourceId?: number, syncMode?: string) {
  const fd = new FormData(); fd.append('file', file)
  if (sourceId !== undefined) fd.append('source_id', String(sourceId))
  if (syncMode) fd.append('sync_mode', syncMode)
  return post('/uploads/excel', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export function getUsers(params?: Record<string, unknown>) { return get('/users', { params }) }
export function createUser(data: Record<string, unknown>) { return post('/users', data) }
export function deleteUser(id: number) { return del(`/users/${id}`) }
export function getAuditLogs(params?: Record<string, unknown>) { return get('/audit/logs', { params }) }
