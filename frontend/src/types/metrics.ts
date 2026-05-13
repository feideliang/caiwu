export interface CoreMetricsSummary {
  revenue?: number;
  tax_excluded_cost?: number;
  gross_profit?: number;
  gross_margin?: number;
  gross_margin_contribution?: number;
  customer_concentration_top3?: number;
  product_concentration_top3?: number;
  high_margin_order_ratio?: number;
  revenue_yoy_growth?: number;
  gross_profit_yoy_growth?: number;
  top_customer_share?: number;
  top_product_margin_share?: number;
  revenue_consecutive_growth?: number;
  gross_profit_consecutive_growth?: number;
  gross_margin_volatility?: number;
  margin_change_analysis?: MarginChangeItem[];
  // Analysis page extensions
  revenue_mom_growth?: number;
  gross_profit_mom_growth?: number;
  order_count?: number;
  achievement_rate?: number;
  loss_ratio?: number;
  core_market_line?: string;
  highest_value_market_line?: string;
}

export interface MarginChangeItem {
  dimension_value: string;
  current_revenue: number;
  current_share: number;
  current_margin: number;
  previous_revenue: number;
  previous_share: number;
  previous_margin: number;
  share_change: number;
  margin_change: number;
  structure_impact: number;
  margin_impact: number;
  total_impact: number;
}

export interface BreakdownItem {
  dimension_value: string;
  revenue?: number;
  tax_excluded_cost?: number;
  gross_profit?: number;
  gross_margin?: number;
  gross_margin_contribution?: number;
  order_count?: number;
  avg_order_value?: number;
  revenue_yoy_growth?: number;
  calculable?: boolean;
  missing_fields?: string[];
}

export interface TrendDataPoint {
  period: string;
  revenue?: number;
  gross_profit?: number;
  gross_margin?: number;
  revenue_mom_growth?: number;
  gross_profit_mom_growth?: number;
}

export interface DataQuality {
  calculable: boolean;
  missing_fields: string[];
  warnings: string[];
}

export interface DimensionTrendPoint {
  period: string;
  dimension_value: string;
  revenue?: number;
  gross_profit?: number;
  gross_margin?: number;
}

export interface CoreMetricsResponse {
  period: string;
  dimension: string;
  summary: CoreMetricsSummary;
  breakdowns: BreakdownItem[];
  trend_series: TrendDataPoint[];
  dimension_trend_series: DimensionTrendPoint[];
  data_quality: DataQuality;
}
