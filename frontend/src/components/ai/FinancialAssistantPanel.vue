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
        <div class="message-content">
          {{ msg.content }}
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

    <!-- Suggestions -->
    <div v-if="suggestions.length > 0 && messages.length === 0" class="suggestions">
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
            :disabled="!inputText.trim()"
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

interface DisplayMessage extends ChatMessage {
  references?: ChatReference[];
}

const props = defineProps<{
  context?: ChatContext;
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
}

.messages {
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.message-references {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 4px;
}

.suggestions {
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
  margin-top: 8px;
}
</style>
