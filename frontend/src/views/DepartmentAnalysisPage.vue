<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <a-page-header title="部门分析" sub-title="部门收入、毛利、贡献度与经营效率">
        <template #extra>
          <a-space wrap>
            <a-select v-model:value="period" :options="periodOptions" style="width: 140px" placeholder="期间" allow-clear />
            <a-select v-model:value="selectedDept" :options="deptOptions" style="width: 180px" placeholder="部门" allow-clear />
            <a-select v-model:value="compare" :options="compareOptions" style="width: 120px" />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>
    <div class="analysis-content">
      <!-- Insight Cards -->
      <InlineInsights :breakdowns="breakdowns" :summary="summary" dimension="department" :max-count="5" class="section" />

      <!-- KPI Cards (8) -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="本年累计收入" :value="toWan(summary?.revenue)" unit="万元" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="目标达成率" :value="summary?.achievement_rate || 0" unit="%" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="核心市场线" :value="0" :label-display="summary?.core_market_line || '-'" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="总订单数" :value="summary?.order_count || 0" unit="笔" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="本年累计毛利" :value="toWan(summary?.gross_profit)" unit="万元" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="整体毛利率" :value="summary?.gross_margin || 0" unit="%" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="最高价值市场线" :value="0" :label-display="summary?.highest_value_market_line || '-'" />
        </a-col>
        <a-col :xs="12" :sm="12" :md="6">
          <KpiCard title="亏损订单占比" :value="summary?.loss_ratio || 0" unit="%" />
        </a-col>
      </a-row>

      <!-- Charts -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="12">
          <ChartWidget title="收入分布" :data="deptRevenueDist" chart-type="pie" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="部门收入排行" :data="deptRevenueRanking" chart-type="bar" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="部门利润排行" :data="deptProfitRanking" chart-type="bar" :loading="loading" />
        </a-col>
        <a-col :xs="24" :md="12">
          <ChartWidget title="部门毛利率对比" :data="deptMarginCompare" chart-type="bar" :loading="loading" />
        </a-col>
      </a-row>

      <!-- 销售部门业绩明细 -->
      <a-card title="销售部门业绩明细" class="section" :loading="loading">
        <a-table
          :columns="deptTableColumns"
          :data-source="breakdowns"
          :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
          row-key="dimension_value"
          size="small"
          :scroll="{ x: 1200 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'revenue'">
              {{ formatWan((record as BreakdownItem).revenue) }}
            </template>
            <template v-if="column.key === 'gross_profit'">
              {{ formatWan((record as BreakdownItem).gross_profit) }}
            </template>
            <template v-if="column.key === 'gross_margin'">
              {{ formatMargin((record as BreakdownItem).gross_margin) }}
            </template>
            <template v-if="column.key === 'order_count'">
              {{ (record as BreakdownItem).order_count ?? '-' }}
            </template>
            <template v-if="column.key === 'avg_order_value'">
              {{ (record as BreakdownItem).avg_order_value != null ? formatWan((record as BreakdownItem).avg_order_value) : '-' }}
            </template>
            <template v-if="column.key === 'revenue_yoy_growth'">
              <span :style="{ color: ((record as BreakdownItem).revenue_yoy_growth ?? 0) >= 0 ? '#52c41a' : '#ff4d4f' }">
                {{ formatGrowth((record as BreakdownItem).revenue_yoy_growth) }}
              </span>
            </template>
            <template v-if="column.key === 'health'">
              <a-tooltip>
                <template #title>{{ getHealthFormula(record as BreakdownItem) }}</template>
                <a-tag :color="getHealthColor(record as BreakdownItem)">{{ getHealthLabel(record as BreakdownItem) }}</a-tag>
              </a-tooltip>
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

const period = ref<string | undefined>('2026-03');
const compare = ref('mom');
const selectedDept = ref<string | undefined>();
const loading = ref(false);
const metricsData = ref<CoreMetricsResponse | null>(null);
const periodOptions = ref<Array<{ label: string; value: string }>>([]);
const deptOptions = ref<Array<{ label: string; value: string }>>([]);

const compareOptions = [
  { label: '环比', value: 'mom' },
  { label: '同比', value: 'yoy' },
  { label: '累计', value: 'cumulative' },
];

const summary = computed(() => metricsData.value?.summary);
const breakdowns = computed<BreakdownItem[]>(() => metricsData.value?.breakdowns || []);

const deptTableColumns = [
  { title: '部门', dataIndex: 'dimension_value', key: 'dimension_value', width: 140, fixed: 'left' },
  { title: '收入(万元)', key: 'revenue', width: 120, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.revenue || 0) - (b.revenue || 0) },
  { title: '毛利(万元)', key: 'gross_profit', width: 120, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.gross_profit || 0) - (b.gross_profit || 0) },
  { title: '毛利率', key: 'gross_margin', width: 100, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.gross_margin || 0) - (b.gross_margin || 0) },
  { title: '订单数', key: 'order_count', width: 100, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.order_count || 0) - (b.order_count || 0) },
  { title: '客单价(万元)', key: 'avg_order_value', width: 130, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.avg_order_value || 0) - (b.avg_order_value || 0) },
  { title: '同比增长', key: 'revenue_yoy_growth', width: 120, sorter: (a: BreakdownItem, b: BreakdownItem) => (a.revenue_yoy_growth || 0) - (b.revenue_yoy_growth || 0) },
  { title: '健康度', key: 'health', width: 100 },
];

function formatGrowth(v: number | null | undefined): string {
  if (v == null) return '-';
  return v.toFixed(2) + '%';
}

function formatMargin(v: number | string | undefined | null): string {
  if (v == null || v === '') return '-';
  const n = typeof v === 'number' ? v : Number(v);
  return isNaN(n) ? '-' : n.toFixed(2) + '%';
}

function getHealthLabel(item: BreakdownItem): string {
  const margin = typeof item.gross_margin === 'number' ? item.gross_margin : Number(item.gross_margin) || 0;
  const growth = item.revenue_yoy_growth ?? 0;
  if (margin >= 30 && growth >= 0) return '健康';
  if (margin >= 15 && growth >= -10) return '一般';
  if (margin < 0) return '亏损';
  return '关注';
}

function getHealthColor(item: BreakdownItem): string {
  const margin = typeof item.gross_margin === 'number' ? item.gross_margin : Number(item.gross_margin) || 0;
  const growth = item.revenue_yoy_growth ?? 0;
  if (margin >= 30 && growth >= 0) return 'green';
  if (margin >= 15 && growth >= -10) return 'orange';
  if (margin < 0) return 'red';
  return 'gold';
}

function getHealthFormula(item: BreakdownItem): string {
  const margin = typeof item.gross_margin === 'number' ? item.gross_margin : Number(item.gross_margin) || 0;
  const growth = item.revenue_yoy_growth ?? 0;
  if (margin >= 30 && growth >= 0) return '健康：毛利率 >= 30% 且 同比增长 >= 0%';
  if (margin >= 15 && growth >= -10) return '一般：毛利率 >= 15% 且 同比增长 >= -10%';
  if (margin < 0) return '亏损：毛利率 < 0%';
  return '关注：未达到健康或一般标准，需重点关注';
}

// Chart 1: Revenue distribution (pie)
const deptRevenueDist = computed(() =>
  breakdowns.value.map((b) => ({
    部门: b.dimension_value,
    收入: b.revenue || 0,
  }))
);

// Chart 2: Department revenue ranking (bar)
const deptRevenueRanking = computed(() =>
  [...breakdowns.value]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .map((b) => ({ 部门: b.dimension_value, 收入: b.revenue || 0 }))
);

// Chart 3: Department profit ranking (bar)
const deptProfitRanking = computed(() =>
  [...breakdowns.value]
    .sort((a, b) => (b.gross_profit || 0) - (a.gross_profit || 0))
    .map((b) => ({ 部门: b.dimension_value, 毛利额: b.gross_profit || 0 }))
);

// Chart 4: Department margin comparison (bar)
const deptMarginCompare = computed(() =>
  breakdowns.value.map((b) => ({
    部门: b.dimension_value,
    毛利率: b.gross_margin || 0,
    收入: b.revenue || 0,
  }))
);

const assistantContext = computed(() => ({
  period: period.value,
  department: selectedDept.value,
  period_compare_type: compare.value,
  active_section: 'department',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: 'department',
      entity: selectedDept.value,
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

async function loadDeptOptions() {
  const { data: deptResp } = await getFilterOptions({ dimension: 'department' });
  const depts = ((deptResp.data as any)?.options || []) as string[];
  if (depts.length) {
    deptOptions.value = depts.map((v) => ({ label: v, value: v }));
  } else {
    // Fallback: derive from metrics breakdowns
    const deptValues = new Set(breakdowns.value.map((b) => b.dimension_value));
    deptOptions.value = [...deptValues].map((v) => ({ label: v, value: v }));
  }
}

function refresh() { fetchMetrics(); }
watch([period, compare, selectedDept], refresh);

onMounted(async () => { await fetchOptions(); await fetchMetrics(); await loadDeptOptions(); });
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
