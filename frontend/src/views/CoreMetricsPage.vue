<template>
  <div class="core-metrics-page">
    <a-page-header title="核心指标" sub-title="收入 / 成本 / 毛利 / 集中度 / 增长">
      <template #extra>
        <a-space>
          <a-select v-model:value="period" :options="periodOptions" style="width: 140px" placeholder="周期" />
          <a-select v-model:value="dimension" :options="dimensionOptions" style="width: 140px" />
          <a-button type="primary" @click="refresh">刷新</a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="page-content" :class="{ 'with-assistant': showAssistant }">
      <div class="main-area">
        <CoreMetricsPanel ref="panelRef" :period="period" :dimension="dimension" />

        <a-card title="集中度排名" size="small" class="section">
          <ConcentrationPanel :breakdowns="breakdowns" :dimension="dimension" />
        </a-card>

        <a-card :title="`${dimensionLabel}维度明细`" size="small" class="section">
          <MetricBreakdownTable :breakdowns="breakdowns" :dimension-label="dimensionLabel" />
        </a-card>
      </div>
      <div v-if="showAssistant" class="assistant-area">
        <FinancialAssistantPanel :context="assistantContext" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import CoreMetricsPanel from '@/components/dashboard/CoreMetricsPanel.vue';
import ConcentrationPanel from '@/components/dashboard/ConcentrationPanel.vue';
import MetricBreakdownTable from '@/components/dashboard/MetricBreakdownTable.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import type { BreakdownItem } from '@/types/metrics';

const period = ref<string>('2026-03');
const dimension = ref<string>('customer');
const breakdowns = ref<BreakdownItem[]>([]);
const panelRef = ref<InstanceType<typeof CoreMetricsPanel> | null>(null);
const isSmall = ref(window.innerWidth < 1024);

const periodOptions = [
  { label: '2026-03', value: '2026-03' },
  { label: '2026-02', value: '2026-02' },
  { label: '2026-01', value: '2026-01' },
  { label: '2025-12', value: '2025-12' },
];
const dimensionOptions = [
  { label: '客户', value: 'customer' },
  { label: '产品线', value: 'product_line' },
  { label: '部门', value: 'department' },
  { label: '总览', value: 'company' },
];
const dimensionLabel = computed(() => dimensionOptions.find((d) => d.value === dimension.value)?.label || '维度');
const showAssistant = computed(() => !isSmall.value);
const assistantContext = computed(() => ({
  period: period.value,
  period_compare_type: 'mom' as string,
  active_section: 'metrics' as string,
}));

function updateSize() {
  isSmall.value = window.innerWidth < 1024;
}

async function fetchBreakdowns() {
  try {
    const { data } = await getCoreMetrics({ period: period.value, dimension: dimension.value });
    breakdowns.value = (data.data?.breakdowns || []) as BreakdownItem[];
  } catch {
    breakdowns.value = [];
  }
}

function refresh() {
  panelRef.value?.fetchData();
  fetchBreakdowns();
}

watch([period, dimension], fetchBreakdowns);

onMounted(() => {
  window.addEventListener('resize', updateSize);
  fetchBreakdowns();
});
</script>

<style scoped lang="less">
.core-metrics-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-content {
  display: flex;
  gap: 16px;

  &.with-assistant {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 16px;
  }

  .main-area {
    min-width: 0;
  }

  .assistant-area {
    min-width: 0;
  }
}
.section {
  margin-top: 12px;
}
</style>
