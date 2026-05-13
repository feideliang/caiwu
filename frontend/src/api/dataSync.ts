import { get, post } from './request';

export interface EmailSyncBatch {
  id: number;
  batch_no: string;
  source_id: number | null;
  status: string;
  record_count: number;
  file_name: string | null;
  processed_at: string | null;
}

export interface EmailSyncBatchResponse {
  items: EmailSyncBatch[];
  total: number;
  page: number;
  page_size: number;
}

export function getEmailSyncBatches(params?: Record<string, unknown>) {
  return get<EmailSyncBatchResponse>('/data-sync/email/batches', { params });
}

export function runEmailSync() {
  return post('/data-sync/email/run', {});
}

export function testEmailConnection(sourceId?: number) {
  return post('/data-sync/email/test-connection', {}, { params: sourceId ? { source_id: sourceId } : {} });
}

export function retryEmailSyncBatch(batchId: number) {
  return post(`/data-sync/email/batches/${batchId}/retry`, {});
}
