export type DrillLevel = 1 | 2 | 3 | 4;

export interface DrillBreadcrumb {
  label: string;
  level: DrillLevel;
  params: {
    department_id?: number;
    department_name?: string;
    product_id?: number;
    product_name?: string;
    record_id?: number;
    record_title?: string;
    metric?: string;
    rule_code?: string;
    dimension?: string;
    dimension_value?: string;
  };
}

export interface DrillRecord {
  id: number;
  level: DrillLevel;
  title: string;
  fields: Record<string, unknown>;
  children_count: number;
}

export interface DrillDepartment {
  id: number;
  name: string;
  revenue: number;
  cost: number;
  gross_profit: number;
  head_count: number;
}

export interface DrillProduct {
  id: number;
  name: string;
  category: string;
  revenue: number;
  cost: number;
  margin: number;
  sales_count: number;
}

export interface DrillSummary {
  report_id: string;
  title: string;
  level: DrillLevel;
  breadcrumbs: DrillBreadcrumb[];
  metrics: Record<string, number>;
  departments?: DrillDepartment[];
  products?: DrillProduct[];
  has_children: boolean;
}

export interface DrillDownState {
  report_id: string;
  current_level: DrillLevel;
  breadcrumbs: DrillBreadcrumb[];
  params: DrillBreadcrumb['params'];
}
