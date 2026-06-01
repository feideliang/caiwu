export interface CoreMetricsSummary {
  revenue?: number;
  tax_excluded_cost?: number;
  gross_profit?: number;
  gross_margin?: number;
  gross_margin_yoy_change?: number;
  gross_margin_mom_change?: number;
  gross_margin_contribution?: number;
  customer_concentration_top3?: number;
  customer_concentration_top3_change?: number;
  product_concentration_top3?: number;
  customer_concentration_top10?: number;
  product_concentration_top10?: number;
  high_margin_order_ratio?: number;
  revenue_yoy_growth?: number;
  gross_profit_yoy_growth?: number;
  top_customer_share?: number;
  top_product_margin_share?: number;
  revenue_consecutive_growth?: number;
  gross_profit_consecutive_growth?: number;
  gross_margin_volatility?: number;
  gross_margin_volatility_change?: number;
  margin_change_analysis?: MarginChangeItem[];
  margin_change_summary?: MarginChangeSummary;
  // Analysis page extensions
  revenue_mom_growth?: number;
  gross_profit_mom_growth?: number;
  order_count?: number;
  achievement_rate?: number;
  loss_ratio?: number;
  core_market_line?: string;
  highest_value_market_line?: string;
  // Market line details
  core_market_line_revenue?: number;
  highest_value_market_profit?: number;
  // Direct sign customer metrics
  direct_sign_revenue?: number;
  direct_sign_revenue_pct?: number;
  direct_sign_profit?: number;
  direct_sign_margin?: number;
  // Negative margin metrics
  negative_margin_order_ratio?: number;
  negative_margin_order_amount?: number;
  negative_margin_order_yoy_change?: number;
  negative_margin_order_mom_change?: number;
  negative_margin_product_ratio?: number;
  negative_margin_product_amount?: number;
  negative_margin_product_yoy_change?: number;
  negative_margin_product_mom_change?: number;
}

export interface MarginChangeSummary {
  continuing_structure_impact?: number;
  continuing_margin_impact?: number;
  new_impact?: number;
  exit_impact?: number;
  continuing_structure_impact_mom?: number;
  continuing_margin_impact_mom?: number;
  new_impact_mom?: number;
  exit_impact_mom?: number;
}

export interface MarginChangeItem {
  dimension_value: string;
  category: 'continuing' | 'new' | 'exit' | string;
  current_revenue: number;
  current_share: number;
  current_margin: number;
  base_revenue: number;
  base_share: number;
  base_margin: number;
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
  revenue_contribution?: number;
  gross_margin_contribution?: number;
  order_count?: number;
  avg_order_value?: number;
  neg_margin_order_count?: number;
  neg_margin_amount?: number;
  revenue_yoy_growth?: number;
  calculable?: boolean;
  missing_fields?: string[];
}

export interface TrendDataPoint {
  period: string;
  revenue?: number;
  gross_profit?: number;
  gross_margin?: number;
  order_count?: number;
  revenue_mom_growth?: number;
  revenue_yoy_growth?: number;
  gross_profit_mom_growth?: number;
  gross_profit_yoy_growth?: number;
  gross_margin_mom_growth?: number;
  gross_margin_yoy_growth?: number;
  order_count_mom_growth?: number;
  order_count_yoy_growth?: number;
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
  product_line_breakdown: BreakdownItem[];
  customer_breakdown: BreakdownItem[];
  contract_type_breakdown: BreakdownItem[];
  trend_series: TrendDataPoint[];
  dimension_trend_series: DimensionTrendPoint[];
  data_quality: DataQuality;
}
