<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="趋势分析" sub-title="收入、毛利、毛利率的时序趋势">
        <template #extra>
          <a-space wrap>
            <!-- Period dimension selector -->
            <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
              <a-select-option value="monthly">月度</a-select-option>
              <a-select-option value="weekly">季度</a-select-option>
              <a-select-option value="yearly">年累计</a-select-option>
            </a-select>
            <!-- Period selector with dynamic options based on dimension -->
            <a-select v-model:value="selectedPeriod" :options="periodSelectOptions" style="width: 160px" placeholder="筛选周期" allow-clear />
            <!-- Dimension selector -->
            <a-select v-model:value="trendDimension" :options="dimensionOptions" style="width: 140px" placeholder="维度" />
            <!-- Entity selector (hidden for company) -->
            <a-select v-if="trendDimension !== 'company'" v-model:value="selectedEntity" :options="entityOptions" style="width: 180px" placeholder="实体" allow-clear />
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

      <!-- Charts Grid -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="收入趋势" :data="revenueTrendData" chart-type="area" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="毛利趋势" :data="profitTrendData" chart-type="line" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="毛利率趋势" :data="marginTrendData" chart-type="line" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="月度收入分布" :data="monthlyRevenueData" chart-type="bar" :loading="loading" />
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

// Filter state
const periodDimension = ref<string>('monthly');
const selectedPeriod = ref<string | undefined>('2026-03');
const trendDimension = ref('company');
const selectedEntity = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const allPeriods = ref<string[]>([]);

const dimensionOptions = [
  { label: '公司整体', value: 'company' },
  { label: '部门', value: 'department' },
  { label: '产品线', value: 'product_line' },
];
const entityOptions = ref<Array<{ label: string; value: string }>>([]);

// Derived period: monthly→"2026-03", weekly→last week in selected period, yearly→"2026"
const period = computed(() => {
  if (periodDimension.value === 'monthly') {
    return selectedPeriod.value;
  }
  if (periodDimension.value === 'yearly') {
    return selectedPeriod.value ? selectedPeriod.value.slice(0, 4) : undefined;
  }
  if (periodDimension.value === 'weekly') {
    // Week string like "2026-W12" → resolve to the month containing that week
    if (selectedPeriod.value && selectedPeriod.value.includes('-W')) {
      const [y, wStr] = selectedPeriod.value.split('-W');
      const w = parseInt(wStr);
      const month = Math.min(12, Math.ceil(w / 4));
      return `${y}-${String(month).padStart(2, '0')}`;
    }
    return undefined;
  }
  return undefined;
});

// Dynamic period select options based on dimension
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  if (periodDimension.value === 'weekly') {
    const weeks = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const [y, m] = p.split('-');
        const weekNum = Math.ceil(parseInt(m) * 4.33 / 1);
        weeks.add(`${y}W${weekNum}`);
      }
    }
    return [...weeks].sort().reverse().map((v) => {
      const match = v.match(/^(\d{4})W(\d+)$/);
      if (match) {
        return { label: `${match[1]}年第${match[2]}周`, value: `${match[1]}-${String(Math.min(12, Math.ceil(parseInt(match[2]) / 4.33))).padStart(2, '0')}` };
      }
      return { label: v, value: v };
    });
  }
  if (periodDimension.value === 'yearly') {
    const years = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const y = p.split('-')[0];
        years.add(y);
      }
    }
    return [...years].sort().reverse().map((y) => ({ label: `${y}年`, value: `${y}` }));
  }
  // monthly
  const months = new Set<string>();
  for (const p of allPeriods.value) {
    if (p.includes('-')) {
      const [y, m] = p.split('-');
      months.add(`${y}-${m}`);
    }
  }
  return [...months].sort().reverse().map((v) => {
    const [y, m] = v.split('-');
    return { label: `${y}年${parseInt(m)}月`, value: `${y}-${m}` };
  });
});

// When period dimension changes, reset selectedPeriod to the first option of the new dimension
watch(periodDimension, () => {
  const opts = periodSelectOptions.value;
  if (opts.length) {
    selectedPeriod.value = opts[0].value;
  }
});

const summary = computed(() => metricsData.value?.summary);

// Chart 1: Revenue trend (area)
const revenueTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    收入: toWan(t.revenue),
  }))
);

// Chart 2: Profit trend (line)
const profitTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    毛利额: t.gross_profit || 0,
  }))
);

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

const assistantContext = computed(() => ({
  period: period.value,
  dimension: trendDimension.value,
  entity: selectedEntity.value,
  period_compare_type: 'yoy',
  active_section: 'trend',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: trendDimension.value,
      entity: trendDimension.value !== 'company' ? selectedEntity.value : undefined,
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
  allPeriods.value = periods;
  if (!selectedPeriod.value && periods.length) {
    selectedPeriod.value = periods[periods.length - 1];
  }
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

watch([periodDimension, selectedPeriod, trendDimension], async () => {
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
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--color-bg-layout);
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
