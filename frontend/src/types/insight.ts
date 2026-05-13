export type InsightType = 'anomaly' | 'trend' | 'correlation' | 'threshold' | 'forecast';
export type InsightStatus = 'unread' | 'read' | 'process' | 'ignore';
export type InsightSeverity = 'high' | 'medium' | 'low';

export interface InsightItem {
  id: number;
  type: InsightType;
  title: string;
  content: string;
  confidence: number;
  status: InsightStatus;
  created_at: string;
}

export interface InsightListResponse {
  items: InsightItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Insight {
  id: number;
  type: InsightType;
  title: string;
  description: string;
  severity: InsightSeverity;
  confidence: number;
  status: InsightStatus;
  related_metric: string;
  related_chart_id?: string;
  data_json?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface InsightSummary {
  total: number;
  unread: number;
  by_type: Record<InsightType, number>;
  by_severity: Record<InsightSeverity, number>;
}
