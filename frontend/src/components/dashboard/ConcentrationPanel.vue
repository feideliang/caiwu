<template>
  <a-card :title="panelTitle" size="small" class="concentration-panel">
    <a-list :data-source="topItems" size="small">
      <template #renderItem="{ item, index }">
        <a-list-item>
          <div class="rank-row">
            <span :class="['rank-badge', index < 3 ? `rank-${index + 1}` : '']">{{ index + 1 }}</span>
            <span class="name">{{ item.dimension_value }}</span>
            <div class="metrics">
              <div class="metric-row">
                <span class="metric-label">收入</span>
                <span class="metric-value">{{ formatNumber(item.revenue) }}</span>
                <a-progress :percent="percent(item.revenue, maxItemRevenue)" :show-info="false" size="small" class="bar" />
              </div>
              <div class="metric-row">
                <span class="metric-label">毛利额</span>
                <span class="metric-value profit">{{ formatNumber(item.gross_profit) }}</span>
                <a-progress :percent="percent(item.gross_profit, maxItemProfit)" :show-info="false" size="small" stroke-color="#52c41a" class="bar" />
              </div>
              <div class="metric-row">
                <span class="metric-label">毛利率</span>
                <span class="metric-value margin">{{ formatMargin(item.gross_margin) }}</span>
                <a-progress :percent="percent(item.gross_margin, 100)" :show-info="false" size="small" stroke-color="#faad14" class="bar" />
              </div>
            </div>
          </div>
        </a-list-item>
      </template>
    </a-list>
    <a-empty v-if="topItems.length === 0" />
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { BreakdownItem } from '@/types/metrics';
import { formatPercent, formatWan } from '@/utils/format';

const props = defineProps<{
  customers?: BreakdownItem[];
  breakdowns?: BreakdownItem[];
  dimension?: string;
}>();

const DIMENSION_LABELS: Record<string, string> = {
  customer: '客户',
  product_line: '产品线',
  department: '部门',
};

const panelTitle = computed(() => {
  const label = DIMENSION_LABELS[props.dimension || ''] || '';
  return `Top 10 ${label}集中度排名`;
});

const topItems = computed<BreakdownItem[]>(() => {
  if (props.dimension === 'customer' && props.customers?.length) {
    return [...props.customers].sort((a, b) => (b.revenue || 0) - (a.revenue || 0)).slice(0, 10);
  }
  if (props.breakdowns?.length) {
    return [...props.breakdowns].sort((a, b) => (b.revenue || 0) - (a.revenue || 0)).slice(0, 10);
  }
  return [];
});

const maxItemRevenue = computed(() => Math.max(1, ...topItems.value.map((c) => c.revenue || 0)));
const maxItemProfit = computed(() => Math.max(1, ...topItems.value.map((c) => Math.abs(c.gross_profit || 0))));

function percent(value: number | undefined, max: number): number {
  if (!value || !max) return 0;
  return Math.round((Math.abs(value) / max) * 100);
}

function formatNumber(v: number | undefined): string {
  const formatted = formatWan(v);
  return formatted === '-' ? formatted : `${formatted}万元`;
}

function formatMargin(v: number | undefined): string {
  return formatPercent(v);
}
</script>

<style scoped lang="less">
.concentration-panel {
  max-width: 600px;
}

.rank-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    text-align: center;
    background: #e8e8e8;
    color: #888;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;
    margin-top: 2px;

    &.rank-1 { background: #ffd700; color: #fff; }
    &.rank-2 { background: #c0c0c0; color: #fff; }
    &.rank-3 { background: #cd7f32; color: #fff; }
  }
  .name {
    width: 80px;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
  }
  .metrics {
    flex: 1;
    min-width: 0;
  }
  .metric-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;

    .metric-label {
      font-size: 12px;
      color: var(--color-text-secondary);
      width: 40px;
      flex-shrink: 0;
    }
    .metric-value {
      font-weight: 600;
      font-size: 12px;
      color: var(--color-primary, #1677ff);
      width: 90px;
      flex-shrink: 0;
      &.profit { color: #52c41a; }
      &.margin { color: #faad14; }
    }
    .bar {
      width: 80px;
      flex-shrink: 0;
    }
  }
}
</style>
