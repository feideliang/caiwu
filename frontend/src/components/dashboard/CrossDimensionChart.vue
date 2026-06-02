<template>
  <a-card
    class="cross-dimension-chart"
    :title="title"
    :loading="loading"
    :body-style="{ padding: '16px' }"
  >
    <v-chart
      v-if="chartOption && !loading"
      ref="chartRef"
      class="chart"
      :option="chartOption"
      renderer="canvas"
      autoresize
      :style="{ height: chartHeight }"
    />
    <a-empty v-else-if="!loading && !hasData" description="暂无数据" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import VChart from 'vue-echarts';
import 'echarts/lib/chart/bar';
import 'echarts/lib/component/tooltip';
import 'echarts/lib/component/legend';
import 'echarts/lib/component/grid';
import { getCoreMetrics } from '@/api/metrics';
import type { BreakdownItem } from '@/types/metrics';

const props = withDefaults(defineProps<{
  title?: string;
  crossDimension: string;
  primaryDimension: string;
  primaryEntity: string;
  period: string;
  periodStart?: string;
  periodEnd?: string;
  periodDimension?: string;
  compareBase?: string;
}>(), {
  title: '',
  periodStart: undefined,
  periodEnd: undefined,
  periodDimension: undefined,
  compareBase: undefined,
});

const loading = ref(false);
const breakdownData = ref<BreakdownItem[]>([]);
const chartRef = ref<any>(null);

const isMobile = ref(window.innerWidth < 768);
const isTablet = ref(window.innerWidth >= 768 && window.innerWidth < 1024);

function updateBreakpoints() {
  isMobile.value = window.innerWidth < 768;
  isTablet.value = window.innerWidth >= 768 && window.innerWidth < 1024;
}

onMounted(() => {
  window.addEventListener('resize', updateBreakpoints);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateBreakpoints);
});

const chartHeight = computed(() => {
  if (isMobile.value) return '240px';
  if (isTablet.value) return '280px';
  return '320px';
});

const hasData = computed(() => breakdownData.value.length > 0);

async function fetchData() {
  loading.value = true;
  try {
    const resp = await getCoreMetrics({
      period: props.period,
      dimension: props.crossDimension,
      entity: props.primaryEntity,
      compare: props.compareBase,
      period_dimension: props.periodDimension,
      period_start: props.periodStart,
      period_end: props.periodEnd,
    });
    const body = resp.data;
    const data = body.data;
    const key = `${props.crossDimension}_breakdown` as keyof typeof data;
    const items = (data[key] ?? data.breakdowns) as BreakdownItem[] | undefined;
    breakdownData.value = items ?? [];
  } catch {
    breakdownData.value = [];
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.crossDimension, props.primaryDimension, props.primaryEntity, props.period, props.periodStart, props.periodEnd, props.periodDimension, props.compareBase] as const,
  () => {
    fetchData();
  },
  { immediate: true },
);

const chartOption = computed(() => {
  const data = breakdownData.value.filter((d) => d.revenue != null || d.gross_profit != null);
  if (!data.length) return null;

  const names = data.map((d) => d.dimension_value);
  const revenueValues = data.map((d) => {
    const v = Number(d.revenue) / 10000;
    return Math.round(v * 100) / 100;
  });
  const profitValues = data.map((d) => {
    const v = Number(d.gross_profit) / 10000;
    return Math.round(v * 100) / 100;
  });
  const marginValues = data.map((d) => Number(d.gross_margin ?? null));

  const hasMargin = marginValues.some((v) => v != null);

  return {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any[]) => {
        let s = `${params[0]?.axisValue || ''}<br/>`;
        for (const p of params) {
          const unit = p.seriesName === '毛利率' ? '%' : '万元';
          s += `${p.marker} ${p.seriesName}: ${p.value}${unit}<br/>`;
        }
        return s;
      },
    },
    legend: {
      bottom: 0,
      type: 'scroll' as const,
    },
    grid: {
      top: 30,
      bottom: isMobile.value ? 50 : 40,
      left: isMobile.value ? 40 : 60,
      right: hasMargin ? 60 : 20,
    },
    xAxis: {
      type: 'category' as const,
      data: names,
      axisLabel: {
        rotate: isMobile.value ? 45 : 0,
        interval: isMobile.value ? 'auto' : 0,
        fontSize: 11,
      },
    },
    yAxis: [
      {
        type: 'value' as const,
        name: '万元',
        position: 'left' as const,
        axisLabel: {
          formatter: (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 }),
        },
      },
      ...(hasMargin
        ? [
            {
              type: 'value' as const,
              name: '%',
              position: 'right' as const,
              axisLabel: {
                formatter: (v: number) => v.toFixed(1),
              },
            },
          ]
        : []),
    ],
    series: [
      {
        name: '营业收入',
        type: 'bar' as const,
        yAxisIndex: 0,
        data: revenueValues,
        itemStyle: { color: '#1890ff' },
      },
      {
        name: '毛利额',
        type: 'bar' as const,
        yAxisIndex: 0,
        data: profitValues,
        itemStyle: { color: '#52c41a' },
      },
      ...(hasMargin
        ? [
            {
              name: '毛利率',
              type: 'line' as const,
              yAxisIndex: 1,
              data: marginValues,
              smooth: true,
              lineStyle: { type: 'dashed' as const, width: 2 },
              itemStyle: { color: '#faad14' },
              symbol: 'circle',
              symbolSize: 6,
            },
          ]
        : []),
    ],
  };
});

defineExpose({ fetchData });
</script>

<style scoped lang="less">
.cross-dimension-chart {
  border-radius: 8px;
  height: 100%;

  .chart {
    width: 100%;
  }
}
</style>
