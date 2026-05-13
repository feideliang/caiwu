import { post } from './request';

export interface ChartRecommendParams {
  data_description: Record<string, unknown>;
  analysis_goal?: 'overview' | 'comparison' | 'trend' | 'distribution' | 'composition' | 'correlation';
  top_k?: number;
  device?: string;
}

export interface ChartRecommendItem {
  chart_type: string;
  priority: number;
  score: number;
  reason: string;
  suggested_config?: Record<string, unknown>;
}

export interface ChartRecommendResult {
  recommendations: ChartRecommendItem[];
  total_candidates: number;
}

export interface LayoutRecommendParams {
  chart_ids: number[];
  device_type?: 'web' | 'tablet' | 'mobile';
  dashboard_id?: number;
}

export interface LayoutRecommendResult {
  device_type: string;
  grid_cols: number;
  grid_rows: number;
  cells: Array<{ chart_id: number; x: number; y: number; w: number; h: number }>;
}

export function recommendChart(data_sample: Record<string, unknown>[], device?: string) {
  // Dynamically extract columns from actual data
  const columns = data_sample.length > 0 ? Object.keys(data_sample[0]) : [];
  // Auto-detect time series: check if any column looks like a period/date
  const timeKeys = ['period', 'date', 'month', 'year', 'time', 'created_at'];
  const is_time_series = columns.some(c => timeKeys.includes(c.toLowerCase()));

  return post<ChartRecommendResult>('/ai/recommend/chart', {
    data_description: {
      columns,
      row_count: data_sample.length,
      time_series: is_time_series
    },
    analysis_goal: 'overview',
    top_k: 5,
    device: device
  });
}

export function recommendLayout(data: LayoutRecommendParams) {
  return post<LayoutRecommendResult>('/ai/recommend/layout', data);
}

// ── AI Chat / Smart Q&A ────────────────────────────────────

export interface ChatContext {
  period?: string;
  department?: string;
  product?: string;
  period_compare_type?: string;
  active_section?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatReference {
  type: string;
  label: string;
  value?: string | number;
}

export interface ChatResponse {
  answer: string;
  suggestions: string[];
  references: ChatReference[];
}

export interface ChatRequest {
  question: string;
  context?: ChatContext;
  history?: ChatMessage[];
  model?: string;
}

export function chatWithAssistant(data: ChatRequest) {
  return post<ChatResponse>('/ai/chat', data);
}

export interface AIConfig {
  current_model: string;
  available_models: Array<{ value: string; label: string }>;
}

export function getAIConfig() {
  return import('@/api/request').then(({ get }) => get<AIConfig>('/ai/config'));
}

/**
 * Stream chat via SSE. Calls onChunk for each token, onDone when complete.
 */
export function streamChat(
  data: ChatRequest,
  onChunk: (text: string) => void,
  onDone: (suggestions: string[], references: ChatReference[]) => void,
  onError: (msg: string) => void,
) {
  const token = localStorage.getItem('access_token');
  const base = window.__APP_CONFIG__?.API_BASE_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const url = `${base}/ai/chat/stream`;

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  }).then(async (resp) => {
    if (!resp.ok) {
      onError(`HTTP ${resp.status}`);
      return;
    }
    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Parse SSE lines
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed === 'data:') continue;
        if (trimmed.startsWith('event:')) continue;

        const jsonStr = trimmed.replace(/^data:\s*/, '');
        try {
          const parsed = JSON.parse(jsonStr);
          if (parsed.done) {
            onDone(parsed.suggestions || [], parsed.references || []);
            return;
          }
          // Parse OpenAI SSE chunk
          if (parsed.choices && parsed.choices.length > 0) {
            const content = parsed.choices[0].delta?.content;
            if (content) onChunk(content);
          }
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }).catch((err) => {
    onError(err.message || 'Network error');
  });
}
