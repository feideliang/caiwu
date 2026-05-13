import { get } from './request'

export interface ContractItem { entity: string; total_ar: number; total_ap: number; net_exposure: number; period: string }
export interface OrderItem { period: string; revenue: number; cost: number; profit: number }
export interface ProjectItem { entity: string; total_revenue: number; total_cost: number; profit_margin: number; period_span: string }
export interface AnomalyItem { metric_name: string; period: string; value: number; expected_mean: number; sigma_distance: number; entity: string | null }
export interface LargeAmountItem { metric_name: string; metric_value: number; period: string; entity: string | null }

export function getContracts(params?: Record<string, unknown>) { return get('/transactions/contracts', { params }) }
export function getOrders(params?: Record<string, unknown>) { return get('/transactions/orders', { params }) }
export function getProjects(params?: Record<string, unknown>) { return get('/transactions/projects', { params }) }
export function getAnomalies(params?: Record<string, unknown>) { return get('/transactions/anomalies', { params }) }
export function getLargeAmounts(params?: Record<string, unknown>) { return get('/transactions/large-amounts', { params }) }
