<template>
  <div class="change-analysis-page">
    <div class="analysis-header">
      <a-page-header title="变动分析" sub-title="收入/毛利额/毛利率的变动及影响因素">
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
            <!-- Dimension selector -->
            <a-select v-model:value="dimension" :options="dimensionOptions" style="width: 140px" placeholder="维度" />
            <!-- Entity selector -->
            <a-select v-if="dimension !== 'company'" v-model:value="selectedEntity" :options="entityOptions" style="width: 180px" placeholder="实体" allow-clear />
            <a-button type="primary" @click="refresh">刷新</a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>

    <div class="page-content" :class="{ 'with-assistant': showAssistant }">
      <div class="main-area">
        <!-- Revenue change -->
        <a-card title="收入变动" size="small" class="section-card">
          <a-row :gutter="[16, 16]">
            <a-col :span="6">
              <KpiCard title="当期收入" :value="toWan(metricsData?.summary?.revenue)" unit="万元" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="基期收入" :value="toWan(basePeriodData?.summary?.revenue)" unit="万元" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="收入变化" :value="metricsData?.summary?.revenue_yoy_growth || 0" unit="%" :precision="2"
                :trend="metricsData?.summary?.revenue_yoy_growth" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <div class="impact-box">
                <div class="impact-title">主要变动影响</div>
                <div v-for="item in revenueTopImpacts" :key="item.name" class="impact-item">
                  <span class="impact-name">{{ item.name }}</span>
                  <span class="impact-value">{{ item.change }}</span>
                  <span class="impact-pct">影响{{ item.pct }}%</span>
                </div>
                <div v-if="!revenueTopImpacts.length" class="impact-empty">暂无数据</div>
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- Gross profit change -->
        <a-card title="毛利额变动" size="small" class="section-card">
          <a-row :gutter="[16, 16]">
            <a-col :span="6">
              <KpiCard title="当期毛利额" :value="toWan(metricsData?.summary?.gross_profit)" unit="万元" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="基期毛利额" :value="toWan(basePeriodData?.summary?.gross_profit)" unit="万元" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="毛利额变化" :value="metricsData?.summary?.gross_profit_yoy_growth || 0" unit="%" :precision="2"
                :trend="metricsData?.summary?.gross_profit_yoy_growth" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <div class="impact-box">
                <div class="impact-title">主要变动影响</div>
                <div v-for="item in profitTopImpacts" :key="item.name" class="impact-item">
                  <span class="impact-name">{{ item.name }}</span>
                  <span class="impact-value">{{ item.change }}</span>
                  <span class="impact-pct">影响{{ item.pct }}%</span>
                </div>
                <div v-if="!profitTopImpacts.length" class="impact-empty">暂无数据</div>
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- Margin change -->
        <a-card title="毛利率变动" size="small" class="section-card">
          <a-row :gutter="[16, 16]">
            <a-col :span="4">
              <KpiCard title="当期毛利率" :value="metricsData?.summary?.gross_margin || 0" unit="%" :precision="2" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="基期毛利率" :value="basePeriodData?.summary?.gross_margin || 0" unit="%" :precision="2" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="毛利率变化" :value="marginChangePp" unit="pp" :precision="2"
                :trend="marginChangePp" trendSuffix="pp" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="结构影响" :value="structureImpact" unit="pp" :precision="4" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="单因素毛利影响" :value="marginFactorImpact" unit="pp" :precision="4" />
            </a-col>
          </a-row>
        </a-card>

        <!-- Concentration ranking -->
        <a-card title="集中度排名" size="small" class="section">
          <ConcentrationPanel :breakdowns="metricsData?.breakdowns || []" :dimension="dimension" :customers="metricsData?.customer_breakdown || []" />
        </a-card>
      </div>

      <div v-if="showAssistant" class="assistant-area">
        <FinancialAssistantPanel :context="assistantContext" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import KpiCard from '@/components/dashboard/KpiCard.vue';
import ConcentrationPanel from '@/components/dashboard/ConcentrationPanel.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import type { CoreMetricsResponse } from '@/types/metrics';
import { toWan } from '@/utils/format';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('yearly');
const selectedPeriod = ref<string | undefined>();
const compareBase = ref<string>('yoy');
const dimension = ref<string>('customer');
const selectedEntity = ref<string | undefined>();
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const allPeriods = ref<string[]>([]);
const entityOptions = ref<Array<{ label: string; value: string }>>([]);

const dimensionOptions = [
  { label: '客户', value: 'customer' },
  { label: '产品线', value: 'product_line' },
  { label: '部门', value: 'department' },
  { label: '公司整体', value: 'company' },
];

// Derived period
const period = computed(() => {
  if (periodDimension.value === 'monthly') return selectedPeriod.value;
  if (periodDimension.value === 'yearly') return selectedPeriod.value ? selectedPeriod.value.slice(0, 4) : undefined;
  if (periodDimension.value === 'weekly') {
    if (selectedPeriod.value && selectedPeriod.value.includes('-Q')) {
      const [y, qStr] = selectedPeriod.value.split('-Q');
      const q = parseInt(qStr);
      return `${y}-${String(q * 3).padStart(2, '0')}`;
    }
    return selectedPeriod.value;
  }
  return undefined;
});

// Dynamic period select options
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  if (periodDimension.value === 'weekly') {
    const quarters = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const [y, m] = p.split('-');
        const q = Math.ceil(parseInt(m) / 3);
        quarters.add(`${y}-Q${q}`);
      }
    }
    return [...quarters].sort().reverse().map((v) => ({ label: v, value: v }));
  }
  if (periodDimension.value === 'yearly') {
    const years = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) years.add(p.split('-')[0]);
    }
    return [...years].sort().reverse().map((y) => ({ label: `${y}年`, value: `${y}` }));
  }
  // monthly
  const months = new Set<string>();
  for (const p of allPeriods.value) {
    if (p.includes('-')) months.add(`${p.split('-')[0]}-${p.split('-')[1]}`);
  }
  return [...months].sort().reverse().map((v) => {
    const [y, m] = v.split('-');
    return { label: `${y}年${parseInt(m)}月`, value: `${y}-${m}` };
  });
});

function onCustomRangeChange(dates: any) {
  if (dates && dates[0] && dates[1]) {
    const fmt = (d: any) => {
      const y = d.year?.() ?? d.getFullYear();
      const mo = d.month?.() ?? (d.getMonth() + 1);
      return `${y}-${String(mo + 1).padStart(2, '0')}`;
    };
    periodStart.value = fmt(dates[0]);
    periodEnd.value = fmt(dates[1]);
  } else {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
}

// Auto-select first period when dimension changes
watch(periodDimension, () => {
  const opts = periodSelectOptions.value;
  if (opts.length) selectedPeriod.value = opts[0].value;
});

// Data
const metricsData = ref<CoreMetricsResponse | null>(null);
const basePeriodData = ref<CoreMetricsResponse | null>(null);
const loading = ref(false);

// Compute base period for comparison
const basePeriod = computed(() => {
  if (!period.value) return undefined;
  if (compareBase.value === 'yoy') {
    // YoY: previous year same period
    if (period.value.length >= 7) {
      const y = parseInt(period.value.slice(0, 4));
      const rest = period.value.slice(4);
      return `${y - 1}${rest}`;
    }
    if (period.value.length === 4) return `${parseInt(period.value) - 1}`;
  }
  if (compareBase.value === 'mom') {
    // MoM: previous month
    if (period.value.length >= 7) {
      const y = parseInt(period.value.slice(0, 4));
      const m = parseInt(period.value.slice(5, 7));
      if (m === 1) return `${y - 1}-12`;
      return `${y}-${String(m - 1).padStart(2, '0')}`;
    }
  }
  return undefined;
});

// Margin change in pp
const marginChangePp = computed(() => {
  const curr = metricsData.value?.summary?.gross_margin || 0;
  const base = basePeriodData.value?.summary?.gross_margin || 0;
  return Math.round((curr - base) * 100) / 100;
});

// Structure and margin factor impact from margin_change_analysis
const structureImpact = computed(() => {
  const analysis = metricsData.value?.summary?.margin_change_analysis || [];
  return Math.round(analysis.reduce((sum, a) => sum + (a.structure_impact || 0), 0) * 10000) / 10000;
});
const marginFactorImpact = computed(() => {
  const analysis = metricsData.value?.summary?.margin_change_analysis || [];
  return Math.round(analysis.reduce((sum, a) => sum + (a.margin_impact || 0), 0) * 10000) / 10000;
});

// Top impacts for revenue/profit changes (explain 80% of change)
const revenueTopImpacts = computed(() => {
  if (dimension.value === 'customer') return []; // too many customers
  const breakdowns = metricsData.value?.breakdowns || [];
  const baseBreakdowns = basePeriodData.value?.breakdowns || [];
  const currTotal = metricsData.value?.summary?.revenue || 0;
  const baseTotal = basePeriodData.value?.summary?.revenue || 0;
  const totalChange = currTotal - baseTotal;
  if (!totalChange || !breakdowns.length) return [];

  const impacts = breakdowns.map((b) => {
    const baseItem = baseBreakdowns.find((bb) => bb.dimension_value === b.dimension_value);
    const change = (b.revenue || 0) - (baseItem?.revenue || 0);
    return { name: b.dimension_value, change: toWan(change), pct: Math.round(Math.abs(change / totalChange) * 100) };
  }).filter((i) => i.pct > 0).sort((a, b) => b.pct - a.pct);

  let cumPct = 0;
  return impacts.filter((i) => { cumPct += i.pct; return cumPct <= 80 || i === impacts[0]; });
});

const profitTopImpacts = computed(() => {
  if (dimension.value === 'customer') return [];
  const breakdowns = metricsData.value?.breakdowns || [];
  const baseBreakdowns = basePeriodData.value?.breakdowns || [];
  const currTotal = metricsData.value?.summary?.gross_profit || 0;
  const baseTotal = basePeriodData.value?.summary?.gross_profit || 0;
  const totalChange = currTotal - baseTotal;
  if (!totalChange || !breakdowns.length) return [];

  const impacts = breakdowns.map((b) => {
    const baseItem = baseBreakdowns.find((bb) => bb.dimension_value === b.dimension_value);
    const change = (b.gross_profit || 0) - (baseItem?.gross_profit || 0);
    return { name: b.dimension_value, change: toWan(change), pct: Math.round(Math.abs(change / totalChange) * 100) };
  }).filter((i) => i.pct > 0).sort((a, b) => b.pct - a.pct);

  let cumPct = 0;
  return impacts.filter((i) => { cumPct += i.pct; return cumPct <= 80 || i === impacts[0]; });
});

const assistantContext = computed(() => ({
  period: period.value,
  dimension: dimension.value,
  period_dimension: periodDimension.value,
  active_section: 'change_analysis',
}));

async function fetchMetrics() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: dimension.value,
      entity: dimension.value !== 'company' ? selectedEntity.value : undefined,
      period_dimension: periodDimension.value,
    });
    metricsData.value = resp.data as CoreMetricsResponse;

    // Fetch base period data for comparison
    if (basePeriod.value) {
      const { data: baseResp } = await getCoreMetrics({
        period: basePeriod.value,
        dimension: dimension.value,
        entity: dimension.value !== 'company' ? selectedEntity.value : undefined,
        period_dimension: periodDimension.value,
      });
      basePeriodData.value = baseResp.data as CoreMetricsResponse;
    } else {
      basePeriodData.value = null;
    }
  } catch {
    metricsData.value = null;
    basePeriodData.value = null;
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
}

async function loadEntityOptions() {
  if (dimension.value === 'company') {
    entityOptions.value = [];
    selectedEntity.value = undefined;
    return;
  }
  const { data: resp } = await getFilterOptions({ dimension: dimension.value });
  const opts = ((resp.data as any)?.options || []) as string[];
  entityOptions.value = opts.map((v) => ({ label: v, value: v }));
  selectedEntity.value = undefined;
}

function refresh() { fetchMetrics(); }

watch([periodDimension, selectedPeriod, dimension], async () => {
  await loadEntityOptions();
  fetchMetrics();
});
watch(selectedEntity, refresh);
watch(compareBase, fetchMetrics);

onMounted(async () => { await fetchOptions(); await fetchMetrics(); });
</script>

<style scoped lang="less">
.change-analysis-page {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .analysis-header {
    :deep(.ant-page-header) {
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--color-bg-layout);
    }
  }
}
.page-content {
  padding: 0 16px;
  display: flex;
  gap: 16px;

  &.with-assistant {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 16px;
  }

  .main-area {
    min-width: 0;
  }

  .assistant-area {
    min-width: 0;
  }
}
.section-card {
  margin-bottom: 0;
}
.section {
  margin-top: 12px;
}

// Impact box styles
.impact-box {
  padding: 12px;
  background: var(--color-bg-layout);
  border-radius: 8px;
  .impact-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: 8px;
  }
  .impact-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    .impact-name {
      font-size: 13px;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .impact-value {
      font-weight: 600;
      font-size: 13px;
      color: var(--color-primary, #1677ff);
    }
    .impact-pct {
      font-size: 12px;
      color: var(--color-text-secondary);
    }
  }
  .impact-empty {
    font-size: 13px;
    color: var(--color-text-secondary);
  }
}

@media (max-width: 1023px) {
  .page-content {
    display: flex;
    flex-direction: column;
  }
}
</style>