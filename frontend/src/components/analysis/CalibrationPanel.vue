<template>
  <a-card class="calibration-panel" size="small">
    <template #title>人工校准</template>
    <a-empty v-if="!pair" description="请选择需要校准的关联对" />
    <template v-else>
      <a-descriptions :column="isMobile ? 1 : 2" size="small" bordered>
        <a-descriptions-item label="变量 X">{{ pair.variable_x }}</a-descriptions-item>
        <a-descriptions-item label="变量 Y">{{ pair.variable_y }}</a-descriptions-item>
        <a-descriptions-item label="相关系数">
          <a-tag :color="correlationColor(pair.correlation_coefficient)">
            {{ (pair.correlation_coefficient ?? 0).toFixed(3) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="P 值">
          {{ pair.p_value != null ? (pair.p_value < 0.001 ? '< 0.001' : pair.p_value.toFixed(4)) : '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="样本量">{{ (pair as any).sample_size ?? '-' }}</a-descriptions-item>
        <a-descriptions-item label="当前状态">
          <a-tag v-if="pair.calibration_status" :color="calibrationStatusColor(pair.calibration_status)">
            {{ calibrationStatusLabel(pair.calibration_status) }}
          </a-tag>
          <a-tag v-else color="default">未校准</a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <!-- AI explanation -->
      <a-alert
        class="ai-explanation"
        message="AI 分析说明"
        :description="aiExplanation || '暂无分析'"
        type="info"
        show-icon
      />

      <!-- Disclaimer -->
      <a-alert
        class="disclaimer"
        message="重要提示"
        description="相关性不等于因果性。AI 提供的关联假设仅供参考，不代表因果关系。请结合实际业务场景进行判断。"
        type="warning"
        show-icon
      />

      <!-- Calibration actions -->
      <div class="calibration-actions">
        <a-space>
          <a-button type="primary" :loading="loading" @click="handleCalibrate('confirm')">
            <CheckOutlined /> 确认
          </a-button>
          <a-button :loading="loading" @click="handleCalibrate('doubt')">
            <QuestionOutlined /> 存疑
          </a-button>
          <a-button danger :loading="loading" @click="handleCalibrate('reject')">
            <CloseOutlined /> 驳回
          </a-button>
        </a-space>
        <a-input
          v-model:value="notes"
          placeholder="备注说明（可选）"
          style="margin-top: 12px"
        />
      </div>
    </template>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { calibrateCorrelation } from '@/api/correlations';
import type { CorrelationPair, CorrelationRecord, CalibrationStatus } from '@/types/correlation';
import { CheckOutlined, QuestionOutlined, CloseOutlined } from '@ant-design/icons-vue';

const props = defineProps<{
  pair: (CorrelationPair & { id?: number; calibration_status?: CalibrationStatus | null }) | CorrelationRecord | null;
  aiExplanation?: string;
}>();

const emit = defineEmits<{
  calibrated: [status: CalibrationStatus];
}>();

const loading = ref(false);
const notes = ref('');

const isMobile = computed(() => window.innerWidth < 768);

function correlationColor(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 0.7) return value > 0 ? 'red' : 'blue';
  if (abs >= 0.4) return 'orange';
  return 'default';
}

function calibrationStatusColor(status: CalibrationStatus): string {
  const colors: Record<CalibrationStatus, string> = { confirm: 'green', doubt: 'orange', reject: 'red' };
  return colors[status];
}

function calibrationStatusLabel(status: CalibrationStatus): string {
  const labels: Record<CalibrationStatus, string> = { confirm: '已确认', doubt: '存疑', reject: '已驳回' };
  return labels[status];
}

async function handleCalibrate(status: CalibrationStatus) {
  if (!props.pair) return;
  loading.value = true;
  try {
    if ((props.pair as CorrelationRecord).id) {
      await calibrateCorrelation((props.pair as CorrelationRecord).id, { action: status, notes: notes.value || undefined });
    }
    emit('calibrated', status);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="less">
.calibration-panel {
  border-radius: 8px;
}

.ai-explanation {
  margin: 16px 0;
}

.disclaimer {
  margin-bottom: 16px;
}

.calibration-actions {
  margin-top: 16px;
}
</style>
