<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="趋势分析" sub-title="收入、毛利、毛利率的时序趋势">
        <template #extra>
          <a-space wrap>
            <!-- Period dimension selector -->
            <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
              <a-select-option value="monthly">月度</a-select-option>
              <a-select-option value="quarterly">季度</a-select-option>
              <a-select-option value="cumulative">年累计</a-select-option>
            </a-select>
            <!-- Period selector with dynamic options based on dimension -->
            <a-select v-model:value="selectedPeriod" :options="periodSelectOptions" style="width: 160px" placeholder="筛选周期" allow-clear />
            <!-- Dimension selector -->
            <a-select v-model:value="trendDimension" :options="dimensionOptions" style="width: 140px" placeholder="维度" />
            <!-- Entity selector (hidden for company) -->
            <a-select v-if="trendDimension !== 'company' && !(trendDimension === 'department' && authStore.isDeptRestricted)" v-model:value="selectedEntity" :options="entityOptions" style="width: 180px" placeholder="实体" allow-clear />
            <a-tag v-if="trendDimension === 'department' && authStore.isDeptRestricted" color="blue">{{ authStore.department }}</a-tag>
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
          <KpiCard title="收入" :value="toWan(summary?.revenue)" unit="万元" :precision="0" :trend="compareBase === 'mom' ? summary?.revenue_mom_change : summary?.revenue_yoy_change" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利额" :value="toWan(summary?.gross_profit)" unit="万元" :precision="0" :trend="compareBase === 'mom' ? summary?.gross_profit_mom_change : summary?.gross_profit_yoy_change" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="订单数" :value="summary?.order_count || 0" unit="笔" :trend="orderCountTrend" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" :trend="grossMarginTrend" />
        </a-col>
      </a-row>

      <!-- Charts Grid -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget :title="revenueTrendTitle" :data="isMultiDim ? multiRevenueData : revenueTrendData" chart-type="area" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget :title="profitTrendTitle" :data="isMultiDim ? multiProfitData : profitTrendData" chart-type="line" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="毛利率趋势" :data="isMultiDim ? multiMarginData : marginTrendData" :chart-type="isMultiDim ? 'area' : 'line'" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="月度收入分布" :data="isMultiDim ? multiRevenueData : monthlyRevenueData" :chart-type="isMultiDim ? 'bar' : 'bar'" :loading="loading" />
        </a-col>
      </a-row>
    </div>
    <div v-if="showAssistant" class="analysis-assistant">
      <FinancialAssistantPanel :context="assistantContext" :recommendations="recommendations" />
    </div>

    <!-- Calculation Rules -->
    <a-collapse :bordered="false" class="calc-rules-section" style="margin-top: 16px">
      <a-collapse-panel header="计算规则说明" key="rules">
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item label="同比 (YoY)">
            (当期值 - 去年同期值) / 去年同期值 x 100%
          </a-descriptions-item>
          <a-descriptions-item label="环比 (MoM)">
            (当期值 - 上期值) / 上期值 x 100%
          </a-descriptions-item>
          <a-descriptions-item label="毛利率同比变动">
            当期毛利率 - 去年同期毛利率（单位：百分点，非百分比增长率）
          </a-descriptions-item>
          <a-descriptions-item label="筛选影响">
            选择筛选条件后，同比/环比的分母（基期数据）也按相同条件过滤，确保对比口径一致。
          </a-descriptions-item>
        </a-descriptions>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store/auth';
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import KpiCard from '@/components/dashboard/KpiCard.vue';
import ChartWidget from '@/components/dashboard/ChartWidget.vue';
import InlineInsights from '@/components/dashboard/InlineInsights.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import { getAnalysisRecommendations } from '@/api/ai';
import type { AnalysisRecommendations } from '@/types/analysis';
import type { CoreMetricsResponse, TrendDataPoint } from '@/types/metrics';
import { toWan } from '@/utils/format';
import { buildPeriodOptions, getDefaultPeriod, normalizePeriodDimension } from '@/utils/period';

const authStore = useAuthStore();
const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('monthly');
const selectedPeriod = ref<string | undefined>();
const compareBase = ref<string>('yoy');
const dataCaliber = ref<string>('absolute');
const trendDimension = ref('company');
const selectedEntity = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const perEntityTrends = ref<Map<string, TrendDataPoint[]>>(new Map());
const allPeriods = ref<string[]>([]);

// Whether to show multi-line trend (dimension selected, no specific entity)
const isMultiDim = computed(() => trendDimension.value !== 'company' && !selectedEntity.value);
const multiDimLabel = computed(() => trendDimension.value === 'department' ? '部门' : '产品线');

const dimensionOptions = [
  { label: '公司整体', value: 'company' },
  { label: '部门', value: 'department' },
  { label: '产品线', value: 'product_bgbu' },
];
const entityOptions = ref<Array<{ label: string; value: string }>>([]);

// Derived period: monthly→"2026-03", quarterly/cumulative/custom resolve through shared period helpers
const period = computed(() => {
  return selectedPeriod.value;
});

// Dynamic period select options based on dimension
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  return buildPeriodOptions(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

// When period dimension changes, reset selectedPeriod to the first option of the new dimension
watch(periodDimension, () => {
  selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

const summary = computed(() => metricsData.value?.summary);

const revenueTrendTitle = computed(() => {
  if (isMultiDim.value) return `各${multiDimLabel.value}收入趋势`;
  if (dataCaliber.value === 'yoy') return '收入趋势（同比%）';
  if (dataCaliber.value === 'mom') return '收入趋势（环比%）';
  return '收入趋势';
});

const profitTrendTitle = computed(() => {
  if (isMultiDim.value) return `各${multiDimLabel.value}毛利趋势`;
  if (dataCaliber.value === 'yoy') return '毛利趋势（同比%）';
  if (dataCaliber.value === 'mom') return '毛利趋势（环比%）';
  return '毛利趋势';
});

// Chart 1: Revenue trend (area)
const revenueTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    收入: dataCaliber.value === 'yoy'
      ? (t.revenue_yoy_growth || 0)
      : dataCaliber.value === 'mom'
        ? (t.revenue_mom_growth || 0)
        : toWan(t.revenue),
  }))
);

// Chart 2: Profit trend (line)
const profitTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    毛利额: dataCaliber.value === 'yoy'
      ? (t.gross_profit_yoy_growth || 0)
      : dataCaliber.value === 'mom'
        ? (t.gross_profit_mom_growth || 0)
        : (t.gross_profit || 0),
  }))
);

// Chart 4: Margin trend (line)
const marginTrendData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    期间: t.period,
    gross_margin: t.gross_margin || 0,
  }))
);

// Chart 5: Monthly revenue distribution (bar)
const monthlyRevenueData = computed(() =>
  (metricsData.value?.trend_series || []).map((t: TrendDataPoint) => ({
    月份: t.period,
    收入: toWan(t.revenue),
  }))
);

// KPI trend values from latest trend_series point
const orderCountTrend = computed(() => {
  const ts = metricsData.value?.trend_series || [];
  if (!ts.length) return undefined;
  const latest = ts[ts.length - 1];
  const key = compareBase.value === 'mom' ? 'order_count_mom_growth' as const : 'order_count_yoy_growth' as const;
  return latest[key] ?? undefined;
});

const grossMarginTrend = computed(() => {
  const ts = metricsData.value?.trend_series || [];
  if (!ts.length) return undefined;
  const latest = ts[ts.length - 1];
  const key = compareBase.value === 'mom' ? 'gross_margin_mom_growth' as const : 'gross_margin_yoy_growth' as const;
  return latest[key] ?? undefined;
});

// Multi-dimension: pivot per-entity trend data into multi-series format
function pivotMulti(seriesMap: Map<string, TrendDataPoint[]>, field: string, toWanFlag = true): Record<string, unknown>[] {
  const dimValues = [...seriesMap.keys()];
  if (!dimValues.length) return [];
  const periods = [...new Set([...seriesMap.values()].flatMap((arr) => arr.map((t) => t.period)))].sort();
  return periods.map((period) => {
    const point: Record<string, unknown> = { 期间: period };
    dimValues.forEach((dim) => {
      const tp = (seriesMap.get(dim) || []).find((t) => t.period === period);
      const raw = tp?.[field as keyof TrendDataPoint] ?? 0;
      point[dim] = toWanFlag ? toWan(raw as number) : raw;
    });
    return point;
  });
}

const multiRevenueData = computed(() => pivotMulti(perEntityTrends.value, 'revenue', true));
const multiProfitData = computed(() => pivotMulti(perEntityTrends.value, 'gross_profit', true));
const multiMarginData = computed(() => pivotMulti(perEntityTrends.value, 'gross_margin', false));

// Fetch per-entity trend series for multi-line display
async function fetchPerEntityTrends() {
  perEntityTrends.value = new Map();
  const dimData = metricsData.value?.dimension_trend_series || [];
  const dimValues = [...new Set(dimData.map((d) => d.dimension_value))].filter((d) => d != null && d !== undefined && d !== 'company');
  if (!isMultiDim.value || !dimValues.length) return;

  const promises = dimValues.map((dim) => {
    const filterParam = trendDimension.value === 'department' ? 'department' : 'product';
    return getCoreMetrics({
      period: period.value,
      dimension: trendDimension.value,
      [filterParam]: dim,
      period_dimension: periodDimension.value,
      compare: compareBase.value,
    }).then((axiosResp) => ({
      dimValue: dim,
      series: ((axiosResp.data.data as CoreMetricsResponse)?.trend_series || []),
    }));
  });
  const results = await Promise.allSettled(promises);
  const map = new Map<string, TrendDataPoint[]>();
  results.forEach((r) => {
    if (r.status === 'fulfilled') {
      map.set(r.value.dimValue, r.value.series);
    }
  });
  perEntityTrends.value = map;
}

const assistantContext = computed(() => ({
  period: period.value,
  dimension: trendDimension.value,
  entity: selectedEntity.value,
  period_dimension: periodDimension.value,
  period_compare_type: compareBase.value,
  active_section: 'trend',
}));

const recommendations = ref<AnalysisRecommendations>();

async function loadRecommendations() {
  try {
    const extra: Record<string, string | undefined> = {};
    if (trendDimension.value === 'department' && selectedEntity.value) {
      extra.department = selectedEntity.value;
    } else if (trendDimension.value === 'product_bgbu' && selectedEntity.value) {
      extra.product = selectedEntity.value;
    }
    const { data } = await getAnalysisRecommendations({
      page_type: 'trend',
      period: period.value,
      period_compare_type: compareBase.value,
      period_dimension: periodDimension.value,
      ...extra,
    });
    recommendations.value = data.data || undefined;
  } catch { /* non-critical */ }
}

async function fetchMetrics() {
  loading.value = true;
  try {
    const filterParam = trendDimension.value === 'department' ? 'department' : trendDimension.value === 'product_bgbu' ? 'product' : null;
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: trendDimension.value,
      [filterParam || 'entity']: filterParam && selectedEntity.value ? selectedEntity.value : undefined,
      period_dimension: periodDimension.value,
      compare: compareBase.value,
    });
    metricsData.value = resp.data as CoreMetricsResponse;
    await fetchPerEntityTrends();
  } finally {
    loading.value = false;
  }
}

async function fetchOptions() {
  try {
    const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
    const periods = ((periodResp.data as any)?.options || []) as string[];
    allPeriods.value = periods;
    if (!selectedPeriod.value && periods.length) {
      selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
    }
  } catch { /* interceptor handles errors */ }
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

// Reload entity options only when dimension changes (clears previous selection)
// Guard: prevent double-fetch during onMounted
let _mounted = false;

watch(trendDimension, async () => {
  if (_mounted) {
    await loadEntityOptions();
    fetchMetrics();
    loadRecommendations();
  }
});

// Refresh data and recommendations on other filter changes
watch([periodDimension, selectedPeriod, selectedEntity, compareBase], () => {
  if (!_mounted) return;
  fetchMetrics();
  loadRecommendations();
});

onMounted(async () => { await fetchOptions(); await nextTick(); _mounted = true; fetchMetrics(); loadRecommendations(); });
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
