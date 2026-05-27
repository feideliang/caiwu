// frontend/src/types/analysis.ts

export interface MetricRecommendation {
  metric_name: string;
  metric_key: string;
  description: string;
  current_value?: number;
  benchmark?: number;
  status: 'normal' | 'warning' | 'critical';
  recommendation: string;
}

export interface AnomalyAlert {
  metric: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
  value?: number;
  threshold?: number;
}

export interface AnalysisRecommendations {
  page_type: string;
  summary: string;
  metrics: MetricRecommendation[];
  suggested_questions: string[];
  anomalies: AnomalyAlert[];
  drill_down_path: string[];
}

export interface AnalysisRecommendationRequest {
  page_type: string;
  period?: string;
  period_compare_type?: string;
  period_dimension?: string;
  department?: string;
  product?: string;
  customer?: string;
}
