<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="部门分析" sub-title="部门收入、毛利、贡献度与经营效率">
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
            <!-- Department selector -->
            <a-select v-if="!authStore.isDeptRestricted" v-model:value="selectedDept" :options="deptOptions" style="width: 180px" placeholder="部门" allow-clear />
            <a-tag v-else color="blue">{{ authStore.department }}</a-tag>
            <!-- Secondary dimension selector -->
            <a-select v-if="selectedDept || authStore.isDeptRestricted" v-model:value="secondaryDimension" style="width: 130px" placeholder="对比维度">
              <a-select-option value="product_line">产品线</a-select-option>
              <a-select-option value="customer">客户</a-select-option>
            </a-select>
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights :breakdowns="displayBreakdowns" :summary="summary" dimension="department" :max-count="5" class="section" />

      <!-- KPI Cards (4) -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="营业收入" :value="toWan(summary?.revenue)" unit="万元" :precision="0" :trend="revTrend" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利额" :value="toWan(summary?.gross_profit)" unit="万元" :precision="0" :trend="gpTrend" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="毛利率" :value="summary?.gross_margin || 0" unit="%" :precision="2"
  :trend="gmTrend" trendSuffix="pp" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="负毛利订单占比" :value="summary?.negative_margin_order_ratio || 0" unit="%" :precision="2" :trend="negOrderTrend" trendSuffix="pp" />
        </a-col>
      </a-row>

      <!-- Drill-down bar -->
      <div class="drill-bar" v-if="drillLevel === 0">
        <span class="drill-hint">点击图表可选择下钻维度（产品线/客户）</span>
      </div>
      <div class="drill-bar" v-else-if="drillLevel === 1">
        <a-button size="small" @click="exitDrill">返回部门总览</a-button>
        <span class="drill-label">当前层级：{{ drillDept }} → {{ drillDimLabel }}</span>
        <a-tag color="blue">{{ drillDimLabel }}</a-tag>
      </div>
      <div class="drill-bar" v-else>
        <a-button size="small" @click="goBackToLevel1">返回上级</a-button>
        <span class="drill-label">当前层级：{{ drillDept }} → {{ drillDimLabel }} → {{ drillEntity }}</span>
        <a-tag color="green">销售产品</a-tag>
      </div>

      <!-- Charts -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget :title="revenueChartTitle" :data="revenueChartData" :chart-type="revenueChartType" :loading="loading" @chart-click="onChartClick" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget :title="marginChartTitle" :data="marginChartData" chart-type="grouped-bar" :loading="loading" @chart-click="onChartClick" />
        </a-col>
      </a-row>

      <!-- Detail Table -->
      <a-card :title="tableTitle" class="section" :loading="loading">
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
              <a v-if="drillLevel === 0" @click.prevent="onDimensionClick((record as BreakdownItem).dimension_value)">{{ (record as BreakdownItem).dimension_value }}</a>
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
      <FinancialAssistantPanel :context="assistantContext" :recommendations="recommendations" />
    </div>

    <!-- Drill dimension picker modal -->
    <a-modal v-model:visible="drillModalVisible" title="选择下钻维度" :footer="null" width="320px">
      <a-space direction="vertical" style="width: 100%">
        <a-button type="primary" block size="large" @click="confirmDrillDim('product_line')">产品线</a-button>
        <a-button block size="large" @click="confirmDrillDim('customer')">客户</a-button>
      </a-space>
    </a-modal>

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
            选择市场线后，同比/环比的分母（基期数据）也按相同市场线过滤，确保对比口径一致。未选择时使用公司整体数据（bgbu=ALL）。增长率超过100%属于正常现象，表示当期收入超过基期一倍以上。
          </a-descriptions-item>
        </a-descriptions>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store/auth';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
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

const authStore = useAuthStore();
const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('cumulative');
const selectedPeriod = ref<string | undefined>();
const compareBase = ref<string>('yoy');
const selectedDept = ref<string | undefined>();
const secondaryDimension = ref<string>('product_line');
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const allPeriods = ref<string[]>([]);
const deptOptions = ref<Array<{ label: string; value: string }>>([]);
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);

// Drill-down state
const drillLevel = ref(0);  // 0=部门总览, 1=产品线/客户, 2=销售产品
const drillDept = ref<string>();
const drillDim = ref<'product_line' | 'customer'>();
const drillEntity = ref<string>();
const drillModalVisible = ref(false);
const drillPendingName = ref<string>();

const drillDimLabel = computed(() => drillDim.value === 'product_line' ? '产品线' : '客户');

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
const breakdowns = computed<BreakdownItem[]>(() => metricsData.value?.breakdowns || []);

// Secondary dimension toggle: switch between product_line and customer breakdown
const displayBreakdowns = computed<BreakdownItem[]>(() => {
  if (secondaryDimension.value === 'customer') {
    return metricsData.value?.customer_breakdown || [];
  }
  return breakdowns.value;
});

// Dynamic trend fields based on compare mode
const isMom = computed(() => compareBase.value === 'mom');
const revTrend = computed(() => isMom.value ? summary.value?.revenue_mom_growth : summary.value?.revenue_yoy_growth);
const gpTrend = computed(() => isMom.value ? summary.value?.gross_profit_mom_growth : summary.value?.gross_profit_yoy_growth);
const gmTrend = computed(() => isMom.value ? summary.value?.gross_margin_mom_change : summary.value?.gross_margin_yoy_change);
const negOrderTrend = computed(() => isMom.value ? summary.value?.negative_margin_order_mom_change : summary.value?.negative_margin_order_yoy_change);

// Dynamic column label
const dimColLabel = computed(() => {
  if (drillLevel.value === 0) {
    return secondaryDimension.value === 'customer' ? '客户' : '产品线';
  }
  if (drillLevel.value === 1) return drillDimLabel.value;
  return '销售产品';
});

// Secondary dimension label for titles
const secondaryDimLabel = computed(() => secondaryDimension.value === 'customer' ? '客户' : '产品线');

// Table columns
const tableColumns = computed(() => [
  { title: dimColLabel.value, dataIndex: 'dimension_value', key: 'dimension_value', width: 140, fixed: 'left' as const },
  { title: '收入(万元)', key: 'revenue', width: 120, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.revenue || 0) - (b.revenue || 0) },
  { title: '收入贡献度', key: 'revenue_contribution', width: 120 },
  { title: '毛利(万元)', key: 'gross_profit', width: 120 },
  { title: '毛利贡献度', key: 'gross_margin_contribution', width: 120 },
  { title: '毛利率', key: 'gross_margin', width: 100 },
  { title: '负毛利订单数量', key: 'neg_margin_order_count', width: 140 },
  { title: '负毛利金额(万元)', key: 'neg_margin_amount', width: 140 },
]);

function formatMargin(v: number | string | undefined | null): string {
  return formatPercent(v);
}

// Dynamic chart titles
const revenueChartTitle = computed(() => {
  if (drillLevel.value === 0) return `${secondaryDimLabel.value}收入排行(万元)`;
  if (drillLevel.value === 1) return `${drillDimLabel.value}收入排行`;
  return '销售产品收入排行';
});

const marginChartTitle = computed(() => {
  if (drillLevel.value === 0) return `${secondaryDimLabel.value}收入毛利率对比`;
  if (drillLevel.value === 1) return `${drillDimLabel.value}收入毛利对比`;
  return '销售产品收入毛利对比';
});

const tableTitle = computed(() => {
  if (drillLevel.value === 0) return `${secondaryDimLabel.value}业绩明细`;
  if (drillLevel.value === 1) return `${drillDimLabel.value}业绩明细`;
  return '销售产品明细';
});

const revenueChartType = computed(() => drillLevel.value === 0 ? 'pie' : 'bar');

// Chart data computations
const revenueChartData = computed(() => {
  if (drillLevel.value === 0) {
    // Revenue pie/bar chart — top 10
    return [...displayBreakdowns.value]
      .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
      .slice(0, 10)
      .map((b) => ({ [secondaryDimLabel.value]: b.dimension_value, '收入(万元)': Math.round((toWan(b.revenue) || 0) * 100) / 100 }));
  }
  // Bar chart for drill levels
  const key = drillLevel.value === 1 ? drillDimLabel.value : '销售产品';
  return [...displayBreakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10)
    .map((b) => ({ [key]: b.dimension_value, '收入(万元)': Math.round((toWan(b.revenue) || 0) * 100) / 100 }));
});

const marginChartData = computed(() => {
  const key = drillLevel.value === 0 ? secondaryDimLabel.value : (drillLevel.value === 1 ? drillDimLabel.value : '销售产品');
  return [...displayBreakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10)
    .map((b) => ({
    [key]: b.dimension_value,
    '营业收入(万元)': Math.round((toWan(b.revenue) || 0) * 100) / 100,
    '毛利额(万元)': Math.round((toWan(b.gross_profit) || 0) * 100) / 100,
    毛利率: b.gross_margin || 0,
  }));
});

const assistantContext = computed(() => ({
  period: period.value,
  department: selectedDept.value,
  period_dimension: periodDimension.value,
  period_start: periodStart.value,
  period_end: periodEnd.value,
  period_compare_type: compareBase.value,
  active_section: 'department',
}));

const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'department',
      period: period.value,
      period_compare_type: compareBase.value,
      department: selectedDept.value,
    });
    recommendations.value = data.data || null;
  } catch { /* non-critical */ }
}

// Drill-down functions
function onDimensionClick(name: string) {
  drillPendingName.value = name;
  drillModalVisible.value = true;
}

function onChartClick(name: string) {
  if (drillLevel.value === 0) {
    drillPendingName.value = name;
    drillModalVisible.value = true;
  } else if (drillLevel.value === 1) {
    enterDrillLevel2(name);
  }
  // Level 2 has no further drill
}

function confirmDrillDim(dim: 'product_line' | 'customer') {
  drillModalVisible.value = false;
  drillLevel.value = 1;
  drillDept.value = drillPendingName.value;
  drillDim.value = dim;
  fetchMetrics();
}

function enterDrillLevel2(name: string) {
  drillLevel.value = 2;
  drillEntity.value = name;
  fetchMetrics();
}

function exitDrill() {
  drillLevel.value = 0;
  drillDept.value = undefined;
  drillDim.value = undefined;
  drillEntity.value = undefined;
  fetchMetrics();
}

function goBackToLevel1() {
  drillLevel.value = 1;
  drillEntity.value = undefined;
  fetchMetrics();
}

async function fetchMetrics() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      period: period.value,
      period_dimension: periodDimension.value,
      compare: compareBase.value,
      period_start: periodStart.value,
      period_end: periodEnd.value,
    };
    if (drillLevel.value === 0) {
      params.dimension = 'department';
      params.entity = selectedDept.value;
    } else if (drillLevel.value === 1) {
      params.dimension = drillDim.value;
      params.department = drillDept.value;
    } else {
      params.dimension = 'sales_product';
      params.department = drillDept.value;
      if (drillDim.value === 'product_line') {
        params.product = drillEntity.value;
      } else {
        params.customer = drillEntity.value;
      }
    }
    const { data: resp } = await getCoreMetrics(params);
    metricsData.value = resp.data as CoreMetricsResponse;
  } catch(err) {
    metricsData.value = null;
    console.error(err);
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
    const { data: deptResp } = await getFilterOptions({ dimension: 'department' });
    const depts = ((deptResp.data as any)?.options || []) as string[];
    deptOptions.value = depts.map((v) => ({ label: v, value: v }));
  } catch(err) {
    console.error('Failed to load filter options:', err);
  }
}

function refresh() { fetchMetrics(); }

// Ignore filter changes when in drill mode
watch([periodDimension, selectedPeriod, compareBase, selectedDept, periodStart, periodEnd], () => {
  if (drillLevel.value === 0) {
    fetchMetrics();
    loadRecommendations();
  }
});

onMounted(async () => { await fetchOptions(); await fetchMetrics(); loadRecommendations(); });
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