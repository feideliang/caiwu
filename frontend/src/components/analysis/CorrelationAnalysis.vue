<template>
  <a-row :gutter="[16, 16]">
    <a-col :xs="24" :lg="16">
      <a-card title="关联分析矩阵" size="small">
        <template #extra>
          <a-space>
            <a-select v-model:value="metricA" placeholder="指标 A" style="width: 140px" :options="metricOptions" />
            <a-select v-model:value="metricB" placeholder="指标 B" style="width: 140px" :options="metricOptions" />
            <a-button size="small" type="primary" :loading="loading" :disabled="!metricA || !metricB" @click="handleAnalyze">
              <ThunderboltOutlined /> 开始分析
            </a-button>
          </a-space>
        </template>
        <CorrelationMatrix
          v-if="variables.length > 0"
          :variables="variables"
          :matrix="matrix"
          :loading="loading"
          @cell-click="onCellClick"
        />
        <a-empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" description="选择两个指标后点击「开始分析」">
          <a-button type="primary" :loading="loading" :disabled="!metricA || !metricB" @click="handleAnalyze">开始分析</a-button>
        </a-empty>
      </a-card>
    </a-col>
    <a-col :xs="24" :lg="8">
      <CalibrationPanel
        :pair="selectedPair"
        :ai-explanation="aiExplanation"
        @calibrated="onCalibrated"
      />
    </a-col>
  </a-row>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Empty } from 'ant-design-vue';
import { useCorrelationStore } from '@/store/correlation';
import type { CalibrationStatus, CorrelationRecord } from '@/types/correlation';
import CorrelationMatrix from './CorrelationMatrix.vue';
import CalibrationPanel from './CalibrationPanel.vue';
import { ThunderboltOutlined } from '@ant-design/icons-vue';
import { getFilterOptions } from '@/api/filters';

const correlationStore = useCorrelationStore();
const loading = computed(() => correlationStore.loading);
const variables = ref<string[]>([]);
const matrix = ref<number[][]>([]);
const selectedPair = ref<CorrelationRecord | null>(null);
const aiExplanation = ref('');

const metricA = ref<string>('revenue');
const metricB = ref<string>('gross_profit');
const metricOptions = ref<Array<{ label: string; value: string }>>([]);

async function loadMetricOptions() {
  const { data: resp } = await getFilterOptions({ dimension: 'metric_name' });
  const metrics = ((resp.data as any)?.options || []) as string[];
  metricOptions.value = metrics.map((m) => ({ label: m, value: m }));
  if (!metricA.value && metrics.includes('revenue')) metricA.value = 'revenue';
  if (!metricB.value && metrics.includes('gross_profit')) metricB.value = 'gross_profit';
}

async function handleAnalyze() {
  if (!metricA.value || !metricB.value) return;
  const result = await correlationStore.analyze(metricA.value, metricB.value);
  await correlationStore.fetchRecords();
  buildMatrix(correlationStore.records);
  selectedPair.value = correlationStore.records[0] || null;
  aiExplanation.value = result?.ai_explanation || selectedPair.value?.ai_explanation || '';
}

function buildMatrix(pairs: CorrelationRecord[]) {
  const varSet = new Set<string>();
  pairs.forEach((p) => {
    varSet.add(p.variable_x);
    varSet.add(p.variable_y);
  });
  const vars = Array.from(varSet);
  variables.value = vars;

  const n = vars.length;
  const m: number[][] = Array.from({ length: n }, () => Array(n).fill(0));

  for (const pair of pairs) {
    const xi = vars.indexOf(pair.variable_x);
    const yi = vars.indexOf(pair.variable_y);
    if (xi >= 0 && yi >= 0) {
      m[xi][yi] = pair.correlation_coefficient;
      m[yi][xi] = pair.correlation_coefficient;
    }
  }
  // Set diagonal to 1
  for (let i = 0; i < n; i++) m[i][i] = 1;

  matrix.value = m;
}

function onCellClick(data: { x: string; y: string; value: number }) {
  const pair = correlationStore.records.find(
    (p) =>
      (p.variable_x === data.y && p.variable_y === data.x) ||
      (p.variable_x === data.x && p.variable_y === data.y),
  );
  if (pair) selectedPair.value = pair;
  aiExplanation.value = pair?.ai_explanation || '';
}

function onCalibrated(status: CalibrationStatus) {
  if (selectedPair.value) {
    (selectedPair.value as Record<string, unknown>).calibration_status = status;
  }
}

onMounted(async () => { await loadMetricOptions(); if (metricA.value && metricB.value) handleAnalyze(); });
</script>

<style scoped lang="less">
.correlation-analysis .ant-card { margin-bottom: 16px; }
</style>
