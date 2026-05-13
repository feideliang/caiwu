<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="产品分析" sub-title="产品线收入、毛利贡献与结构风险">
        <template #extra>
          <a-space wrap>
            <a-select v-model:value="period" :options="periodOptions" style="width: 140px" placeholder="期间" allow-clear />
            <a-select v-model:value="selectedProduct" :options="productOptions" style="width: 180px" placeholder="产品线" allow-clear />
            <a-select v-model:value="compare" :options="compareOptions" style="width: 120px" />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights :breakdowns="breakdowns" :summary="summary" dimension="product_line" :max-count="5" class="section" />

      <!-- KPI Cards -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="收入贡献" :value="toWan(summary?.revenue)" unit="万元" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率趋势" :value="summary?.gross_profit_mom_growth || 0" unit="%" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="亏损产品占比" :value="lossRatio" unit="%" />
        </a-col>
      </a-row>

      <!-- Charts -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品收入排行" :data="productRevenueRanking" chart-type="bar" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品毛利率分布" :data="productMarginDist" chart-type="pie" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品收入-毛利气泡图" :data="productBubbleData" chart-type="scatter" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品毛利率趋势" :data="productMarginTrend" chart-type="line" :loading="loading" />
        </a-col>
      </a-row>

      <!-- Detail Table -->
      <a-card title="产品线明细" size="small" class="section">
        <MetricBreakdownTable :breakdowns="breakdowns" dimension-label="产品线" />
      </a-card>
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
import MetricBreakdownTable from '@/components/dashboard/MetricBreakdownTable.vue';
import InlineInsights from '@/components/dashboard/InlineInsights.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import type { CoreMetricsResponse, BreakdownItem, TrendDataPoint } from '@/types/metrics';
import { toWan } from '@/utils/format';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

const period = ref<string | undefined>('2026-03');
const compare = ref('mom');
const selectedProduct = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const periodOptions = ref<Array<{ label: string; value: string }>>([]);
const productOptions = ref<Array<{ label: string; value: string }>>([]);

const compareOptions = [
  { label: '环比', value: 'mom' },
  { label: '同比', value: 'yoy' },
  { label: '累计', value: 'cumulative' },
];

const summary = computed(() => metricsData.value?.summary);
const breakdowns = computed<BreakdownItem[]>(() => metricsData.value?.breakdowns || []);

// Loss ratio from summary or computed from breakdowns
const lossRatio = computed(() => {
  if (summary.value?.loss_ratio !== undefined && summary.value.loss_ratio !== null) {
    return summary.value.loss_ratio;
  }
  const items = breakdowns.value;
  if (!items.length) return 0;
  const lossCount = items.filter((b) => (b.gross_profit || 0) < 0).length;
  return Math.round((lossCount / items.length) * 100);
});

// Chart 1: Product revenue ranking (bar)
const productRevenueRanking = computed(() =>
  [...breakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 8)
    .map((b) => ({ 产品线: b.dimension_value, 收入: b.revenue || 0 }))
);

// Chart 2: Product gross margin distribution (pie)
const productMarginDist = computed(() =>
  breakdowns.value.map((b) => ({
    产品线: b.dimension_value,
    毛利额: b.gross_profit || 0,
  }))
);

// Chart 3: Product revenue-gross profit bubble (scatter)
const productBubbleData = computed(() =>
  breakdowns.value.map((b) => ({
    产品线: b.dimension_value,
    收入: b.revenue || 0,
    毛利额: b.gross_profit || 0,
    毛利率: b.gross_margin || 0,
  }))
);

// Chart 4: Product margin trend (line from trend_series)
const productMarginTrend = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    毛利率: t.gross_margin || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  product: selectedProduct.value,
  period_compare_type: compare.value,
  active_section: 'product',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: 'product_line',
      entity: selectedProduct.value,
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

async function loadProductOptions() {
  const { data: prodResp } = await getFilterOptions({ dimension: 'product_line' });
  const prods = ((prodResp.data as any)?.options || []) as string[];
  if (prods.length) {
    productOptions.value = prods.map((v) => ({ label: v, value: v }));
  } else {
    // Fallback: derive from metrics breakdowns
    const prodValues = new Set(breakdowns.value.map((b) => b.dimension_value));
    productOptions.value = [...prodValues].map((v) => ({ label: v, value: v }));
  }
}

function refresh() { fetchMetrics(); }
watch([period, compare, selectedProduct], refresh);

onMounted(async () => { await fetchOptions(); await fetchMetrics(); await loadProductOptions(); });
</script>

<style scoped lang="less">
.analysis-page {
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
