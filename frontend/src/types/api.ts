/** Generic API response envelope */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  trace_id: string;
}

/** Paginated list wrapper */
export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** User roles */
export type UserRole = 'admin' | 'analyst' | 'viewer';

/** Authenticated user */
export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  department?: string;
  created_at?: string;
  last_login?: string;
}

/** Login request */
export interface LoginRequest {
  username: string;
  password: string;
}

/** Login response data */
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/** Filter config for dynamic filter controls */
export interface FilterFieldConfig {
  field: string;
  label: string;
  type: 'select' | 'date_range' | 'number_range' | 'text';
  options?: Array<{ label: string; value: string | number }>;
  placeholder?: string;
}

/** Filter condition */
export interface FilterCondition {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'like' | 'between';
  value: unknown;
}

/** Filter view (saved) */
export interface FilterView {
  id: number;
  name: string;
  conditions: FilterCondition[];
  logic: 'AND' | 'OR';
  created_by: number;
  created_at: string;
}

/** Filter options response */
export interface FilterOptions {
  fields: FilterFieldConfig[];
  recent_views: FilterView[];
}
