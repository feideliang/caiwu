<template>
  <div class="financial-overview">
    <!-- Section 1: Overview / KPI Cards -->
    <a-row :gutter="[16, 16]" class="kpi-row">
      <a-col :xs="12" :sm="12" :md="6" v-for="kpi in kpiCards" :key="kpi.title">
        <KpiCard
          :title="kpi.title"
          :value="kpi.value"
          :unit="kpi.unit"
          :precision="kpi.precision"
          :trend="kpi.trend"
          :trend-suffix="kpi.trendSuffix"
          :trend-label="kpi.trendLabel"
          :icon="kpi.icon"
        />
      </a-col>
    </a-row>

    <!-- Core Metrics Panel -->
    <CoreMetricsPanel
      :period="period"
      :dimension="department ? 'department' : product ? 'product_bgbu' : 'company'"
      :entity="department || product"
      :period-dimension="periodDimension"
      :product="product"
      :department="department"
    />

    <!-- Section 2: Trends -->
    <a-divider orientation="left">
      <a-space>
        <span>趋势</span>
        <a-select
          v-model:value="dataCaliber"
          size="small"
          :style="{ width: '90px' }"
          @click.stop
        >
          <a-select-option value="absolute">绝对值</a-select-option>
          <a-select-option value="yoy">同比</a-select-option>
          <a-select-option value="mom">环比</a-select-option>
        </a-select>
      </a-space>
    </a-divider>
    <a-row :gutter="[16, 16]" class="chart-row">
      <a-col :xs="24" :md="16">
        <ChartWidget
          :title="trendTitle"
          :data="trendData"
          :chart-type="appliedChartType"
          :loading="loading"
          :show-extra="true"
          :value-suffix="dataCaliber === 'absolute' ? '万元' : '%'"
          @refresh="fetchData"
        />
      </a-col>
      <a-col :xs="24" :md="8">
        <AIChartRecommender
          data-type="time_series"
          :data-sample="trendData"
          @apply="onApplyRecommendation"
        />
      </a-col>
    </a-row>

    <!-- Insights -->
    <a-divider orientation="left">智能洞察</a-divider>
    <InsightCard :max-count="5" />

    <!-- Calculation Rules -->
    <a-collapse :bordered="false" class="calc-rules-section">
      <a-collapse-panel header="计算规则说明" key="rules">
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item label="同比 (YoY)">
            (当期值 - 去年同期值) / 去年同期值 x 100%<br />
            例：2026年3月同比 = (2026-03值 - 2025-03值) / 2025-03值
          </a-descriptions-item>
          <a-descriptions-item label="环比 (MoM)">
            (当期值 - 上期值) / 上期值 x 100%<br />
            例：2026年3月环比 = (2026-03值 - 2026-02值) / 2026-02值
          </a-descriptions-item>
          <a-descriptions-item label="毛利率">
            毛利额 / 营业收入 x 100%
          </a-descriptions-item>
          <a-descriptions-item label="同比变动(百分点)">
            当期毛利率 - 去年同期毛利率（单位：百分点）
          </a-descriptions-item>
          <a-descriptions-item label="年累计">
            当年1月至当前期间的所有月度数据求和
          </a-descriptions-item>
          <a-descriptions-item label="筛选影响">
            选择市场线后，所有指标（含同比/环比的分母）均仅基于该市场线的数据计算，确保对比口径一致。选择产品线时同理。未选择筛选条件时使用公司整体数据（bgbu=ALL）。
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { Component } from 'vue';
import {
  DollarOutlined,
  FallOutlined,
  RiseOutlined,
  PercentageOutlined,
} from '@ant-design/icons-vue';
import KpiCard from './KpiCard.vue';
import ChartWidget from './ChartWidget.vue';
import InsightCard from './InsightCard.vue';
import CoreMetricsPanel from './CoreMetricsPanel.vue';
import AIChartRecommender from '@/components/ai/AIChartRecommender.vue';
import { useInsightsStore } from '@/store/insights';
import { queryDashboard, type DashboardBff } from '@/api/dashboard';
import { toWan } from '@/utils/format';

const props = defineProps<{
  period?: string;
  periodCompareType?: 'yoy' | 'mom' | 'cumulative';
  periodDimension?: string;
  periodStart?: string;
  periodEnd?: string;
  department?: string;
  product?: string;
}>();

interface KpiCardItem {
  title: string;
  value: number;
  unit: string;
  precision: number;
  trend?: number;
  trendSuffix?: string;
  trendLabel?: string;
  icon: Component;
}

const loading = ref(false);
const appliedChartType = ref('line');
const dashboardData = ref<DashboardBff | null>(null);
const insightsStore = useInsightsStore();
const dataCaliber = ref<'absolute' | 'yoy' | 'mom'>('absolute');

const kpiCards = computed<KpiCardItem[]>(() => {
  const kpis = dashboardData.value?.kpis;
  if (!kpis) {
    return [
      { title: '营业收入', value: 0, unit: '', precision: 0, icon: DollarOutlined },
      { title: '营业成本', value: 0, unit: '', precision: 0, icon: FallOutlined },
      { title: '毛利额', value: 0, unit: '', precision: 0, icon: RiseOutlined },
      { title: '毛利率', value: 0, unit: '%', precision: 2, icon: PercentageOutlined },
    ];
  }
  return [
    { title: '营业收入', value: toWan(kpis.revenue), unit: '万元', precision: 0, trend: kpis.revenue_yoy_growth, trendLabel: '同比', icon: DollarOutlined },
    { title: '营业成本', value: toWan(kpis.cost), unit: '万元', precision: 0, trend: kpis.cost_yoy_growth, trendLabel: '同比', icon: FallOutlined },
    { title: '毛利额', value: toWan(kpis.gross_profit), unit: '万元', precision: 0, trend: kpis.profit_yoy_growth, trendLabel: '同比', icon: RiseOutlined },
    { title: '毛利率', value: kpis.gross_margin, unit: '%', precision: 2, trend: kpis.gross_margin_yoy_change, trendSuffix: '个百分点', trendLabel: '同比', icon: PercentageOutlined },
  ];
});

const trendData = computed(() => {
  const series = dashboardData.value?.kpis?.trend_series;
  if (series && series.length > 0) {
    return series.map((item: {
      period: string; revenue: number; cost: number; gross_profit: number; gross_margin: number;
      revenue_yoy_growth?: number; revenue_mom_growth?: number;
      gross_profit_yoy_growth?: number; gross_profit_mom_growth?: number;
      gross_margin_yoy_growth?: number; gross_margin_mom_growth?: number;
      gross_margin_yoy_change?: number; gross_margin_mom_change?: number;
      order_count?: number; order_count_yoy_growth?: number; order_count_mom_growth?: number;
    }) => {
      const rev = dataCaliber.value === 'yoy' ? (item.revenue_yoy_growth || 0)
        : dataCaliber.value === 'mom' ? (item.revenue_mom_growth || 0)
        : item.revenue;
      const cost = dataCaliber.value === 'yoy' ? 0  // cost YoY not included in series
        : dataCaliber.value === 'mom' ? 0
        : item.cost;
      const gp = dataCaliber.value === 'yoy' ? (item.gross_profit_yoy_growth || 0)
        : dataCaliber.value === 'mom' ? (item.gross_profit_mom_growth || 0)
        : item.gross_profit;
      const gm = dataCaliber.value === 'yoy' ? (item.gross_margin_yoy_change || 0)
        : dataCaliber.value === 'mom' ? (item.gross_margin_mom_change || 0)
        : item.gross_margin;
      return {
        period: item.period,
        revenue: rev,
        cost,
        gross_profit: gp,
        gross_margin: gm,
      };
    });
  }
  if (dashboardData.value?.charts?.length) {
    const trendChart = dashboardData.value.charts.find((c) => c.type === 'line') || dashboardData.value.charts[0];
    return trendChart.data || [];
  }
  return [];
});

const trendTitle = computed(() => {
  switch (props.periodDimension) {
    case 'quarterly': return '季度趋势';
    case 'cumulative': return '累计趋势';
    case 'custom': return '趋势';
    default: return '月度趋势';
  }
});

async function fetchData() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = { period_compare_type: 'yoy' };
    if (props.period) params.period = props.period;
    if (props.periodDimension) params.period_dimension = props.periodDimension;
    if (props.periodStart) params.period_start = props.periodStart;
    if (props.periodEnd) params.period_end = props.periodEnd;
    if (props.department) params.department = props.department;
    if (props.product) params.product = props.product;
    const { data } = await queryDashboard(params);
    dashboardData.value = data.data;
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false;
  }
}

let _mounted = false;

watch(() => [props.period, props.periodDimension, props.periodStart, props.periodEnd, props.department, props.product], () => {
  if (!_mounted) return;
  fetchData();
});

onMounted(async () => {
  await Promise.all([
    fetchData(),
    insightsStore.fetchInsights(),
  ]);
  _mounted = true;
});

function onApplyRecommendation(chartType: string, _config: Record<string, unknown>) {
  appliedChartType.value = chartType;
}
</script>

<style scoped lang="less">
.financial-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kpi-row {
  margin-bottom: 0;
}

:deep(.ant-divider-inner-text) {
  font-size: 16px;
  font-weight: 600;
}

.calc-rules-section {
  margin-top: 8px;

  :deep(.ant-collapse-header) {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  :deep(.ant-descriptions-item-label) {
    font-weight: 600;
    width: 140px;
  }

  :deep(.ant-descriptions-item-content) {
    font-size: 13px;
    color: var(--color-text-secondary);
  }
}
</style>
