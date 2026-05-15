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
      @click="onChartClick"
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

const emit = defineEmits<{
  refresh: [];
  drilldown: [];
  'chart-click': [value: string];
}>();

function onChartClick(params: { name?: string }) {
  if (params.name) {
    emit('chart-click', params.name);
  }
}

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
  case 'bar-line': {
    const hasMargin = valueKeys.includes('gross_margin') || valueKeys.includes('毛利率');
    const marginKey = valueKeys.find((k) => k === 'gross_margin' || k === '毛利率') || '';
    const mainKeys = valueKeys.filter((k) => k !== marginKey);
    const nameKey = Object.keys(props.data[0])[0] || 'name';

    return {
      tooltip: { trigger: 'axis' as const },
      legend: { bottom: 0, type: 'scroll' as const },
      grid: { top: 30, bottom: isMobile.value ? 50 : 40, left: isMobile.value ? 40 : 60, right: hasMargin ? 60 : 20 },
      xAxis: { type: 'category' as const, data: props.data.map((d) => d[nameKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
      yAxis: [
        { type: 'value' as const, name: '万元', position: 'left' as const },
        ...(hasMargin ? [{ type: 'value' as const, name: '%', position: 'right' as const }] : []),
      ],
      series: [
        ...mainKeys.map((key) => ({
          name: key,
          type: 'bar' as const,
          yAxisIndex: 0,
          data: props.data.map((d) => Math.round(Number(d[key]) / 10000 * 100) / 100),
        })),
        ...(hasMargin ? [{
          name: marginKey || '毛利率',
          type: 'line' as const,
          yAxisIndex: 1,
          data: props.data.map((d) => d[marginKey]),
          smooth: true,
          lineStyle: { type: 'dashed' as const },
        }] : []),
      ],
    };
  }
  case 'line': {
    // Chinese legend mapping
    const legendMap: Record<string, string> = {
      revenue: '营业收入',
      cost: '营业成本',
      gross_profit: '毛利额',
      gross_margin: '毛利率',
    };
    const hasMargin = valueKeys.includes('gross_margin');
    const mainKeys = valueKeys.filter((k) => k !== 'gross_margin');

    return {
      ...baseOption,
      grid: {
        top: 30,
        bottom: isMobile.value ? 50 : 40,
        left: isMobile.value ? 40 : 60,
        right: hasMargin ? 60 : 20,
      },
      xAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]), axisLabel: { rotate: isMobile.value ? 45 : 0 } },
      yAxis: [
        { type: 'value' as const, name: '万元', position: 'left' as const },
        ...(hasMargin ? [{ type: 'value' as const, name: '%', position: 'right' as const, max: (v: any) => Math.ceil(v.max * 1.2) }] : []),
      ],
      series: [
        ...mainKeys.map((key) => ({
          name: legendMap[key] || key,
          type: 'line' as const,
          yAxisIndex: 0,
          data: props.data.map((d) => Math.round(Number(d[key]) / 10000 * 100) / 100),
          smooth: true,
        })),
        ...(hasMargin ? [{
          name: legendMap.gross_margin,
          type: 'line' as const,
          yAxisIndex: 1,
          data: props.data.map((d) => d['gross_margin']),
          smooth: true,
          lineStyle: { type: 'dashed' as const },
        }] : []),
      ],
      tooltip: {
        trigger: 'axis' as const,
        formatter: (params: any[]) => {
          let s = `${params[0]?.axisValue || ''}<br/>`;
          params.forEach((p: any) => {
            const val = p.seriesName === '毛利率' ? `${p.value}%` : `${p.value}万元`;
            s += `${p.marker} ${p.seriesName}: ${val}<br/>`;
          });
          return s;
        },
      },
      legend: { bottom: 0, type: 'scroll' as const },
    };
  }
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
    case 'grouped-bar': {
      const colorMap: Record<string, string> = { 营业收入: '#1890ff', 毛利额: '#52c41a' };
      return {
        tooltip: { trigger: 'axis' as const },
        legend: { bottom: 0, type: 'scroll' as const },
        grid: { top: 30, bottom: isMobile.value ? 50 : 40, left: isMobile.value ? 100 : 140, right: 40 },
        xAxis: { type: 'value' as const, name: '万元' },
        yAxis: { type: 'category' as const, data: props.data.map((d) => d[xKey]).reverse(), axisLabel: { fontSize: 11 } },
        series: valueKeys.map((key) => ({
          name: key,
          type: 'bar' as const,
          data: props.data.map((d) => +Math.round(Number(d[key]) / 10000 * 100) / 100).reverse(),
          itemStyle: { color: colorMap[key] || '#1890ff' },
        })),
      };
    }
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
