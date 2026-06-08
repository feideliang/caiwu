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
            <a-select v-model:value="selectedCustomer" :options="filteredCustomerOptions" style="width: 180px" placeholder="客户" allow-clear show-search @search="(val: string) => customerSearchValue = val" />
            <!-- Secondary dimension selector -->
            <a-select v-if="selectedCustomer" v-model:value="secondaryDimension" style="width: 130px" placeholder="对比维度">
              <a-select-option value="customer">客户</a-select-option>
              <a-select-option value="contract_type">合同类型</a-select-option>
            </a-select>
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
          <KpiCard title="收入" :value="toWan(summary?.revenue)" unit="万元" :precision="0" :trend="revTrend" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利额" :value="toWan(summary?.gross_profit)" unit="万元" :precision="0" :trend="gpTrend" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" :precision="2" :trend="gmTrend" trendSuffix="pp" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="客户集中度Top10" :value="summary?.customer_concentration_top10 || 0" unit="%" :precision="2" :trend="top10Trend" trendSuffix="pp" />
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
          <ChartWidget :title="drillMode ? '销售产品收入排行' : (secondaryDimLabel + '收入Top10')" :data="customerRevenueRanking" chart-type="bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget :title="drillMode ? '销售产品收入毛利对比' : (secondaryDimLabel + '收入毛利对比')" :data="customerRevenueMarginCompare" chart-type="grouped-bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
      </a-row>

      <!-- Charts Row 2: Margin pie -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget :title="drillMode ? '销售产品毛利率分布' : (secondaryDimLabel + '毛利率分布')" :data="customerMarginPie" chart-type="pie" :loading="loading" @chart-click="onChartClick" />
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
          <a-descriptions-item label="毛利率">
            毛利额 / 营业收入 x 100%
          </a-descriptions-item>
          <a-descriptions-item label="筛选影响">
            选择客户后，同比/环比的分母（基期数据）也按相同客户过滤，确保对比口径一致。增长率超过100%属于正常现象。
          </a-descriptions-item>
        </a-descriptions>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import KpiCard from '@/components/dashboard/KpiCard.vue';
import ChartWidget from '@/components/dashboard/ChartWidget.vue';
import InlineInsights from '@/components/dashboard/InlineInsights.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import { getAnalysisRecommendations } from '@/api/ai';
import type { AnalysisRecommendations } from '@/types/analysis';
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
const secondaryDimension = ref<string>('customer');
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const allPeriods = ref<string[]>([]);
const customerOptions = ref<Array<{ label: string; value: string }>>([]);
const customerSearchValue = ref('');
const filteredCustomerOptions = computed(() => {
  if (!customerSearchValue.value) return customerOptions.value;
  const kw = customerSearchValue.value.toLowerCase();
  return customerOptions.value.filter(o => o.label.toLowerCase().includes(kw));
});
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);

// Drill-down state
const drillMode = ref(false);
const drillCustomer = ref<string | undefined>();

// Current dimension: customer or sales_product (drill-down)
const currentDimension = computed(() => drillMode.value ? 'sales_product' : 'customer');

// When in non-drill mode, use customer_breakdown or contract_type_breakdown based on secondaryDimension
const secondaryDimLabel = computed(() => secondaryDimension.value === 'contract_type' ? '合同类型' : '客户');

const displayBreakdowns = computed<BreakdownItem[]>(() => {
  if (drillMode.value) {
    return metricsData.value?.breakdowns || [];
  }
  if (secondaryDimension.value === 'contract_type') {
    return metricsData.value?.contract_type_breakdown || [];
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

// Dynamic trend fields based on compare mode
const isMom = computed(() => compareBase.value === 'mom');
const revTrend = computed(() => isMom.value ? summary.value?.revenue_mom_growth : summary.value?.revenue_yoy_growth);
const gpTrend = computed(() => isMom.value ? summary.value?.gross_profit_mom_growth : summary.value?.gross_profit_yoy_growth);
const gmTrend = computed(() => isMom.value ? summary.value?.gross_margin_mom_change : summary.value?.gross_margin_yoy_change);
const top10Trend = computed(() => undefined);

// Table columns
const tableColumns = computed(() => [
  { title: drillMode.value ? '销售产品' : secondaryDimLabel.value, dataIndex: 'dimension_value', key: 'dimension_value', width: 160, fixed: 'left' },
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
      [drillMode.value ? '销售产品' : secondaryDimLabel.value]: b.dimension_value,
      '收入(万元)': toWan(b.revenue),
    }))
);

// Chart 2: Customer revenue + gross profit grouped bar
const customerRevenueMarginCompare = computed(() =>
  [...displayBreakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10)
    .map((b) => ({
    [drillMode.value ? '销售产品' : secondaryDimLabel.value]: b.dimension_value,
    '营业收入(万元)': Math.round((toWan(b.revenue) || 0) * 100) / 100,
    '毛利额(万元)': Math.round((toWan(b.gross_profit) || 0) * 100) / 100,
  }))
);

// Chart 3: Customer margin rate pie
const customerMarginPie = computed(() =>
  [...displayBreakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10)
    .map((b) => ({
    [drillMode.value ? '销售产品' : secondaryDimLabel.value]: b.dimension_value,
    毛利率: b.gross_margin || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  customer: drillMode.value ? drillCustomer.value : selectedCustomer.value,
  period_dimension: periodDimension.value,
  period_start: periodStart.value,
  period_end: periodEnd.value,
      compare: compareBase.value,
  period_compare_type: compareBase.value,
  active_section: 'customer',
}));

const recommendations = ref<AnalysisRecommendations>();

async function loadRecommendations() {
  try {
    const customerParam = drillMode.value ? drillCustomer.value : selectedCustomer.value;
    const { data } = await getAnalysisRecommendations({
      page_type: 'customer',
      period: period.value,
      period_compare_type: compareBase.value,
      ...(customerParam ? { customer: customerParam.trim() } : {}),
    });
    recommendations.value = data.data || undefined;
  } catch { /* non-critical */ }
}

async function fetchMetrics() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      period: period.value,
      dimension: currentDimension.value,
      period_dimension: periodDimension.value,
      period_start: periodStart.value,
      period_end: periodEnd.value,
      compare: compareBase.value,
    };
    if (drillMode.value && drillCustomer.value) {
      params.entity = drillCustomer.value;
    } else if (selectedCustomer.value) {
      params.entity = selectedCustomer.value;
    }
    const { data: resp } = await getCoreMetrics(params);
    metricsData.value = resp.data as CoreMetricsResponse;
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
    const { data: custResp } = await getFilterOptions({ dimension: 'customer' });
    const customers = ((custResp.data as any)?.options || []) as any[];
    customerOptions.value = customers.map((v: any) =>
      typeof v === 'string' ? ({ label: v, value: v }) : v,
    );
  } catch { /* interceptor handles errors */ }
}

function refresh() { fetchMetrics(); }

// Guard: prevent double-fetch when fetchOptions sets selectedPeriod during onMounted
let _mounted = false;

watch([periodDimension, selectedPeriod, compareBase, selectedCustomer, periodStart, periodEnd, secondaryDimension], () => {
  if (!_mounted) return;
  if (!drillMode.value) {
    fetchMetrics();
    loadRecommendations();
  }
});

onMounted(async () => { await fetchOptions(); await nextTick(); _mounted = true; fetchMetrics(); loadRecommendations(); });
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