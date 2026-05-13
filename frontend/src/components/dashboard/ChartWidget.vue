<template>
  <a-card class="chart-widget" :title="title" :loading="loading" :body-style="{ padding: '16px' }">
    <template #extra v-if="showExtra">
      <a-space>
        <a-button type="text" size="small" @click="$emit('refresh')">
          <ReloadOutlined />
        </a-button>
        <a-button type="text" size="small" @click="$emit('drilldown')">
          <SearchOutlined />
        </a-button>
      </a-space>
    </template>
    <v-chart
      v-if="chartOption && !loading"
      class="chart"
      :option="chartOption"
      renderer="canvas"
      autoresize
      :style="{ height: chartHeight }"
    />
    <a-empty v-else-if="!loading && !chartOption" description="暂无数据" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import VChart from 'vue-echarts';
import 'echarts/lib/chart/bar';
import 'echarts/lib/chart/line';
import 'echarts/lib/chart/pie';
import 'echarts/lib/chart/scatter';
import 'echarts/lib/component/tooltip';
import 'echarts/lib/component/legend';
import 'echarts/lib/component/grid';
import 'echarts/lib/component/title';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue';

const props = withDefaults(defineProps<{
  title: string;
  data?: Record<string, unknown>[];
  chartType?: string;
  loading?: boolean;
  showExtra?: boolean;
}>(), {
  data: () => [],
  chartType: 'bar',
  loading: false,
  showExtra: false,
});

defineEmits<{
  refresh: [];
  drilldown: [];
}>();

const isMobile = ref(window.innerWidth < 768);
const isTablet = ref(window.innerWidth >= 768 && window.innerWidth < 1024);

function updateBreakpoints() {
  isMobile.value = window.innerWidth < 768;
  isTablet.value = window.innerWidth >= 768 && window.innerWidth < 1024;
}

if (typeof window !== 'undefined') {
  window.addEventListener('resize', updateBreakpoints);
}

const chartHeight = computed(() => {
  if (isMobile.value) return '240px';
  if (isTablet.value) return '280px';
  return '320px';
});

const chartOption = computed(() => {
  if (!props.data?.length) return null;

  const baseOption = {
    tooltip: { trigger: 'axis' as const },
    legend: { bottom: 0, type: 'scroll' as const },
    grid: {
      top: 30,
      bottom: isMobile.value ? 50 : 40,
      left: isMobile.value ? 40 : 60,
      right: 20,
    },
  };

  const xKey = Object.keys(props.data[0])[0] || 'name';
  const valueKeys = Object.keys(props.data[0]).filter((k) => k !== xKey);

  switch (props.chartType) {
    case 'line':
      return {
        ...baseOption,
        xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
        yAxis: { type: 'value' as const },
        series: valueKeys.map((key) => ({ name: key, type: 'line', data: props.data.map((d) => d[key]), smooth: true })),
      };
    case 'area':
      return {
        ...baseOption,
        xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
        yAxis: { type: 'value' as const },
        series: valueKeys.map((key) => ({
          name: key,
          type: 'line',
          data: props.data.map((d) => d[key]),
          smooth: true,
          areaStyle: { opacity: 0.3 },
        })),
      };
    case 'scatter': {
      // Scatter/bubble: first value key = x, second = y, third = bubble size (optional)
      const xVal = valueKeys[0];
      const yVal = valueKeys[1] || xVal;
      const sizeVal = valueKeys[2];
      return {
        tooltip: { trigger: 'item' as const },
        grid: { top: 30, bottom: 50, left: 60, right: 20 },
        xAxis: { type: 'value' as const, name: xVal },
        yAxis: { type: 'value' as const, name: yVal },
        series: [{
          type: 'scatter',
          data: props.data.map((d) => [d[xVal], d[yVal], sizeVal ? d[sizeVal] : 10, d[xKey]]),
          symbolSize: (data: number[]) => sizeVal ? Math.max(10, Math.min(60, data[2] / 10)) : 15,
          label: {
            show: true,
            formatter: (p: { data: [number, number, number, string] }) => p.data[3],
            position: 'top',
            fontSize: 11,
          },
        }],
      };
    }
    case 'stacked-area': {
      return {
        ...baseOption,
        xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
        yAxis: { type: 'value' as const, stack: 'total' },
        series: valueKeys.map((key) => ({
          name: key,
          type: 'line',
          stack: 'total',
          data: props.data.map((d) => d[key]),
          smooth: true,
          areaStyle: { opacity: 0.6 },
        })),
      };
    }
    case 'bar':
      return {
        ...baseOption,
        xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
        yAxis: { type: 'value' as const },
        series: valueKeys.map((key) => ({ name: key, type: 'bar', data: props.data.map((d) => d[key]) })),
      };
    case 'pie': {
      const pieData = props.data.map((d) => ({ name: String(d[xKey]), value: d[valueKeys[0]] as number }));
      return {
        tooltip: { trigger: 'item' as const },
        legend: { bottom: 0, type: 'scroll' as const },
        series: [{ type: 'pie', radius: isMobile.value ? ['30%', '60%'] : ['40%', '70%'], data: pieData }],
      };
    }
    default:
      return {
        ...baseOption,
        xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]) },
        yAxis: { type: 'value' as const },
        series: [{ type: 'bar', data: props.data.map((d) => d[valueKeys[0]]) }],
      };
  }
});
</script>

<style scoped lang="less">
.chart-widget {
  border-radius: 8px;
  height: 100%;

  .chart {
    width: 100%;
  }
}
</style>
