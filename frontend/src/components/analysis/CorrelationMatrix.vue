<template>
  <div class="correlation-matrix">
    <a-spin :spinning="loading">
      <v-chart
        v-if="matrix.length > 0"
        class="heatmap-chart"
        :option="chartOption"
        renderer="canvas"
        :autoresize="true"
        @click="onChartClick as any"
      />
      <a-empty v-else-if="!loading" description="暂无数据" />
    </a-spin>

    <!-- Legend -->
    <div class="matrix-legend">
      <span class="label">相关性:</span>
      <div class="gradient-bar">
        <span class="gradient-label">-1.0 (强负相关)</span>
        <div class="gradient-track" />
        <span class="gradient-label">0</span>
        <div class="gradient-track positive" />
        <span class="gradient-label">+1.0 (强正相关)</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { HeatmapChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GridComponent,
} from 'echarts/components';
import type { EChartsOption } from 'echarts';

use([
  markRaw(CanvasRenderer),
  markRaw(HeatmapChart),
  markRaw(TitleComponent),
  markRaw(TooltipComponent),
  markRaw(VisualMapComponent),
  markRaw(GridComponent),
]);

const props = defineProps<{
  variables: string[];
  matrix: number[][];
  loading?: boolean;
}>();

const emit = defineEmits<{
  'cell-click': [data: { x: string; y: string; value: number }];
}>();

function shortLabel(name: string): string {
  if (name.length > 10) return name.substring(0, 8) + '..';
  return name;
}

// Build heatmap data: [xIndex, yIndex, value]
const heatmapData = computed(() => {
  const data: [number, number, number][] = [];
  for (let y = 0; y < props.matrix.length; y++) {
    for (let x = 0; x < props.matrix[y].length; x++) {
      data.push([x, y, props.matrix[y][x]]);
    }
  }
  return data;
});

const chartOption = computed<EChartsOption>(() => ({
  tooltip: {
    position: 'top',
    formatter: ((params: { data: [number, number, number] }) => {
      const [x, y, val] = params.data;
      return `${props.variables[y]} vs ${props.variables[x]}: ${val.toFixed(3)}`;
    }) as any,
  },
  grid: {
    top: 10,
    bottom: 80,
    left: 100,
    right: 40,
  },
  xAxis: {
    type: 'category',
    data: props.variables.map((v) => shortLabel(v)),
    axisLabel: { rotate: 45, fontSize: 11 },
    splitArea: { show: true },
  },
  yAxis: {
    type: 'category',
    data: props.variables.map((v) => shortLabel(v)),
    axisLabel: { fontSize: 11 },
    splitArea: { show: true },
  },
  visualMap: {
    min: -1,
    max: 1,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    inRange: {
      color: ['#ff4d4f', '#ffffff', '#52c41a'],
    },
    text: ['1.0', '-1.0'],
  },
  series: [
    {
      name: '相关系数',
      type: 'heatmap',
      data: heatmapData.value,
      label: {
        show: true,
        fontSize: 11,
        formatter: ((params: { data: [number, number, number] }) => {
          const [, , val] = params.data;
          return val.toFixed(2);
        }) as any,
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
    },
  ],
}));

function onChartClick(params: { data: [number, number, number] }) {
  const [x, y, value] = params.data;
  emit('cell-click', {
    x: props.variables[x],
    y: props.variables[y],
    value,
  });
}
</script>

<style scoped lang="less">
.correlation-matrix {
  width: 100%;
}

.heatmap-chart {
  width: 100%;
  height: 400px;
}

.matrix-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  justify-content: center;

  .label {
    font-size: 12px;
    color: var(--color-text-secondary);
  }

  .gradient-bar {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .gradient-track {
    width: 80px;
    height: 12px;
    background: linear-gradient(to right, #ff4d4f, #ffffff);
    border-radius: 2px;

    &.positive {
      background: linear-gradient(to right, #ffffff, #52c41a);
    }
  }

  .gradient-label {
    font-size: 11px;
    color: var(--color-text-secondary);
  }
}

@media (max-width: 767px) {
  .heatmap-chart {
    height: 300px;
  }
}
</style>
