<template>
  <a-card class="kpi-card" :body-style="{ padding: cardPadding }">
    <a-statistic
      v-if="!labelDisplay"
      :title="title"
      :value="value"
      :precision="precision"
      :value-style="{ color: valueColor }"
    >
      <template #title>
        {{ title }}
        <span v-if="alert" class="alert-badge" :style="{ backgroundColor: alertColor }"></span>
      </template>
      <template #prefix>
        <component :is="icon" />
      </template>
      <template #suffix>
        <span class="unit">{{ unit }}</span>
        <span v-if="trend !== undefined" :class="['trend', trendClass]">
          <CaretUpOutlined v-if="trend > 0" />
          <CaretDownOutlined v-else-if="trend < 0" />
          {{ Math.abs(trend) }}{{ trendSuffix }}
        </span>
        <span v-else class="trend text-secondary">—</span>
      </template>
    </a-statistic>
    <div v-else class="text-kpi">
      <div class="text-kpi-title">{{ title }}</div>
      <div class="text-kpi-value">{{ labelDisplay }}</div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { Component } from 'vue';
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons-vue';

const props = withDefaults(defineProps<{
  title: string;
  value: number;
  unit?: string;
  precision?: number;
  trend?: number;
  trendSuffix?: string;
  color?: string;
  icon?: Component;
  alert?: 'red' | 'yellow' | 'blue';
  labelDisplay?: string;
}>(), {
  unit: '',
  precision: 2,
  trend: undefined,
  trendSuffix: '%',
  color: undefined,
  icon: undefined,
  alert: undefined,
  labelDisplay: undefined,
});

const isSmall = ref(window.innerWidth < 768);

function updateSize() {
  isSmall.value = window.innerWidth < 768;
}

onMounted(() => window.addEventListener('resize', updateSize));
onUnmounted(() => window.removeEventListener('resize', updateSize));

const alertColor = computed(() => {
  const map: Record<string, string> = { red: '#ff4d4f', yellow: '#faad14', blue: '#1677ff' };
  return map[props.alert || ''] || '';
});

const valueColor = computed(() => {
  if (props.color) return props.color;
  if (props.trend !== undefined) return props.trend >= 0 ? '#52c41a' : '#ff4d4f';
  return 'inherit';
});

const trendClass = computed(() => {
  if (props.trend === undefined) return '';
  return props.trend >= 0 ? 'text-success' : 'text-error';
});

const cardPadding = computed(() => isSmall.value ? '12px' : '20px 24px');
</script>

<style scoped lang="less">
.kpi-card {
  border-radius: 8px;
  transition: box-shadow 0.3s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

.unit {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-left: 4px;
}

.trend {
  margin-left: 8px;
  font-size: 14px;
}

.alert-badge {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 6px;
  vertical-align: middle;
}
</style>
