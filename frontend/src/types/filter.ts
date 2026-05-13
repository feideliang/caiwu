export interface FilterCondition {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'like' | 'between';
  value: unknown;
}

export type FilterLogic = 'AND' | 'OR';

export interface FilterView {
  id: number;
  name: string;
  conditions: FilterCondition[];
  logic: FilterLogic;
  created_by: number;
  created_at: string;
}

export interface FilterFieldConfig {
  field: string;
  label: string;
  type: 'select' | 'date_range' | 'number_range' | 'text';
  options?: Array<{ label: string; value: string | number }>;
  placeholder?: string;
}

export interface FilterOptions {
  fields: FilterFieldConfig[];
  recent_views: FilterView[];
}
