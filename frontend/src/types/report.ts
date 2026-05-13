export type ReportType = 'revenue_daily' | 'gross_profit_daily' | 'department_daily' | 'product_line_daily' | 'custom';
export type ReportStatus = 'pending' | 'generating' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ReportFormat = 'word' | 'pdf';

export interface ReportRequest {
  type: ReportType;
  title?: string;
  date_from: string;
  date_to: string;
  format: ReportFormat;
  include_charts?: boolean;
  sections?: string[];
}

export interface Report {
  id: number;
  report_type: string;
  status: string;
  current_step?: string;
  period?: string;
  output_format: string;
  file_path?: string;
  file_name?: string;
  user_id: number;
  error_message?: string;
  task_id?: string;
  celery_task_id?: string;
  retry_count: number;
  parent_task_id?: number;
  params?: Record<string, unknown>;
  created_at: string;
  completed_at?: string;
}
