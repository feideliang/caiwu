<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="产品分析" sub-title="产品线收入、毛利贡献与结构风险">
        <template #extra>
          <a-space wrap>
            <!-- Period dimension selector -->
            <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
              <a-select-option value="monthly">月度</a-select-option>
              <a-select-option value="weekly">季度</a-select-option>
              <a-select-option value="yearly">年累计</a-select-option>
              <a-select-option value="custom">自定义期间</a-select-option>
            </a-select>
            <!-- Period selector -->
            <a-range-picker
              v-if="periodDimension === 'custom'"
              v-model:value="customRange"
              picker="month"
              :allow-clear="true"
              style="width: 280px"
              format="YYYY年M月"
              @change="onCustomRangeChange"
            />
            <a-select
              v-else
              v-model:value="selectedPeriod"
              :options="periodSelectOptions"
              style="width: 160px"
              placeholder="筛选周期"
              allow-clear
            />
            <!-- Compare base period -->
            <a-select v-model:value="compareBase" style="width: 120px" placeholder="对比基期">
              <a-select-option value="yoy">同比</a-select-option>
              <a-select-option value="mom">环比</a-select-option>
              <a-select-option value="custom_compare">自定义期间</a-select-option>
            </a-select>
            <!-- Product line selector -->
            <a-select v-model:value="selectedProduct" :options="productOptions" style="width: 180px" placeholder="产品线" allow-clear />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights :breakdowns="breakdowns" :summary="summary" dimension="product_line" :max-count="5" class="section" />

      <!-- KPI Cards (4) -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="收入" :value="toWan(summary?.revenue)" unit="万元" :precision="2" :trend="summary?.revenue_yoy_growth" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利额" :value="toWan(summary?.gross_profit)" unit="万元" :precision="2" :trend="summary?.gross_profit_yoy_growth" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" :precision="2" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="亏损产品占比" :value="lossRatio" unit="%" :precision="2" />
        </a-col>
      </a-row>

      <!-- Drill-down toggle -->
      <div class="drill-bar" v-if="!drillMode">
        <span class="drill-hint">点击下方产品线可钻取到销售产品名称层级</span>
      </div>
      <div class="drill-bar" v-else>
        <a-button size="small" @click="exitDrill">返回产品线</a-button>
        <span class="drill-label">当前层级：销售产品名称</span>
      </div>

      <!-- Charts -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget :title="drillMode ? '销售产品收入排行' : '产品收入排行'" :data="productRevenueRanking" chart-type="bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品线收入毛利对比" :data="productRevenueMarginCompare" chart-type="grouped-bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
      </a-row>

      <!-- Charts Row 2: Margin pie + Rev/Gross profit scatter -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="产品毛利率分布" :data="productMarginPie" chart-type="pie" :loading="loading" @chart-click="onChartClick" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="收入毛利气泡图" :data="productBubble" chart-type="scatter" :loading="loading" />
        </a-col>
      </a-row>

      <!-- Detail Table -->
      <a-card :title="drillMode ? '销售产品明细' : '产品线明细'" size="small" class="section">
        <a-table
          :columns="productTableColumns"
          :data-source="breakdowns"
          :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
          row-key="dimension_value"
          size="small"
          :scroll="{ x: 1000 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'dimension_value'">
              <a v-if="!drillMode" @click.prevent="enterDrill((record as BreakdownItem).dimension_value)">{{ (record as BreakdownItem).dimension_value }}</a>
              <span v-else>{{ (record as BreakdownItem).dimension_value }}</span>
            </template>
            <template v-if="column.key === 'revenue'">
              {{ formatWan((record as BreakdownItem).revenue) }}
            </template>
            <template v-if="column.key === 'revenue_contribution'">
              {{ formatMargin((record as BreakdownItem).revenue_contribution) }}
            </template>
            <template v-if="column.key === 'gross_profit'">
              {{ formatWan((record as BreakdownItem).gross_profit) }}
            </template>
            <template v-if="column.key === 'gross_margin_contribution'">
              {{ formatMargin((record as BreakdownItem).gross_margin_contribution) }}
            </template>
            <template v-if="column.key === 'gross_margin'">
              {{ formatMargin((record as BreakdownItem).gross_margin) }}
            </template>
            <template v-if="column.key === 'neg_margin_order_count'">
              {{ (record as BreakdownItem).neg_margin_order_count ?? '-' }}
            </template>
            <template v-if="column.key === 'neg_margin_amount'">
              {{ (record as BreakdownItem).neg_margin_amount != null ? formatWan((record as BreakdownItem).neg_margin_amount) : '-' }}
            </template>
          </template>
        </a-table>
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
import InlineInsights from '@/components/dashboard/InlineInsights.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import type { CoreMetricsResponse, BreakdownItem } from '@/types/metrics';
import { toWan, formatWan } from '@/utils/format';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('yearly');
const selectedPeriod = ref<string | undefined>();
const compareBase = ref<string>('yoy');
const selectedProduct = ref<string | undefined>();
const customRange = ref<[any, any] | null>(null);
const allPeriods = ref<string[]>([]);
const productOptions = ref<Array<{ label: string; value: string }>>([]);
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);

// Drill-down state
const drillMode = ref(false);
const drillProduct = ref<string | undefined>();

// Current dimension: product_line or sales_product (drill-down)
const currentDimension = computed(() => drillMode.value ? 'sales_product' : 'product_line');

// Derived period
const period = computed(() => {
  if (periodDimension.value === 'monthly') return selectedPeriod.value;
  if (periodDimension.value === 'yearly') return selectedPeriod.value ? selectedPeriod.value.slice(0, 4) : undefined;
  if (periodDimension.value === 'weekly') {
    if (selectedPeriod.value && selectedPeriod.value.includes('-Q')) {
      const [y, qStr] = selectedPeriod.value.split('-Q');
      return `${y}-${String(parseInt(qStr) * 3).padStart(2, '0')}`;
    }
    return selectedPeriod.value;
  }
  return undefined;
});

// Period select options
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  if (periodDimension.value === 'weekly') {
    const quarters = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const [y, m] = p.split('-');
        quarters.add(`${y}-Q${Math.ceil(parseInt(m) / 3)}`);
      }
    }
    return [...quarters].sort().reverse().map((v) => ({ label: v, value: v }));
  }
  if (periodDimension.value === 'yearly') {
    const years = new Set<string>();
    for (const p of allPeriods.value) { if (p.includes('-')) years.add(p.split('-')[0]); }
    return [...years].sort().reverse().map((y) => ({ label: `${y}年`, value: `${y}` }));
  }
  const months = new Set<string>();
  for (const p of allPeriods.value) { if (p.includes('-')) months.add(`${p.split('-')[0]}-${p.split('-')[1]}`); }
  return [...months].sort().reverse().map((v) => {
    const [y, m] = v.split('-');
    return { label: `${y}年${parseInt(m)}月`, value: `${y}-${m}` };
  });
});

function onCustomRangeChange(_dates: any) {}

watch(periodDimension, () => {
  const opts = periodSelectOptions.value;
  if (opts.length) selectedPeriod.value = opts[0].value;
});

const summary = computed(() => metricsData.value?.summary);
const breakdowns = computed<BreakdownItem[]>(() => metricsData.value?.breakdowns || []);

const lossRatio = computed(() => {
  if (summary.value?.negative_margin_product_ratio !== undefined && summary.value.negative_margin_product_ratio !== null) {
    return summary.value.negative_margin_product_ratio;
  }
  const items = breakdowns.value;
  if (!items.length) return 0;
  const lossCount = items.filter((b) => (b.gross_profit || 0) < 0).length;
  return Math.round((lossCount / items.length) * 100);
});

// Table columns
const productTableColumns = computed(() => [
  { title: drillMode.value ? '销售产品' : '产品线', dataIndex: 'dimension_value', key: 'dimension_value', width: 160, fixed: 'left' },
  { title: '收入(万元)', key: 'revenue', width: 120 },
  { title: '收入贡献度', key: 'revenue_contribution', width: 120 },
  { title: '毛利(万元)', key: 'gross_profit', width: 120 },
  { title: '毛利贡献度', key: 'gross_margin_contribution', width: 120 },
  { title: '毛利率', key: 'gross_margin', width: 100 },
  { title: '负毛利产品数量', key: 'neg_margin_order_count', width: 140 },
  { title: '负毛利金额(万元)', key: 'neg_margin_amount', width: 140 },
]);

function formatMargin(v: number | string | undefined | null): string {
  if (v == null || v === '') return '-';
  const n = typeof v === 'number' ? v : Number(v);
  return isNaN(n) ? '-' : n.toFixed(2) + '%';
}

// Drill-down functions
function enterDrill(productName: string) {
  drillMode.value = true;
  drillProduct.value = productName;
  fetchMetrics();
}

function exitDrill() {
  drillMode.value = false;
  drillProduct.value = undefined;
  fetchMetrics();
}

function onChartClick(name: string) {
  if (!drillMode.value && drillProduct.value !== name) {
    enterDrill(name);
  }
}

// Chart 1: Product revenue ranking (bar)
const productRevenueRanking = computed(() =>
  [...breakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 8)
    .map((b) => ({
      [drillMode.value ? '销售产品' : '产品线']: b.dimension_value,
      收入: b.revenue || 0,
    }))
);

// Chart 2: Product revenue + gross profit grouped horizontal bar
const productRevenueMarginCompare = computed(() =>
  breakdowns.value.map((b) => ({
    产品线: b.dimension_value,
    营业收入: b.revenue || 0,
    毛利额: b.gross_profit || 0,
  }))
);

// Chart 3: Product margin rate pie
const productMarginPie = computed(() =>
  breakdowns.value.map((b) => ({
    产品线: b.dimension_value,
    毛利率: b.gross_margin || 0,
  }))
);

// Chart 4: Product revenue vs gross profit bubble
const productBubble = computed(() =>
  breakdowns.value.map((b) => ({
    产品线: b.dimension_value,
    收入: b.revenue || 0,
    毛利额: b.gross_profit || 0,
    size: b.revenue || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  product: drillMode.value ? drillProduct.value : selectedProduct.value,
  period_dimension: periodDimension.value,
  period_compare_type: compareBase.value,
  active_section: 'product',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: currentDimension.value,
      entity: drillMode.value ? undefined : selectedProduct.value,
      product: drillMode.value ? drillProduct.value : undefined,
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
    selectedPeriod.value = periodDimension.value === 'yearly' ? periods[periods.length - 1].slice(0, 4) : periods[periods.length - 1];
  }
  const { data: prodResp } = await getFilterOptions({ dimension: 'product_line' });
  const prods = ((prodResp.data as any)?.options || []) as string[];
  productOptions.value = prods.map((v) => ({ label: v, value: v }));
}

function refresh() { fetchMetrics(); }

watch([periodDimension, selectedPeriod, compareBase, selectedProduct], () => {
  if (!drillMode.value) fetchMetrics();
});

onMounted(async () => { await fetchOptions(); await fetchMetrics(); });
</script>

<style scoped lang="less">
.analysis-page {
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

.drill-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  .drill-hint {
    font-size: 13px;
    color: var(--color-text-secondary);
  }
  .drill-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-primary, #1677ff);
  }
}

@media (max-width: 1023px) {
  .analysis-page {
    grid-template-columns: 1fr;
    .analysis-assistant { width: 100%; }
  }
}
</style>