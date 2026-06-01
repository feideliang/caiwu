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
            <!-- Compare period selector (only for custom_compare) -->
            <template v-if="compareBase === 'custom_compare'">
              <a-range-picker
                v-if="periodDimension === 'custom'"
                v-model:value="compareRange"
                picker="month"
                :allow-clear="true"
                style="width: 280px"
                format="YYYY年M月"
                @change="onCompareRangeChange"
              />
              <a-select
                v-else
                v-model:value="comparePeriod"
                :options="periodSelectOptions"
                style="width: 160px"
                placeholder="基期期间"
                allow-clear
              />
            </template>
            <!-- Dimension selector -->
            <a-select v-model:value="dimension" :options="dimensionOptions" style="width: 140px" placeholder="维度" />
            <!-- Entity selector -->
            <a-select v-if="dimension !== 'company' && !(dimension === 'department' && authStore.isDeptRestricted)" v-model:value="selectedEntity" :options="entityOptions" style="width: 180px" placeholder="实体" allow-clear />
            <a-tag v-if="dimension === 'department' && authStore.isDeptRestricted" color="blue">{{ authStore.department }}</a-tag>
            <!-- Show active department scope filter -->
            <a-tag v-if="departmentScope && dimension !== 'department' && dimension !== 'company'" color="orange" closable @close="departmentScope = undefined">部门: {{ departmentScope }}</a-tag>
            <!-- Cross-dimension selector -->
            <a-select v-if="crossDimensionOptions.length" v-model:value="crossDimension" :options="crossDimensionOptions" style="width: 140px" placeholder="交叉维度" allow-clear />
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
              <KpiCard title="当期收入" :value="toWan(metricsData?.summary?.revenue)" unit="万元" :precision="0"
                :trend="revenueChangeRate" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="基期收入" :value="toWan(basePeriodData?.summary?.revenue)" unit="万元" :precision="0"
                :trend="baseRevenueTrend" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="收入变化" :value="toWan(revenueChangeValue)" unit="万元" :precision="0"
                :trend="revenueChangeRate" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <div class="impact-box">
                <div class="impact-title">主要变动影响</div>
                <div v-for="item in revenueTopImpactPage" :key="item.name" class="impact-item">
                  <span class="impact-name">{{ item.name }}</span>
                  <span class="impact-value">{{ item.change >= 0 ? '+' : '' }}{{ item.change.toFixed(0) }}万</span>
                  <span class="impact-pct">影响度{{ item.pct }}%</span>
                </div>
                <div v-if="!revenueTopImpacts.length" class="impact-empty">暂无数据</div>
                <a-pagination v-if="revenueImpactPageCount > 1" simple size="small" :total="revenueTopImpacts.length" :page-size="10" :current="revenueImpactPageNum" @change="revenueImpactPageNum = $event" class="impact-pager" />
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- Gross profit change -->
        <a-card title="毛利额变动" size="small" class="section-card">
          <a-row :gutter="[16, 16]">
            <a-col :span="6">
              <KpiCard title="当期毛利额" :value="toWan(metricsData?.summary?.gross_profit)" unit="万元" :precision="0"
                :trend="profitChangeRate" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="基期毛利额" :value="toWan(basePeriodData?.summary?.gross_profit)" unit="万元" :precision="0"
                :trend="baseProfitTrend" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="毛利额变化" :value="toWan(profitChangeValue)" unit="万元" :precision="0"
                :trend="profitChangeRate" trendSuffix="%" />
            </a-col>
            <a-col :span="6">
              <div class="impact-box">
                <div class="impact-title">主要变动影响</div>
                <div v-for="item in profitTopImpactPage" :key="item.name" class="impact-item">
                  <span class="impact-name">{{ item.name }}</span>
                  <span class="impact-value">{{ item.change >= 0 ? '+' : '' }}{{ item.change.toFixed(0) }}万</span>
                  <span class="impact-pct">影响度{{ item.pct }}%</span>
                </div>
                <div v-if="!profitTopImpacts.length" class="impact-empty">暂无数据</div>
                <a-pagination v-if="profitImpactPageCount > 1" simple size="small" :total="profitTopImpacts.length" :page-size="10" :current="profitImpactPageNum" @change="profitImpactPageNum = $event" class="impact-pager" />
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- Margin change - overview + 4-factor decomposition -->
        <a-card title="毛利率变动" size="small" class="section-card">
          <a-row :gutter="[16, 16]" style="margin-bottom: 16px">
            <a-col :span="8">
              <KpiCard title="当期毛利率" :value="metricsData?.summary?.gross_margin || 0" unit="%" :precision="2" />
            </a-col>
            <a-col :span="8">
              <KpiCard title="基期毛利率" :value="basePeriodData?.summary?.gross_margin || 0" unit="%" :precision="2" />
            </a-col>
            <a-col :span="8">
              <KpiCard title="毛利率变化" :value="marginChangeValue" unit="pp" :precision="2" />
            </a-col>
          </a-row>
          <a-divider style="margin: 0 0 16px 0" />
          <a-row :gutter="[16, 16]">
            <a-col :span="6">
              <KpiCard title="存续结构影响" :value="continuingStructureImpact" unit="pp" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="存续毛利影响" :value="continuingMarginImpact" unit="pp" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="新增影响" :value="newImpact" unit="pp" :precision="2" />
            </a-col>
            <a-col :span="6">
              <KpiCard title="退出影响" :value="exitImpact" unit="pp" :precision="2" />
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
            <template #headerCell="{ column }">
              <a-tooltip v-if="(column as any).tooltip" :title="(column as any).tooltip">{{ (column as any).title }}</a-tooltip>
            </template>
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'category'">
                {{ categoryLabel((record as any).category) }}
              </template>
              <template v-if="column.key === 'current_revenue' || column.key === 'base_revenue'">
                {{ formatWan((record as any)[column.key]) }}万元
              </template>
              <template v-if="column.key === 'current_margin' || column.key === 'base_margin'">
                {{ formatPercent((record as any)[column.key]) }}
              </template>
              <template v-else-if="column.key === 'current_share' || column.key === 'base_share'">
                {{ formatPercent((record as any)[column.key]) }}
              </template>
              <template v-else-if="column.key === 'share_change' || column.key === 'margin_change'">
                <span :class="getImpactClass((record as any)[column.key])">{{ formatSignedPp((record as any)[column.key]) }}</span>
              </template>
              <template v-else-if="column.key === 'structure_impact' || column.key === 'margin_impact' || column.key === 'total_impact'">
                <span :class="getImpactClass((record as any)[column.key])">{{ formatSignedPp((record as any)[column.key]) }}</span>
              </template>
            </template>
          </a-table>
        </a-card>

        <!-- Concentration ranking -->
        <ConcentrationPanel :breakdowns="metricsData?.breakdowns || []" :dimension="dimension" :customers="metricsData?.customer_breakdown || []" />

        <!-- Cross-dimension analysis -->
        <CrossDimensionChart
          v-if="crossDimension"
          :cross-dimension="crossDimension"
          :primary-dimension="dimension"
          :primary-entity="selectedEntity || ''"
          :period="period || ''"
          :period-start="periodStart"
          :period-end="periodEnd"
          :period-dimension="periodDimension"
          :compare-base="compareBase"
        />

        <!-- Calculation Rules -->
        <a-collapse :bordered="false" class="calc-rules-section">
          <a-collapse-panel header="计算规则说明" key="rules">
            <a-descriptions :column="1" size="small" bordered>
              <a-descriptions-item label="同比 (YoY)">
                (当期值 - 去年同期值) / 去年同期值 x 100%<br />
                月度: 2026-03同比 = vs 2025-03; 季度: 2026-Q1同比 = vs 2025-Q1; 年累计: 2026年累计 = vs 2025年同期累计
              </a-descriptions-item>
              <a-descriptions-item label="环比 (MoM)">
                (当期值 - 上期值) / 上期值 x 100%<br />
                月度: 2026-03环比 = vs 2026-02; 季度: 2026-Q1环比 = vs 2025-Q4
              </a-descriptions-item>
              <a-descriptions-item label="毛利率">
                毛利额 / 营业收入 x 100%
              </a-descriptions-item>
              <a-descriptions-item label="毛利率变动拆解">
                存续结构影响 = 存续业务占比变化 x (存续毛利率 - 基期整体毛利率)<br />
                存续毛利影响 = 基期占比 x (当期毛利率 - 基期毛利率)<br />
                新增影响 = 新增业务的收入占比 x 毛利率<br />
                退出影响 = 退出业务对基期的拖累
              </a-descriptions-item>
              <a-descriptions-item label="筛选影响">
                选择部门/市场线后，所有指标（含同比/环比的基数）均仅基于该部门数据计算，确保对比口径一致。选择产品线或客户时同理。维度切换不影响筛选范围。
              </a-descriptions-item>
              <a-descriptions-item label="客户集中度 Top3/Top10">
                当期收入最高的前3（或前10）个客户的收入之和 ÷ 当期全部客户收入总和 × 100%。<br />
                <strong>例：</strong>前3名客户分别贡献 500万、300万、200万，全部客户收入合计 1200万 → 集中度 = (500+300+200) ÷ 1200 × 100% = 83.33%。<br />
                分子分母取自同一数据源（客户维度汇总表），确保口径一致。若部分客户存在退货/冲减（负收入），分母会小于正收入之和，集中度可能接近但不超过100%。
              </a-descriptions-item>
              <a-descriptions-item label="产品集中度 Top3/Top10">
                当期毛利最高的前3（或前10）个产品的毛利之和 ÷ 当期全部产品毛利总和 × 100%。<br />
                <strong>例：</strong>前3名产品毛利分别为 400万、300万、200万，全部产品毛利合计 1000万 → 集中度 = (400+300+200) ÷ 1000 × 100% = 90.00%。<br />
                若部分产品出现亏损（负毛利），分母会小于正毛利之和，集中度可能接近但不超过100%。
              </a-descriptions-item>
              <a-descriptions-item label="高毛利订单占比">
                当期毛利率超过阈值（默认40%）的订单数 ÷ 当期有收入的订单总数 × 100%。<br />
                <strong>例：</strong>当月共200笔有收入订单，其中120笔毛利率 &gt; 40% → 高毛利订单占比 = 120 ÷ 200 × 100% = 60.00%。<br />
                注意：这是订单数量比，不是金额比。单笔订单毛利率 = (收入 - 成本) ÷ 收入 × 100%。
              </a-descriptions-item>
            </a-descriptions>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <div v-if="showAssistant" class="assistant-area">
        <FinancialAssistantPanel :context="assistantContext" :recommendations="recommendations" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store/auth';
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import KpiCard from '@/components/dashboard/KpiCard.vue';
import ConcentrationPanel from '@/components/dashboard/ConcentrationPanel.vue';
import CrossDimensionChart from '@/components/dashboard/CrossDimensionChart.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getCoreMetrics } from '@/api/metrics';
import { getFilterOptions } from '@/api/filters';
import { getAnalysisRecommendations } from '@/api/ai';
import type { AnalysisRecommendations } from '@/types/analysis';
import type { CoreMetricsResponse } from '@/types/metrics';
import { formatPercent, formatPp, formatWan, toWan } from '@/utils/format';
import { buildPeriodOptions, formatMonthValue, getComparePeriod, getDefaultPeriod, normalizePeriodDimension } from '@/utils/period';

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
const comparePeriod = ref<string | undefined>();  // custom compare period (single)
const compareRange = ref<[any, any] | null>(null);
const comparePeriodStart = ref<string | undefined>();
const comparePeriodEnd = ref<string | undefined>();
const dimension = ref<string>('customer');
const selectedEntity = ref<string | undefined>();
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const allPeriods = ref<string[]>([]);
const entityOptions = ref<Array<{ label: string; value: string }>>([]);

// Cross-dimension analysis
const crossDimension = ref<string>('');

// Track department scope: when user selects a department entity, preserve it
// for cross-dimension analysis (e.g., 部门=CBG → switch to 客户, still scope to CBG)
const departmentScope = ref<string | undefined>();

const dimensionOptions = [
  { label: '客户', value: 'customer' },
  { label: '产品线', value: 'product_line' },
  { label: '部门', value: 'department' },
  { label: '公司整体', value: 'company' },
];

const crossDimensionOptions = computed<Array<{ label: string; value: string }>>(() => {
  if (dimension.value === 'company' || !selectedEntity.value) return [];
  const all = [
    { label: '客户', value: 'customer' },
    { label: '产品线', value: 'product_line' },
    { label: '部门', value: 'department' },
  ];
  return all.filter((o) => o.value !== dimension.value);
});

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

function onCompareRangeChange(dates: any) {
  if (dates && dates[0] && dates[1]) {
    comparePeriodStart.value = formatMonthValue(dates[0]);
    comparePeriodEnd.value = formatMonthValue(dates[1]);
  } else {
    comparePeriodStart.value = undefined;
    comparePeriodEnd.value = undefined;
  }
}

// Auto-select first period when dimension changes
watch(periodDimension, () => {
  selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

// Clear compare period when switching away from custom_compare
watch(compareBase, (val) => {
  if (val !== 'custom_compare') {
    comparePeriod.value = undefined;
    compareRange.value = null;
    comparePeriodStart.value = undefined;
    comparePeriodEnd.value = undefined;
  }
});

// Reset cross-dimension when primary dimension changes
watch([dimension, selectedEntity], ([newDim, newEntity], [oldDim, oldEntity]) => {
  crossDimension.value = '';
  // Preserve department scope when leaving department dimension
  if (oldDim === 'department' && newDim !== 'department' && oldEntity) {
    departmentScope.value = oldEntity;
  }
  // Set department scope when entity selected on department dimension
  if (newDim === 'department' && newEntity) {
    departmentScope.value = newEntity;
  }
  // Clear when switching to company
  if (newDim === 'company') {
    departmentScope.value = undefined;
  }
}, { immediate: false });

// Data
const metricsData = ref<CoreMetricsResponse | null>(null);
const basePeriodData = ref<CoreMetricsResponse | null>(null);
const loading = ref(false);
let fetchKey = 0;

// Compute base period for comparison
const basePeriod = computed(() => {
  if (compareBase.value === 'custom_compare') {
    if (periodDimension.value === 'custom') return undefined;  // uses comparePeriodStart/End
    return comparePeriod.value;
  }
  return getComparePeriod(period.value, compareBase.value, normalizePeriodDimension(periodDimension.value));
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

const baseRevenueTrend = computed(() => {
  return compareBase.value === 'mom'
    ? (basePeriodData.value?.summary?.revenue_mom_growth ?? undefined)
    : (basePeriodData.value?.summary?.revenue_yoy_growth ?? undefined);
});

const baseProfitTrend = computed(() => {
  return compareBase.value === 'mom'
    ? (basePeriodData.value?.summary?.gross_profit_mom_growth ?? undefined)
    : (basePeriodData.value?.summary?.gross_profit_yoy_growth ?? undefined);
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

const marginChangeValue = computed(() => {
  const curr = metricsData.value?.summary?.gross_margin;
  const base = basePeriodData.value?.summary?.gross_margin;
  if (curr == null || base == null) return 0;
  const rawDiff = curr - base;

  // Cross-check: sum of total_impact from breakdown should match overall margin change
  const breakdown = metricsData.value?.summary?.margin_change_analysis || [];
  if (breakdown.length > 0) {
    const summedImpact = breakdown.reduce(
      (sum, r: any) => sum + ((r.total_impact as number) || 0),
      0,
    );
    const delta = rawDiff - summedImpact;
    // If difference exceeds 0.01pp, float the display to match the summed breakdown
    if (Math.abs(delta) > 0.01) {
      return summedImpact;
    }
  }
  return rawDiff;
});

const columnTooltips: Record<string, string> = {
  current_margin: '当期该维度值的毛利率 = 毛利额 / 收入 × 100%',
  base_margin: '基期该维度值的毛利率 = 基期毛利额 / 基期收入 × 100%',
  margin_change: '毛利率变化 = 当期毛利率 - 基期毛利率（单位：pp）',
  structure_impact: '结构影响 = (当期收入占比 - 基期收入占比) × (存续毛利率 - 基期整体毛利率)',
  margin_impact: '毛利影响 = 基期收入占比 × (当期毛利率 - 基期毛利率)',
  total_impact: '总影响 = 结构影响 + 毛利影响（反映该维度对整体毛利率变动的贡献）',
};

const marginAnalysisColumns = [
  { title: '分类', key: 'category', width: 100 },
  { title: '维度值', dataIndex: 'dimension_value', key: 'dimension_value', width: 180 },
  { title: '当期收入', dataIndex: 'current_revenue', key: 'current_revenue', width: 120 },
  { title: '基期收入', dataIndex: 'base_revenue', key: 'base_revenue', width: 120 },
  { title: '当期收入占比', dataIndex: 'current_share', key: 'current_share', width: 120 },
  { title: '基期收入占比', dataIndex: 'base_share', key: 'base_share', width: 120 },
  { title: '收入占比变化', dataIndex: 'share_change', key: 'share_change', width: 120 },
  { title: '当期毛利率', dataIndex: 'current_margin', key: 'current_margin', width: 120, tooltip: columnTooltips.current_margin },
  { title: '基期毛利率', dataIndex: 'base_margin', key: 'base_margin', width: 120, tooltip: columnTooltips.base_margin },
  { title: '毛利率变化', dataIndex: 'margin_change', key: 'margin_change', width: 120, tooltip: columnTooltips.margin_change },
  { title: '结构影响', dataIndex: 'structure_impact', key: 'structure_impact', width: 120, tooltip: columnTooltips.structure_impact },
  { title: '毛利影响', dataIndex: 'margin_impact', key: 'margin_impact', width: 120, tooltip: columnTooltips.margin_impact },
  { title: '总影响', dataIndex: 'total_impact', key: 'total_impact', width: 120, tooltip: columnTooltips.total_impact },
];

function categoryLabel(category: string): string {
  if (category === 'continuing') return '存续';
  if (category === 'new') return '新增';
  if (category === 'exit') return '退出';
  return category;
}

function formatSignedPp(value: number | string | undefined | null): string {
  const formatted = formatPp(value);
  if (formatted === '-') return formatted;
  const numeric = typeof value === 'number' ? value : Number(value);
  if (Number.isFinite(numeric) && numeric > 0) return `+${formatted}`;
  return formatted;
}

function getImpactClass(value: number | string | undefined | null): string {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return '';
  return numeric >= 0 ? 'text-success' : 'text-error';
}

// Top impacts for revenue/profit changes (explain 80% of change)
function computeTopImpacts(
  breakdowns: { dimension_value: string; revenue?: number; gross_profit?: number }[],
  baseBreakdowns: { dimension_value: string; revenue?: number; gross_profit?: number }[],
  _currTotal: number,
  _baseTotal: number,
  valueKey: 'revenue' | 'gross_profit',
): { name: string; change: number; pct: number }[] {
  if (!breakdowns.length) return [];

  const impacts = breakdowns.map((b) => {
    const baseItem = baseBreakdowns.find((bb) => bb.dimension_value === b.dimension_value);
    const change = (b[valueKey] || 0) - (baseItem?.[valueKey] || 0);
    return {
      name: b.dimension_value,
      change: change / 10000,
      absChange: Math.abs(change),
    };
  }).filter((i) => i.absChange > 0).sort((a, b) => b.absChange - a.absChange);

  if (!impacts.length) return [];

  // Use breakdown-level total change as denominator, not summary total
  const breakdownTotalChange = impacts.reduce((s, i) => s + i.absChange, 0);
  if (breakdownTotalChange === 0) return [];

  const withPct = impacts.map((i) => ({
    name: i.name,
    change: i.change,
    pct: Math.round((i.absChange / breakdownTotalChange) * 100),
  }));

  let cumPct = 0;
  return withPct.filter((i) => { cumPct += i.pct; return cumPct <= 100 || i === withPct[0]; });
}

const revenueTopImpacts = computed(() => {
  const useContractType = dimension.value === 'customer' && (metricsData.value?.contract_type_breakdown?.length || 0) > 0;
  const breakdowns = useContractType
    ? metricsData.value?.contract_type_breakdown || []
    : metricsData.value?.breakdowns || [];
  const baseBreakdowns = useContractType
    ? basePeriodData.value?.contract_type_breakdown || []
    : basePeriodData.value?.breakdowns || [];
  const currTotal = metricsData.value?.summary?.revenue || 0;
  const baseTotal = basePeriodData.value?.summary?.revenue || 0;
  return computeTopImpacts(breakdowns, baseBreakdowns, currTotal, baseTotal, 'revenue');
});

const profitTopImpacts = computed(() => {
  const useContractType = dimension.value === 'customer' && (metricsData.value?.contract_type_breakdown?.length || 0) > 0;
  const breakdowns = useContractType
    ? metricsData.value?.contract_type_breakdown || []
    : metricsData.value?.breakdowns || [];
  const baseBreakdowns = useContractType
    ? basePeriodData.value?.contract_type_breakdown || []
    : basePeriodData.value?.breakdowns || [];
  const currTotal = metricsData.value?.summary?.gross_profit || 0;
  const baseTotal = basePeriodData.value?.summary?.gross_profit || 0;
  return computeTopImpacts(breakdowns, baseBreakdowns, currTotal, baseTotal, 'gross_profit');
});

// Pagination for impact lists
const IMPACT_PAGE_SIZE = 10;
const revenueImpactPageNum = ref(1);
const profitImpactPageNum = ref(1);

// Reset page on dimension/entity change
watch([dimension, selectedEntity], () => {
  revenueImpactPageNum.value = 1;
  profitImpactPageNum.value = 1;
});

const revenueImpactPageCount = computed(() => Math.ceil((revenueTopImpacts.value.length || 0) / IMPACT_PAGE_SIZE));
const profitImpactPageCount = computed(() => Math.ceil((profitTopImpacts.value.length || 0) / IMPACT_PAGE_SIZE));

const revenueTopImpactPage = computed(() => {
  const s = (revenueImpactPageNum.value - 1) * IMPACT_PAGE_SIZE;
  return revenueTopImpacts.value.slice(s, s + IMPACT_PAGE_SIZE);
});

const profitTopImpactPage = computed(() => {
  const s = (profitImpactPageNum.value - 1) * IMPACT_PAGE_SIZE;
  return profitTopImpacts.value.slice(s, s + IMPACT_PAGE_SIZE);
});

const assistantContext = computed(() => ({
  period: period.value,
  dimension: dimension.value,
  period_dimension: periodDimension.value,
  period_start: periodStart.value,
  period_end: periodEnd.value,
  active_section: 'change_analysis',
}));

const recommendations = ref<AnalysisRecommendations>();

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'core_metrics',
      period: period.value,
      period_compare_type: compareBase.value,
    });
    recommendations.value = data.data || undefined;
  } catch { /* non-critical */ }
}

async function fetchMetrics() {
  basePeriodData.value = null;
  const key = fetchKey;
  loading.value = true;
  try {
    // Pass department scope for filtering:
    // departmentScope always holds the current department filter (set by watch1 when entity selected)
    const deptParam = departmentScope.value;
    const effectiveDim = crossDimension.value || dimension.value;
    const entityParam = effectiveDim !== 'company' && !crossDimension.value ? selectedEntity.value : undefined;
    const { data: resp } = await getCoreMetrics({
      period: period.value,
      dimension: effectiveDim,
      entity: entityParam,
      department: deptParam,
      period_dimension: periodDimension.value,
      compare: compareBase.value,
      compare_period: basePeriod.value,
      period_start: periodStart.value,
      period_end: periodEnd.value,
    });
    if (key !== fetchKey) return; // stale request, discard
    metricsData.value = resp.data as CoreMetricsResponse;

    // Fetch base period data for comparison
    const hasBasePeriod = basePeriod.value || (compareBase.value === 'custom_compare' && comparePeriodStart.value && comparePeriodEnd.value);
    if (hasBasePeriod) {
      const basePeriodVal = basePeriod.value;
      const isCustomCompareRange = compareBase.value === 'custom_compare' && periodDimension.value === 'custom';
      const { data: baseResp } = await getCoreMetrics({
        period: isCustomCompareRange ? undefined : basePeriodVal,
        dimension: effectiveDim,
        entity: entityParam,
        department: deptParam,
        period_dimension: periodDimension.value,
        compare: 'all',
        period_start: isCustomCompareRange ? comparePeriodStart.value : periodStart.value,
        period_end: isCustomCompareRange ? comparePeriodEnd.value : periodEnd.value,
      });
      if (key !== fetchKey) return; // stale request, discard
      basePeriodData.value = baseResp.data as CoreMetricsResponse;
    } else {
      basePeriodData.value = null;
    }
  } catch {
    if (key !== fetchKey) return;
    // Don't null out metricsData if only base period fetch failed
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
  const params: Record<string, unknown> = { dimension: dimension.value };
  // Filter entity options by current department scope
  if (departmentScope.value) {
    params.department = departmentScope.value;
  }
  const { data: resp } = await getFilterOptions(params);
  const opts = ((resp.data as any)?.options || []) as string[];
  entityOptions.value = opts.map((v) => ({ label: v, value: v }));
  selectedEntity.value = undefined;
}

function refresh() { fetchKey++; fetchMetrics(); }

let _oldDim: string | undefined;
let _oldCompare: string | undefined;
watch([periodDimension, selectedPeriod, dimension, periodStart, periodEnd, selectedEntity, compareBase, comparePeriod, comparePeriodStart, comparePeriodEnd, crossDimension], async ([, newSP, newDim, , , , newCompare]) => {
  if (!newSP) return;
  if (_oldDim !== newDim || _oldCompare !== newCompare) {
    await loadEntityOptions();
    _oldDim = newDim;
    _oldCompare = newCompare;
  }
  fetchKey++;
  fetchMetrics();
  loadRecommendations();
}, { immediate: true });

// Department scope cleared externally (e.g., user closes orange tag) → refetch
watch(departmentScope, (newVal, oldVal) => {
  if (!selectedPeriod.value) return;
  if (newVal === undefined && oldVal !== undefined) {
    fetchKey++;
    fetchMetrics();
    loadRecommendations();
  }
});

onMounted(async () => { await fetchOptions(); loadRecommendations(); });
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
  .impact-pager {
    margin-top: 8px;
  }
}

.text-success { color: #52c41a; }
.text-error { color: #ff4d4f; }

.calc-rules-section {
  margin-top: 16px;

  :deep(.ant-collapse-header) {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  :deep(.ant-descriptions-item-label) {
    font-weight: 600;
    width: 160px;
  }

  :deep(.ant-descriptions-item-content) {
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
