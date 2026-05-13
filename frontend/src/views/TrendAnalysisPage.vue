<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="趋势分析" sub-title="收入、毛利、毛利率的时序趋势">
        <template #extra>
          <a-space wrap>
            <a-select v-model:value="period" :options="periodOptions" style="width: 140px" placeholder="期间" allow-clear />
            <a-select v-model:value="trendDimension" :options="dimensionOptions" style="width: 140px" placeholder="维度" />
            <a-select v-if="trendDimension !== 'company'" v-model:value="selectedEntity" :options="entityOptions" style="width: 180px" placeholder="实体" allow-clear />
            <a-select v-model:value="compare" :options="compareOptions" style="width: 120px" />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights
        :breakdowns="metricsData?.breakdowns || []"
        :summary="summary"
        dimension="company"
        :trend-series="metricsData?.trend_series || []"
        :max-count="5"
        class="section"
      />

      <!-- KPI Cards -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="收入" :value="toWan(summary?.revenue)" unit="万元" :trend="summary?.revenue_mom_growth" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利额" :value="toWan(summary?.gross_profit)" unit="万元" :trend="summary?.gross_profit_mom_growth" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="订单数" :value="summary?.order_count || 0" unit="笔" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" />
        </a-col>
      </a-row>

      <!-- Charts Grid 2x3 -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="收入趋势" :data="revenueTrendData" chart-type="area" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="毛利趋势" :data="profitTrendData" chart-type="line" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="收入结构趋势" :data="revenueStructureData" chart-type="stacked-area" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="毛利率趋势" :data="marginTrendData" chart-type="line" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="月度收入分布" :data="monthlyRevenueData" chart-type="bar" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="月度毛利率分布" :data="monthlyMarginData" chart-type="line" :loading="loading" />
        </a-col>
      </a-row>
    </div>
    <div v-if="showAssistant" class="analysis-assistant">
      <FinancialAssistantPanel :context="assistantContext" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import KpiCard from '@/components/dashboard/KpiCard.vue';
import ChartWidget from '@/components/dashboard/ChartWidget.vue';
import InlineInsights from '@/components/dashboard/InlineInsights.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import type { CoreMetricsResponse, TrendDataPoint } from '@/types/metrics';
import { toWan } from '@/utils/format';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

const period = ref<string | undefined>('2026-03');
const compare = ref('mom');
const trendDimension = ref('company');
const selectedEntity = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const periodOptions = ref<Array<{ label: string; value: string }>>([]);
const dimensionOptions = [
  { label: '公司整体', value: 'company' },
  { label: '部门', value: 'department' },
  { label: '产品线', value: 'product_line' },
];
const entityOptions = ref<Array<{ label: string; value: string }>>([]);

const compareOptions = [
  { label: '环比', value: 'mom' },
  { label: '同比', value: 'yoy' },
  { label: '累计', value: 'cumulative' },
];

const summary = computed(() => metricsData.value?.summary);

// Chart 1: Revenue trend (area)
const revenueTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    收入: t.revenue || 0,
  }))
);

// Chart 2: Profit trend (line)
const profitTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    毛利额: t.gross_profit || 0,
  }))
);

// Chart 3: Revenue structure trend (stacked area by selected dimension)
const revenueStructureData = computed(() => {
  if (trendDimension.value === 'company') {
    return (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
      期间: t.period,
      收入: t.revenue || 0,
    }));
  }
  const dimTrend = metricsData.value?.dimension_trend_series || [];
  const periodMap: Record<string, Record<string, number>> = {};
  for (const pt of dimTrend) {
    if (!periodMap[pt.period]) periodMap[pt.period] = {};
    periodMap[pt.period][pt.dimension_value] = (pt.revenue || 0);
  }
  const periods = Object.keys(periodMap).sort();
  const dims = new Set<string>();
  for (const p of periods) for (const d of Object.keys(periodMap[p])) dims.add(d);
  return periods.map((p) => {
    const row: Record<string, unknown> = { 期间: p };
    for (const d of dims) row[d] = periodMap[p][d] || 0;
    return row;
  });
});

// Chart 4: Margin trend (line)
const marginTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    毛利率: t.gross_margin || 0,
  }))
);

// Chart 5: Monthly revenue distribution (bar)
const monthlyRevenueData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    月份: t.period,
    收入: t.revenue || 0,
  }))
);

// Chart 6: Monthly margin distribution (line)
const monthlyMarginData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    月份: t.period,
    毛利率: t.gross_margin || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  dimension: trendDimension.value,
  entity: selectedEntity.value,
  period_compare_type: compare.value,
  active_section: 'trend',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: trendDimension.value,
      entity: trendDimension.value !== 'company' ? selectedEntity.value : undefined,
      compare: compare.value,
    });
    metricsData.value = resp.data as CoreMetricsResponse;
  } finally {
    loading.value = false;
  }
}

async function fetchOptions() {
  const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
  const periods = ((periodResp.data as any)?.options || []) as string[];
  periodOptions.value = periods.map((v) => ({ label: v, value: v })).reverse();
  if (!period.value && periods.length) period.value = periods[periods.length - 1];
}

async function loadEntityOptions() {
  if (trendDimension.value === 'company') {
    entityOptions.value = [];
    selectedEntity.value = undefined;
    return;
  }
  const { data: resp } = await getFilterOptions({ dimension: trendDimension.value });
  const opts = ((resp.data as any)?.options || []) as string[];
  entityOptions.value = opts.map((v) => ({ label: v, value: v }));
  selectedEntity.value = undefined;
}

function refresh() { fetchMetrics(); }
watch([period, compare, trendDimension], async () => {
  await loadEntityOptions();
  fetchMetrics();
});
watch(selectedEntity, refresh);

onMounted(async () => { await fetchOptions(); await fetchMetrics(); });
</script>

<style scoped lang="less">
.analysis-page {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: auto 1fr;

  .analysis-header {
    grid-column: 1 / -1;
    padding: 0 16px;
  }

  .analysis-content {
    min-width: 0;
    padding: 0 16px;
  }

  .analysis-assistant {
    min-width: 0;
    margin-top: 16px;
  }
}

.kpi-row { margin-bottom: 16px; }
.section { margin-top: 16px; }

@media (max-width: 1023px) {
  .analysis-page {
    grid-template-columns: 1fr;
    .analysis-assistant { width: 100%; }
  }
}
</style>
