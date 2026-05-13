import { get, post, put, del } from './request';

export interface Rule {
  id: number;
  category: string;
  rule_text: string;
  source_section: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export function listRules(category?: string) {
  return get<Rule[]>('/rules/', category ? { params: { category } } : undefined);
}

export function createRule(data: Omit<Rule, 'id' | 'created_at' | 'updated_at'>) {
  return post<Rule>('/rules/', data);
}

export function updateRule(id: number, data: Partial<Omit<Rule, 'id' | 'created_at' | 'updated_at'>>) {
  return put<Rule>(`/rules/${id}`, data);
}

export function deleteRule(id: number) {
  return del<Rule>(`/rules/${id}`);
}

export function importRules(rules: Array<Omit<Rule, 'id' | 'created_at' | 'updated_at'>>) {
  return post('/rules/import', rules);
}
