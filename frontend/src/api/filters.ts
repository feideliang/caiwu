import { post, get, del } from './request';
import type { FilterOptions, FilterView, FilterCondition } from '@/types/filter';

export interface FilterQueryParams {
  page?: number;
  page_size?: number;
}

export interface SaveFilterViewParams {
  name: string;
  conditions: FilterCondition[];
  logic: 'AND' | 'OR';
}

export function getFilterOptions(params?: Record<string, unknown>) {
  return get<FilterOptions>('/filter-options', { params });
}

export function getFilterViews(params?: FilterQueryParams) {
  return get<FilterView[]>('/filter-views', { params });
}

export function saveFilterView(data: SaveFilterViewParams) {
  return post<FilterView>('/filter-views', {
    name: data.name,
    dashboard_id: null,
    filters: data.conditions,
    is_public: false
  });
}

export function deleteFilterView(id: number) {
  return del(`/filter-views/${id}`);
}
