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
          :icon="kpi.icon"
        />
      </a-col>
    </a-row>

    <!-- Core Metrics Panel -->
    <CoreMetricsPanel
      :period="period"
      :dimension="department ? 'department' : product ? 'product_line' : 'company'"
      :entity="department || product"
      :period-dimension="periodDimension"
    />

    <!-- Section 2: Trends -->
    <a-divider orientation="left">趋势</a-divider>
    <a-row :gutter="[16, 16]" class="chart-row">
      <a-col :xs="24" :md="16">
        <ChartWidget
          title="月度趋势"
          :data="trendData"
          :chart-type="appliedChartType"
          :loading="loading"
          :show-extra="true"
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
  icon: Component;
}

const loading = ref(false);
const appliedChartType = ref('line');
const dashboardData = ref<DashboardBff | null>(null);
const insightsStore = useInsightsStore();

const kpiCards = computed<KpiCardItem[]>(() => {
  const kpis = dashboardData.value?.kpis;
  if (!kpis) {
    return [
      { title: '营业收入', value: 0, unit: '', precision: 2, icon: DollarOutlined },
      { title: '营业成本', value: 0, unit: '', precision: 2, icon: FallOutlined },
      { title: '毛利额', value: 0, unit: '', precision: 2, icon: RiseOutlined },
      { title: '毛利率', value: 0, unit: '%', precision: 2, icon: PercentageOutlined },
    ];
  }
  return [
    { title: '营业收入', value: toWan(kpis.revenue), unit: '万元', precision: 2, trend: kpis.revenue_yoy_growth, icon: DollarOutlined },
    { title: '营业成本', value: toWan(kpis.cost), unit: '万元', precision: 2, trend: kpis.cost_yoy_growth, icon: FallOutlined },
    { title: '毛利额', value: toWan(kpis.gross_profit), unit: '万元', precision: 2, trend: kpis.profit_yoy_growth, icon: RiseOutlined },
    { title: '毛利率', value: kpis.gross_margin, unit: '%', precision: 2, trend: kpis.gross_margin_yoy_change, trendSuffix: '个百分点', icon: PercentageOutlined },
  ];
});

const trendData = computed(() => {
  const series = dashboardData.value?.kpis?.trend_series;
  if (series && series.length > 0) {
    return series.map((item: { period: string; revenue: number; cost: number; gross_profit: number; gross_margin: number }) => ({
      period: item.period,
      revenue: item.revenue,
      cost: item.cost,
      gross_profit: item.gross_profit,
      gross_margin: item.gross_margin,
    }));
  }
  if (dashboardData.value?.charts?.length) {
    const trendChart = dashboardData.value.charts.find((c) => c.type === 'line') || dashboardData.value.charts[0];
    return trendChart.data || [];
  }
  return [];
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

watch(() => [props.period, props.periodDimension, props.periodStart, props.periodEnd, props.department, props.product], fetchData);

onMounted(async () => {
  await Promise.all([
    fetchData(),
    insightsStore.fetchInsights(),
  ]);
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
</style>
