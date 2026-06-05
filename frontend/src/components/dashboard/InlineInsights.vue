<template>
  <div v-if="insights.length > 0" class="inline-insights">
    <div class="insights-header">
      <BulbOutlined class="header-icon" />
      <span class="header-title">核心趋势洞察</span>
    </div>
    <div class="insights-list">
      <a-tooltip v-for="(insight, index) in insights" :key="index" placement="top">
        <template #title>
          <div class="tooltip-content">{{ insight.calculation }}</div>
        </template>
        <div :class="['insight-item', `type-${insight.type}`]" :style="{ cursor: insight.route ? 'pointer' : 'default' }" @click="handleDrill(insight)">
          <component :is="insightIcon(insight.type)" class="insight-icon" />
          <span class="insight-text">{{ insight.title }}</span>
          <ArrowRightOutlined v-if="insight.route" class="drill-arrow" />
        </div>
      </a-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue';
import { useRouter } from 'vue-router';
import { BulbOutlined, ArrowUpOutlined, ArrowDownOutlined, InfoCircleOutlined, WarningOutlined, ArrowRightOutlined } from '@ant-design/icons-vue';
import type { BreakdownItem, CoreMetricsSummary, TrendDataPoint } from '@/types/metrics';
import { useInlineInsights, type InlineInsight } from '@/composables/useInsights';

const router = useRouter();

const props = withDefaults(defineProps<{
  breakdowns: BreakdownItem[];
  summary?: CoreMetricsSummary;
  dimension?: 'department' | 'product_bgbu' | 'company' | 'customer';
  trendSeries?: TrendDataPoint[];
  maxCount?: number;
}>(), {
  dimension: 'department',
  maxCount: 5,
});

const insights = useInlineInsights({
  dimension: props.dimension,
  breakdowns: computed(() => props.breakdowns),
  summary: computed(() => props.summary),
  trendSeries: computed(() => props.trendSeries || []),
  maxCount: props.maxCount,
});

const iconMap: Record<string, Component> = {
  positive: ArrowUpOutlined,
  negative: ArrowDownOutlined,
  warning: WarningOutlined,
  neutral: InfoCircleOutlined,
};

function insightIcon(type: InlineInsight['type']): Component {
  return iconMap[type] || InfoCircleOutlined;
}

function handleDrill(insight: InlineInsight) {
  if (insight.route) {
    router.push(insight.route);
  }
}
</script>

<style scoped lang="less">
.inline-insights {
  background: #fff8f8;
  border: 1px solid #ffccc7;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.insights-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ffccc7;

  .header-icon {
    font-size: 18px;
    color: #c41d1d;
  }

  .header-title {
    font-weight: 600;
    font-size: 14px;
  }
}

.insights-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid transparent;
  cursor: default;
  transition: background-color 0.2s;

  &:hover {
    background-color: #fafafa;
  }

  &.type-positive {
    border-left-color: #52c41a;
    .insight-icon { color: #52c41a; }
  }

  &.type-negative {
    border-left-color: #ff4d4f;
    .insight-icon { color: #ff4d4f; }
  }

  &.type-warning {
    border-left-color: #faad14;
    .insight-icon { color: #faad14; }
  }

  &.type-neutral {
    border-left-color: #1677ff;
    .insight-icon { color: #1677ff; }
  }

  .insight-icon {
    font-size: 14px;
    flex-shrink: 0;
  }

  .insight-text {
    font-size: 13px;
    color: var(--color-text, #333);
  }

  .drill-arrow {
    margin-left: auto;
    font-size: 12px;
    color: #bbb;
  }
}

.tooltip-content {
  font-size: 12px;
  line-height: 1.6;
  max-width: 400px;
  white-space: normal;
}
</style>
