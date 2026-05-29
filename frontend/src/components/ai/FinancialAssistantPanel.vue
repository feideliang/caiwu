<template>
  <a-card size="small" class="assistant-panel">
    <template #title>
      <div style="display:flex;align-items:center;justify-content:space-between">
        <span>智能助手</span>
        <a-select v-model:value="selectedModel" size="small" style="width:140px" :options="modelOptions" @change="onModelChange" />
      </div>
    </template>
    <!-- Messages -->
    <div class="messages" ref="messagesRef">
      <template v-if="messages.length === 0">
        <a-empty description="输入问题开始智能问数" />
      </template>
      <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
        <div class="message-label">
          {{ msg.role === 'user' ? '你' : '助手' }}
        </div>
        <div
          class="message-content markdown-body"
          :class="{ 'is-assistant': msg.role === 'assistant' }"
          v-html="msg.role === 'assistant' ? renderMarkdown(msg.content) : renderPlainText(msg.content)"
        >
        </div>
        <!-- References -->
        <div v-if="msg.references && msg.references.length" class="message-references">
          <a-tag v-for="(ref, rIdx) in msg.references" :key="rIdx" size="small" color="blue">
            {{ ref.label }}: {{ ref.value }}
          </a-tag>
        </div>
      </div>
      <div v-if="loading" class="message assistant">
        <div class="message-label">助手</div>
        <div class="message-content">
          <a-spin size="small" /> 思考中...
        </div>
      </div>
    </div>

    <!-- Analysis Recommendations -->
    <div v-if="recommendations" class="recommendations">
      <div v-if="recommendations.summary" class="rec-summary">
        {{ recommendations.summary }}
      </div>

      <!-- Anomaly Alerts -->
      <div v-if="recommendations.anomalies.length" class="rec-anomalies">
        <div
          v-for="(alert, idx) in recommendations.anomalies"
          :key="idx"
          :class="['rec-alert', alert.severity, 'clickable']"
          @click="askQuestion(alert.message)"
        >
          <span class="alert-icon">{{ alert.severity === 'high' ? '🔴' : alert.severity === 'medium' ? '🟡' : '🔵' }}</span>
          <span class="alert-message">{{ alert.message }}</span>
          <span class="alert-action">点击分析</span>
        </div>
      </div>

      <!-- Key Metrics -->
      <div v-if="recommendations.metrics.length" class="rec-metrics">
        <div
          v-for="(m, idx) in recommendations.metrics"
          :key="idx"
          class="rec-metric clickable"
          :class="m.status"
          @click="askQuestion(`为什么${m.metric_name}${m.status === 'warning' ? '预警' : m.status === 'critical' ? '严重异常' : '正常'}`)"
        >
          <span class="metric-name">{{ m.metric_name }}</span>
          <span class="metric-value" v-if="m.current_value !== undefined">
            {{ formatMetricValue(m) }}
          </span>
          <span class="metric-rec">{{ m.recommendation }}</span>
        </div>
      </div>

      <!-- Drill-down path -->
      <div v-if="recommendations.drill_down_path && recommendations.drill_down_path.length" class="rec-drilldown">
        <span class="drilldown-label">建议下钻：</span>
        <a-tag
          v-for="(p, idx) in recommendations.drill_down_path"
          :key="idx"
          size="small"
          color="geekblue"
          class="drill-tag-clickable"
          @click="askQuestion(`请分析${p}的详细情况`)"
        >
          {{ p }}
        </a-tag>
      </div>
    </div>

    <!-- Suggestions -->
    <div v-if="suggestions.length > 0" class="suggestions">
      <a-button
        v-for="(s, idx) in suggestions"
        :key="idx"
        size="small"
        type="default"
        @click="askQuestion(s)"
      >
        {{ s }}
      </a-button>
    </div>

    <!-- Input -->
    <div class="input-area">
      <a-input
        v-model:value="inputText"
        placeholder="输入财务分析问题..."
        size="small"
        :disabled="loading"
        @press-enter="sendMessage"
      >
        <template #suffix>
          <a-button
            type="primary"
            size="small"
            :loading="loading"
            :disabled="!String(inputText || '').trim()"
            @click="sendMessage"
          >
            发送
          </a-button>
        </template>
      </a-input>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { streamChat, getAIConfig, type ChatContext, type ChatMessage, type ChatReference, type ChatResponse } from '@/api/ai';
import type { MetricRecommendation, AnomalyAlert } from '@/types/analysis';

interface DisplayMessage extends ChatMessage {
  references?: ChatReference[];
}

const props = defineProps<{
  context?: ChatContext;
  recommendations?: {
    metrics: MetricRecommendation[];
    anomalies: AnomalyAlert[];
    suggested_questions: string[];
    summary: string;
    drill_down_path?: string[];
  } | undefined;
}>();

const messages = ref<DisplayMessage[]>([]);
const inputText = ref('');
const loading = ref(false);
const messagesRef = ref<HTMLElement>();

const suggestions = ref<string[]>([]);
const selectedModel = ref('');
const modelOptions = ref<Array<{ label: string; value: string }>>([]);

// Fetch available models on mount
onMounted(async () => {
  // Clean up any stale overlays/modals
  document.querySelectorAll('vite-error-overlay, .ant-modal-mask, [data-vite-dev-overlay]').forEach(el => (el as HTMLElement).remove());

  try {
    const { data: resp } = await getAIConfig();
    const cfg = resp.data as { current_model: string; available_models: Array<{ value: string; label: string }> };
    modelOptions.value = cfg.available_models.map(m => ({ label: m.label, value: m.value }));
    selectedModel.value = cfg.current_model;
  } catch {
    modelOptions.value = [{ label: 'DeepSeek V4 Flash', value: 'deepseek-v4-flash' }];
    selectedModel.value = 'deepseek-v4-flash';
  }
  // Also fetch initial suggestions
  try {
    const { data: resp } = await chatWithAssistantNonStream({
      question: '__init__',
      context: props.context,
      history: [],
      model: selectedModel.value,
    });
    const chatData = resp.data as ChatResponse;
    suggestions.value = chatData.suggestions || [];
  } catch {
    suggestions.value = [];
  }
});

// Non-streaming chat for __init__ requests
import { chatWithAssistant } from '@/api/ai';
async function chatWithAssistantNonStream(data: any) {
  return chatWithAssistant(data);
}

async function askQuestion(question: string) {
  inputText.value = question;
  await sendMessage();
}

async function sendMessage() {
  const question = inputText.value.trim();
  if (!question || loading.value) return;

  // Add user message
  messages.value.push({ role: 'user', content: question });
  inputText.value = '';
  loading.value = true;

  // Add placeholder assistant message
  const assistantIdx = messages.value.length;
  messages.value.push({ role: 'assistant', content: '', references: [] });

  // Build history (last 6 messages)
  const history: ChatMessage[] = messages.value
    .slice(-6)
    .filter(m => m.content) // skip empty streaming messages
    .map((m) => ({ role: m.role, content: m.content }));

  try {
    await new Promise<void>((resolve) => {
      streamChat(
        {
          question,
          context: props.context,
          history,
          model: selectedModel.value,
        },
        // onChunk
        (text) => {
          messages.value[assistantIdx].content += text;
        },
        // onDone
        (sugs, refs) => {
          messages.value[assistantIdx].references = refs;
          suggestions.value = sugs || suggestions.value;
          resolve();
        },
        // onError
        (msg) => {
          messages.value[assistantIdx].content = `请求失败：${msg}`;
          resolve();
        },
      );
    });
  } catch (e: any) {
    messages.value[assistantIdx].content = `请求失败：${e?.message || '未知错误'}`;
  } finally {
    loading.value = false;
    await nextTick();
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }
}

function onModelChange() {
  // Model changed, will be used in next request
}

function formatMetricValue(m: MetricRecommendation): string {
  if (m.metric_key.includes('margin') || m.metric_key.includes('concentration') || m.metric_key.includes('ratio')) {
    return m.current_value != null ? `${m.current_value.toFixed(1)}%` : '--';
  }
  if (m.current_value != null && m.current_value > 10000) {
    return `${(m.current_value / 10000).toFixed(1)}亿`;
  }
  return m.current_value != null ? m.current_value.toFixed(0) : '--';
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function inlineMarkdown(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function renderPlainText(text: string): string {
  return escapeHtml(text).replace(/\n/g, '<br>');
}

function renderMarkdown(text: string): string {
  const lines = text.split(/\r?\n/);
  const html: string[] = [];
  let inList = false;
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${paragraph.map(line => inlineMarkdown(line)).join('<br>')}</p>`);
    paragraph = [];
  };

  const closeList = () => {
    if (!inList) return;
    html.push('</ul>');
    inList = false;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      closeList();
      continue;
    }
    if (/^(#{1,3})\s+/.test(line)) {
      flushParagraph();
      closeList();
      const level = Math.min(3, line.match(/^#+/)?.[0].length || 1);
      html.push(`<h${level}>${inlineMarkdown(line.replace(/^#{1,3}\s+/, ''))}</h${level}>`);
      continue;
    }
    if (/^[一二三四五六七八九十]+[、.．]/.test(line)) {
      flushParagraph();
      closeList();
      html.push(`<h3>${inlineMarkdown(line)}</h3>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      flushParagraph();
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(line.replace(/^[-*]\s+/, ''))}</li>`);
      continue;
    }
    paragraph.push(line);
  }

  flushParagraph();
  closeList();
  return html.join('');
}

// Auto-scroll when messages change
watch(messages, async () => {
  await nextTick();
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  }
}, { deep: true });
</script>

<style scoped lang="less">
.assistant-panel {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 140px);
  overflow: hidden;

  :deep(.ant-card-body) {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding-bottom: 8px;
  }
}

.messages {
  min-height: 120px;
  max-height: 350px;
  overflow-y: auto;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 4px;

  &.user {
    align-items: flex-end;

    .message-label {
      color: var(--color-primary, #1677ff);
    }

    .message-content {
      background: #e6f4ff;
      border-radius: 12px 12px 2px 12px;
    }
  }

  &.assistant {
    align-items: flex-start;

    .message-label {
      color: #52c41a;
    }

    .message-content {
      background: #f5f5f5;
      border-radius: 12px 12px 12px 2px;
    }
  }
}

.message-label {
  font-size: 11px;
  font-weight: 600;
  padding: 0 4px;
}

.message-content {
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.6;
  max-width: 90%;
  word-break: break-word;
}

.markdown-body {
  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 0 0 8px;
    font-weight: 700;
    line-height: 1.5;
  }

  :deep(h3) {
    font-size: 14px;
  }

  :deep(p) {
    margin: 0 0 8px;
  }

  :deep(ul) {
    margin: 0 0 8px 18px;
    padding: 0;
  }

  :deep(li) {
    margin-bottom: 4px;
  }

  :deep(strong) {
    color: #1677ff;
    font-weight: 700;
  }

  :deep(code) {
    padding: 1px 4px;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.04);
    font-family: Consolas, 'Courier New', monospace;
  }
}

.message-references {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 4px;
}

.suggestions {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0;
  border-top: 1px solid #f0f0f0;

  :deep(.ant-btn) {
    color: #333 !important;
    border-color: #d9d9d9;
  }
}

.input-area {
  position: relative;
  z-index: 3;
  margin-top: 8px;
}

.recommendations {
  position: relative;
  z-index: 1;
  padding: 8px 0;
}

.rec-summary {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  position: relative;
  z-index: 1;
}

.rec-anomalies {
  position: relative;
  z-index: 2;
  margin-bottom: 8px;
}

.rec-alert {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 4px;

  &.high {
    background: #fff2f0;
    border: 1px solid #ffccc7;
    color: #cf1322;
  }

  &.medium {
    background: #fffbe6;
    border: 1px solid #ffe58f;
    color: #d48806;
  }

  &.low {
    background: #e6f4ff;
    border: 1px solid #91caff;
    color: #0958d9;
  }

  &.clickable {
    cursor: pointer;
    transition: all 0.2s;
    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    }
  }
}

.alert-message {
  flex: 1;
}

.alert-action {
  font-size: 11px;
  opacity: 0.5;
  margin-left: 4px;
}

.rec-metrics {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rec-metric {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #f9f9f9;
  font-size: 12px;

  &.critical {
    background: #fff2f0;
    border: 1px solid #ffccc7;
  }

  &.warning {
    background: #fffbe6;
    border: 1px solid #ffe58f;
  }

  &.normal {
    background: #f6ffed;
    border: 1px solid #b7eb8f;
  }

  &.clickable {
    cursor: pointer;
    transition: all 0.2s;
    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    }
  }
}

.metric-name {
  font-weight: 600;
  color: #333;
  white-space: nowrap;
}

.metric-value {
  color: #1677ff;
  font-weight: 500;
  white-space: nowrap;
}

.metric-rec {
  color: #666;
  margin-left: auto;
  font-size: 11px;
}

.rec-drilldown {
  position: relative;
  z-index: 2;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.drilldown-label {
  font-size: 12px;
  color: #999;
}

.drill-tag-clickable {
  cursor: pointer;
  transition: all 0.2s;
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  }
}
</style>
