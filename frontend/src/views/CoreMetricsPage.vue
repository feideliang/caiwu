<template>
  <div class="change-analysis-page">
    <div class="analysis-header">
      <a-page-header title="变动分析" sub-title="收入/毛利额/毛利率的变动及影响因素">
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
              <div class="change-card">
                <div class="change-title">收入变化</div>
                <div class="change-value">
                  <span class="change-amount">{{ formatWan(revenueChangeValue, 2) }}万元</span>
                </div>
                <div class="change-rate" :class="revenueChangeRate >= 0 ? 'up' : 'down'">
                  {{ revenueChangeRate >= 0 ? '+' : '' }}{{ revenueChangeRate?.toFixed(2) }}%
                </div>
              </div>
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
              <div class="change-card">
                <div class="change-title">毛利额变化</div>
                <div class="change-value">
                  <span class="change-amount">{{ formatWan(profitChangeValue, 2) }}万元</span>
                </div>
                <div class="change-rate" :class="profitChangeRate >= 0 ? 'up' : 'down'">
                  {{ profitChangeRate >= 0 ? '+' : '' }}{{ profitChangeRate?.toFixed(2) }}%
                </div>
              </div>
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
              <KpiCard title="存续结构影响" :value="continuingStructureImpact" unit="pp" :precision="4" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="存续毛利影响" :value="continuingMarginImpact" unit="pp" :precision="4" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="新增影响" :value="newImpact" unit="pp" :precision="4" />
            </a-col>
            <a-col :span="4">
              <KpiCard title="退出影响" :value="exitImpact" unit="pp" :precision="4" />
            </a-col>
          </a-row>
        </a-card>

        <a-card title="毛利率变动拆解明细" size="small" class="section-card">
          <a-table
            :columns="marginAnalysisColumns"
            :data-source="metricsData?.summary?.margin_change_analysis || []"
            row-key="dimension_value"
            size="small"
            :pagination="{ pageSize: 10 }"
            :scroll="{ x: 1200 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'category'">
                {{ categoryLabel((record as any).category) }}
              </template>
              <template v-if="column.key === 'current_revenue' || column.key === 'base_revenue'">
                {{ formatWan((record as any)[column.key], 2) }}万元
              </template>
              <template v-if="column.key === 'current_margin' || column.key === 'base_margin'">
                {{ formatPercent((record as any)[column.key]) }}
              </template>
              <template v-if="column.key === 'structure_impact' || column.key === 'margin_impact' || column.key === 'total_impact'">
                {{ formatPp((record as any)[column.key]) }}
              </template>
            </template>
          </a-table>
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
import { formatPercent, formatPp, formatWan, toWan } from '@/utils/format';
import { buildPeriodOptions, formatMonthValue, getComparePeriod, getDefaultPeriod, normalizePeriodDimension } from '@/utils/period';

const isSmall = ref(window.innerWidth < 1024);
function updateSize() { isSmall.value = window.innerWidth < 1024; }
onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));
const showAssistant = computed(() => !isSmall.value);

// Filter state
const periodDimension = ref<string>('cumulative');
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

const period = computed(() => {
  return periodDimension.value === 'custom' ? undefined : selectedPeriod.value;
});

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

// Auto-select first period when dimension changes
watch(periodDimension, () => {
  selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

// Data
const metricsData = ref<CoreMetricsResponse | null>(null);
const basePeriodData = ref<CoreMetricsResponse | null>(null);
const loading = ref(false);

// Compute base period for comparison
const basePeriod = computed(() => {
  return getComparePeriod(period.value, compareBase.value, normalizePeriodDimension(periodDimension.value));
});

// Margin change in pp
const marginChangePp = computed(() => {
  const curr = metricsData.value?.summary?.gross_margin || 0;
  const base = basePeriodData.value?.summary?.gross_margin || 0;
  return Math.round((curr - base) * 100) / 100;
});

// Absolute change values
const revenueChangeValue = computed(() => {
  const curr = metricsData.value?.summary?.revenue || 0;
  const base = basePeriodData.value?.summary?.revenue;
  if (curr == null || base == null) return 0;
  return curr - base;
});

const profitChangeValue = computed(() => {
  const curr = metricsData.value?.summary?.gross_profit;
  const base = basePeriodData.value?.summary?.gross_profit;
  if (curr == null || base == null) return 0;
  return curr - base;
});

const revenueChangeRate = computed(() => {
  return compareBase.value === 'mom'
    ? (metricsData.value?.summary?.revenue_mom_growth || 0)
    : (metricsData.value?.summary?.revenue_yoy_growth || 0);
});

const profitChangeRate = computed(() => {
  return compareBase.value === 'mom'
    ? (metricsData.value?.summary?.gross_profit_mom_growth || 0)
    : (metricsData.value?.summary?.gross_profit_yoy_growth || 0);
});

// Structure and margin factor impact from margin_change_analysis
const continuingStructureImpact = computed(() => {
  return metricsData.value?.summary?.margin_change_summary?.continuing_structure_impact || 0;
});
const continuingMarginImpact = computed(() => {
  return metricsData.value?.summary?.margin_change_summary?.continuing_margin_impact || 0;
});
const newImpact = computed(() => {
  return metricsData.value?.summary?.margin_change_summary?.new_impact || 0;
});
const exitImpact = computed(() => {
  return metricsData.value?.summary?.margin_change_summary?.exit_impact || 0;
});

const marginAnalysisColumns = [
  { title: '分类', key: 'category', width: 100 },
  { title: '维度值', dataIndex: 'dimension_value', key: 'dimension_value', width: 180 },
  { title: '当期收入', dataIndex: 'current_revenue', key: 'current_revenue', width: 120 },
  { title: '基期收入', dataIndex: 'base_revenue', key: 'base_revenue', width: 120 },
  { title: '当期毛利率', dataIndex: 'current_margin', key: 'current_margin', width: 120 },
  { title: '基期毛利率', dataIndex: 'base_margin', key: 'base_margin', width: 120 },
  { title: '结构影响', dataIndex: 'structure_impact', key: 'structure_impact', width: 120 },
  { title: '毛利影响', dataIndex: 'margin_impact', key: 'margin_impact', width: 120 },
  { title: '总影响', dataIndex: 'total_impact', key: 'total_impact', width: 120 },
];

function categoryLabel(category: string): string {
  if (category === 'continuing') return '存续';
  if (category === 'new') return '新增';
  if (category === 'exit') return '退出';
  return category;
}

// Top impacts for revenue/profit changes (explain 80% of change)
const revenueTopImpacts = computed(() => {
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
  period_start: periodStart.value,
  period_end: periodEnd.value,
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
      compare: compareBase.value,
      compare_period: basePeriod.value,
      period_start: periodStart.value,
      period_end: periodEnd.value,
    });
    metricsData.value = resp.data as CoreMetricsResponse;

    // Fetch base period data for comparison
    if (basePeriod.value) {
      const { data: baseResp } = await getCoreMetrics({
        period: basePeriod.value,
        dimension: dimension.value,
        entity: dimension.value !== 'company' ? selectedEntity.value : undefined,
        period_dimension: periodDimension.value,
        compare: compareBase.value,
        period_start: periodStart.value,
        period_end: periodEnd.value,
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
    selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
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

watch([periodDimension, selectedPeriod, dimension, periodStart, periodEnd], async () => {
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

// Change card styles
.change-card {
  padding: 12px;
  background: var(--color-bg-layout);
  border-radius: 8px;
  .change-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: 4px;
  }
  .change-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--color-text);
    margin-bottom: 4px;
    .change-amount {
      font-size: 18px;
    }
  }
  .change-rate {
    font-size: 14px;
    font-weight: 600;
    &.up { color: #f5222d; }
    &.down { color: #52c41a; }
  }
}

@media (max-width: 1023px) {
  .page-content {
    display: flex;
    flex-direction: column;
  }
}
</style>
