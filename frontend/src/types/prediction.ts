export type PredictionType = 'cash_flow' | 'ar_aging' | 'revenue' | 'dso' | 'cost' | 'gross_profit';
export type PredictionStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface PredictionRequest {
  metric_name: string;
  prediction_type: string;
  horizon: number;
}

export interface PredictionDataPoint {
  date: string;
  value: number;
  lower_bound: number;
  upper_bound: number;
  is_actual: boolean;
}

export interface ConfidenceBand {
  upper: number[];
  lower: number[];
}

export interface PredictionResult {
  id: number;
  metric_name: string;
  prediction_type: string | null;
  horizon: number | null;
  forecast_values: Record<string, number>;
  confidence_band: Record<string, { lower: number; upper: number }>;
  historical_values: Record<string, number>;
  model_type: string | null;
  training_window: number | null;
  mape: number | null;
  accuracy_score: number | null;
  accepted: boolean;
  rejected_reason: string | null;
  message?: string | null;
  computed_at: string | null;
  // Compatibility fields
  type?: PredictionType;
  status?: PredictionStatus;
  horizon_months?: number;
  data_points?: PredictionDataPoint[];
  confidence?: ConfidenceBand;
  created_at?: string;
  completed_at?: string;
  error_message?: string;
}
