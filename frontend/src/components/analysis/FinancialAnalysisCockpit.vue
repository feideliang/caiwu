<template>
  <a-layout class="analysis-cockpit">
    <a-layout-content class="analysis-main">
      <a-page-header :title="title" :sub-title="subtitle">
        <template #extra>
          <a-space wrap>
            <a-select
              v-model:value="period"
              :options="periodOptions"
              style="width: 140px"
              placeholder="期间"
              allow-clear
            />
            <a-select
              v-if="filterDimension"
              v-model:value="selectedEntity"
              :options="entityOptions"
              :placeholder="filterLabel"
              style="width: 180px"
              allow-clear
            />
            <a-select v-model:value="compare" :options="compareOptions" style="width: 120px" />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>

      <CoreMetricsPanel
        ref="panelRef"
        :period="period"
        :dimension="dimension"
        :entity="selectedEntity"
        :compare="compare"
        :period-dimension="periodDimension"
      />

      <a-card :title="chartTitle" size="small" class="section">
        <ChartWidget
          :title="chartTitle"
          :data="chartData"
          :chart-type="chartType"
          :loading="loading"
          :show-extra="true"
          @refresh="refresh"
        />
      </a-card>

      <a-card v-if="dimension !== 'company'" :title="`${dimensionLabel}维度明细`" size="small" class="section">
        <MetricBreakdownTable :breakdowns="breakdowns" :dimension-label="dimensionLabel" />
      </a-card>

      <a-card v-if="showConcentration" title="结构集中度与风险" size="small" class="section">
        <ConcentrationPanel :products="breakdowns" />
      </a-card>
    </a-layout-content>
    <a-layout-sider
      v-if="showAssistant"
      width="320"
      theme="light"
      :trigger="null"
      class="assistant-sider"
    >
      <FinancialAssistantPanel :context="assistantContext" />
    </a-layout-sider>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import CoreMetricsPanel from '@/components/dashboard/CoreMetricsPanel.vue';
import ChartWidget from '@/components/dashboard/ChartWidget.vue';
import MetricBreakdownTable from '@/components/dashboard/MetricBreakdownTable.vue';
import ConcentrationPanel from '@/components/dashboard/ConcentrationPanel.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import type { BreakdownItem, CoreMetricsResponse, TrendDataPoint } from '@/types/metrics';

const props = withDefaults(defineProps<{
  title: string;
  subtitle: string;
  dimension: string;
  dimensionLabel: string;
  activeSection: string;
  chartTitle: string;
  chartType?: 'line' | 'bar' | 'pie';
  filterDimension?: string;
  filterLabel?: string;
  showConcentration?: boolean;
}>(), {
  chartType: 'bar',
  filterDimension: undefined,
  filterLabel: '维度',
  showConcentration: false,
});

const isSmall = ref(window.innerWidth < 1024);

function updateSize() {
  isSmall.value = window.innerWidth < 1024;
}

onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));

const showAssistant = computed(() => !isSmall.value);

const period = ref<string | undefined>('2026-03');
const compare = ref('mom');
const selectedEntity = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const periodOptions = ref<Array<{ label: string; value: string }>>([]);
const entityOptions = ref<Array<{ label: string; value: string }>>([]);
const panelRef = ref<InstanceType<typeof CoreMetricsPanel> | null>(null);

const compareOptions = [
  { label: '环比', value: 'mom' },
  { label: '同比', value: 'yoy' },
  { label: '累计', value: 'cumulative' },
];

/** periodDimension is derived from compare mode:
 *  'cumulative' compare → 'cumulative' period dim
 *  'mom'/'yoy' compare  → 'monthly' period dim
 */
const periodDimension = computed(() =>
  compare.value === 'cumulative' ? 'cumulative' : 'monthly'
);

const breakdowns = computed<BreakdownItem[]>(() => metricsData.value?.breakdowns || []);

const chartData = computed<Record<string, unknown>[]>(() => {
  if (props.dimension === 'company') {
    return (metricsData.value?.trend_series || []).map((item: TrendDataPoint) => ({
      期间: item.period,
      收入: item.revenue || 0,
      毛利额: item.gross_profit || 0,
      毛利率: item.gross_margin || 0,
    }));
  }
  return breakdowns.value.map((item) => ({
    [props.dimensionLabel]: item.dimension_value,
    收入: item.revenue || 0,
    毛利额: item.gross_profit || 0,
    毛利率: item.gross_margin || 0,
  }));
});

const assistantContext = computed(() => ({
  period: period.value,
  department: props.activeSection === 'department' ? selectedEntity.value : undefined,
  product: props.activeSection === 'product' ? selectedEntity.value : undefined,
  period_compare_type: compare.value,
  period_dimension: periodDimension.value,
  active_section: props.activeSection,
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: props.dimension,
      entity: selectedEntity.value,
      compare: compare.value,
      period_dimension: periodDimension.value,
    });
    metricsData.value = resp.data as CoreMetricsResponse;
  } finally {
    loading.value = false;
  }
}

async function fetchOptions() {
  const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
  const periods = ((periodResp.data as any)?.options || []) as string[];
  periodOptions.value = periods.map((value) => ({ label: value, value })).reverse();
  if (!period.value && periods.length) period.value = periods[periods.length - 1];

  if (props.filterDimension) {
    const { data: entityResp } = await getFilterOptions({ dimension: props.filterDimension });
    const options = ((entityResp.data as any)?.options || []) as string[];
    entityOptions.value = options.map((value) => ({ label: value, value }));
  }
}

function refresh() {
  panelRef.value?.fetchData();
  fetchMetrics();
}

watch([period, compare, selectedEntity], refresh);

onMounted(async () => {
  await fetchOptions();
  await fetchMetrics();
});
</script>

<style scoped lang="less">
.analysis-cockpit {
  width: 100%;
  gap: 16px;
}

.analysis-main {
  min-width: 0;
  padding-right: 16px;
}

.assistant-sider {
  background: transparent;
}

.section {
  margin-top: 16px;
}

@media (max-width: 1023px) {
  .analysis-cockpit {
    flex-direction: column;
  }

  .analysis-main {
    padding-right: 0;
  }

  .assistant-sider {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
  }
}
</style>
