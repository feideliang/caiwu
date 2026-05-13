export type CalibrationStatus = 'confirm' | 'doubt' | 'reject';

export interface CorrelationPair {
  variable_x: string;
  variable_y: string;
  correlation_coefficient: number;
  p_value: number;
  sample_size: number;
}

export interface CorrelationAnalysisResult {
  pairs: CorrelationPair[];
  ai_explanation: string;
  disclaimer: string;
  analyzed_at: string;
}

export interface CorrelationRecord {
  id: number;
  variable_x: string;
  variable_y: string;
  correlation_coefficient: number;
  p_value: number;
  ai_explanation?: string;
  calibration_status?: CalibrationStatus | null;
  calibrated_by?: number;
  calibrated_at?: string;
  created_at: string;
}

export interface CorrelationListResponse {
  items: CorrelationRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CalibrationRequest {
  action: CalibrationStatus;
  notes?: string;
}
