<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="客户分析" sub-title="客户收入、毛利贡献与集中度风险">
        <template #extra>
          <a-space wrap>
            <!-- Period dimension selector -->
            <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
              <a-select-option value="monthly">月度</a-select-option>
              <a-select-option value="quarterly">季度</a-select-option>
              <a-select-option value="cumulative">年累计</a-select-option>
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
            <!-- Customer selector -->
            <a-select v-model:value="selectedCustomer" :options="customerOptions" style="width: 180px" placeholder="客户" allow-clear />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights :breakdowns="displayBreakdowns" :summary="summary" dimension="customer" :max-count="5" class="section" />

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
          <KpiCard title="客户集中度Top3" :value="summary?.customer_concentration_top3 || 0" unit="%" :precision="2" />
        </a-col>
      </a-row>

      <!-- Drill-down toggle -->
      <div class="drill-bar" v-if="!drillMode">
        <span class="drill-hint">点击下方客户名称可钻取到销售产品层级</span>
      </div>
      <div class="drill-bar" v-else>
        <a-button size="small" @click="exitDrill">返回客户</a-button>
        <span class="drill-label">当前层级：销售产品（客户：{{ drillCustomer }}）</span>
      </div>

      <!-- Charts -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget :title="drillMode ? '销售产品收入排行' : '客户收入Top10'" :data="customerRevenueRanking" chart-type="bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="客户收入毛利对比" :data="customerRevenueMarginCompare" chart-type="grouped-bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
      </a-row>

      <!-- Charts Row 2: Margin pie -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="客户毛利率分布" :data="customerMarginPie" chart-type="pie" :loading="loading" @chart-click="onChartClick" />
        </a-col>
      </a-row>

      <!-- Detail Table -->
      <a-card :title="drillMode ? '销售产品明细' : '客户明细'" size="small" class="section">
        <a-table
          :columns="tableColumns"
          :data-source="displayBreakdowns"
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
import { toWan, formatPercent, formatWan } from '@/utils/format';
import { buildPeriodOptions, formatMonthValue, getDefaultPeriod, normalizePeriodDimension } from '@/utils/period';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('cumulative');
const selectedPeriod = ref<string | undefined>();
const compareBase = ref<string>('yoy');
const selectedCustomer = ref<string | undefined>();
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const allPeriods = ref<string[]>([]);
const customerOptions = ref<Array<{ label: string; value: string }>>([]);
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);

// Drill-down state
const drillMode = ref(false);
const drillCustomer = ref<string | undefined>();

// Current dimension: customer or sales_product (drill-down)
const currentDimension = computed(() => drillMode.value ? 'sales_product' : 'customer');

// When in non-drill mode, use customer_breakdown; in drill mode, use breakdowns
const displayBreakdowns = computed<BreakdownItem[]>(() => {
  if (drillMode.value) {
    return metricsData.value?.breakdowns || [];
  }
  return metricsData.value?.customer_breakdown || [];
});

// Derived period
const period = computed(() => {
  return periodDimension.value === 'custom' ? undefined : selectedPeriod.value;
});

// Period select options
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  return buildPeriodOptions(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

function onCustomRangeChange(dates: any) {
  if (dates && dates[0] && dates[1]) {
    periodStart.value = formatMonthValue(dates[0]);
    periodEnd.value = formatMonthValue(dates[1]);
  } else {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
}

watch(periodDimension, () => {
  selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

const summary = computed(() => metricsData.value?.summary);

// Table columns
const tableColumns = computed(() => [
  { title: drillMode.value ? '销售产品' : '客户', dataIndex: 'dimension_value', key: 'dimension_value', width: 160, fixed: 'left' },
  { title: '收入(万元)', key: 'revenue', width: 120 },
  { title: '收入贡献度', key: 'revenue_contribution', width: 120 },
  { title: '毛利(万元)', key: 'gross_profit', width: 120 },
  { title: '毛利贡献度', key: 'gross_margin_contribution', width: 120 },
  { title: '毛利率', key: 'gross_margin', width: 100 },
]);

function formatMargin(v: number | string | undefined | null): string {
  return formatPercent(v);
}

// Drill-down functions
function enterDrill(customerName: string) {
  drillMode.value = true;
  drillCustomer.value = customerName;
  fetchMetrics();
}

function exitDrill() {
  drillMode.value = false;
  drillCustomer.value = undefined;
  fetchMetrics();
}

function onChartClick(name: string) {
  if (!drillMode.value && drillCustomer.value !== name) {
    enterDrill(name);
  }
}

// Chart 1: Customer revenue top 10 (bar)
const customerRevenueRanking = computed(() =>
  [...displayBreakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10)
    .map((b) => ({
      [drillMode.value ? '销售产品' : '客户']: b.dimension_value,
      收入: b.revenue || 0,
    }))
);

// Chart 2: Customer revenue + gross profit grouped bar
const customerRevenueMarginCompare = computed(() =>
  displayBreakdowns.value.map((b) => ({
    客户: b.dimension_value,
    营业收入: b.revenue || 0,
    毛利额: b.gross_profit || 0,
  }))
);

// Chart 3: Customer margin rate pie
const customerMarginPie = computed(() =>
  displayBreakdowns.value.map((b) => ({
    客户: b.dimension_value,
    毛利率: b.gross_margin || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  customer: drillMode.value ? drillCustomer.value : selectedCustomer.value,
  period_dimension: periodDimension.value,
  period_start: periodStart.value,
  period_end: periodEnd.value,
  period_compare_type: compareBase.value,
  active_section: 'customer',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: currentDimension.value,
      entity: drillMode.value ? undefined : selectedCustomer.value,
      customer: drillMode.value ? drillCustomer.value : undefined,
      period_dimension: periodDimension.value,
      period_start: periodStart.value,
      period_end: periodEnd.value,
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
    selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
  }
  const { data: custResp } = await getFilterOptions({ dimension: 'customer' });
  const customers = ((custResp.data as any)?.options || []) as string[];
  customerOptions.value = customers.map((v) => ({ label: v, value: v }));
}

function refresh() { fetchMetrics(); }

watch([periodDimension, selectedPeriod, compareBase, selectedCustomer, periodStart, periodEnd], () => {
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