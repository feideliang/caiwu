import { post, get } from './request';

export interface BffQueryParams {
  date_from?: string;
  date_to?: string;
  department?: string;
  product?: string;
  period_dimension?: string; // monthly / quarterly / cumulative / custom
  period_start?: string;
  period_end?: string;
  filters?: Record<string, unknown>;
  period_compare_type?: 'yoy' | 'mom' | 'cumulative';
}

export interface TrendItem {
  period: string;
  revenue: number;
  cost: number;
  gross_profit: number;
  gross_margin: number;
  revenue_yoy_growth?: number;
  revenue_mom_growth?: number;
  gross_profit_yoy_growth?: number;
  gross_profit_mom_growth?: number;
  gross_margin_yoy_growth?: number;
  gross_margin_mom_growth?: number;
  order_count?: number;
  order_count_yoy_growth?: number;
  order_count_mom_growth?: number;
}

export interface KpiData {
  revenue: number;
  cost: number;
  gross_profit: number;
  gross_margin: number;
  achievement_rate: number;
  revenue_mom_growth: number;
  profit_mom_growth: number;
  cost_yoy_growth: number;
  revenue_yoy_growth: number;
  profit_yoy_growth: number;
  gross_margin_yoy_change: number;
  revenue_cumulative: number;
  profit_cumulative: number;
  revenue_cumulative_growth: number;
  profit_cumulative_growth: number;
  revenue_consecutive_growth: number | null;
  gross_profit_consecutive_growth: number | null;
  trend_series: TrendItem[];
}

export interface ChartData {
  id: string;
  title: string;
  type: string;
  data: Record<string, unknown>[];
  options: Record<string, unknown>;
}

export interface BreakdownItem {
  dimension_value: string;
  revenue?: number;
  tax_excluded_cost?: number;
  gross_profit?: number;
  gross_margin?: number;
  gross_margin_contribution?: number;
  revenue_mom_growth?: number;
  gross_profit_mom_growth?: number;
}

export interface DashboardBff {
  kpis: KpiData;
  charts: ChartData[];
  updated_at: string;
  department_breakdown: BreakdownItem[];
  product_breakdown: BreakdownItem[];
}

export function queryDashboard(data: BffQueryParams) {
  return post<DashboardBff>('/dashboard/bff', data);
}

export function getInsights(params?: { status?: string; page?: number; page_size?: number; source?: string }) {
  return get('/insights', { params });
}

export function getInsight(id: number) {
  return get(`/insights/${id}`);
}

export function updateInsightStatus(id: number, status: string) {
  return post(`/insights/${id}/status`, { status });
}

export function getDataFreshness() {
  return get('/system/data-freshness');
}
