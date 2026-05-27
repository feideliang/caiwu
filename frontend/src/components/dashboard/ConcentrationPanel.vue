<template>
  <a-card title="Top 10 客户集中度排名" size="small" class="concentration-panel">
    <a-row :gutter="16">
      <a-col :span="12">
        <a-list :data-source="leftItems" size="small">
          <template #renderItem="{ item, index }">
            <a-list-item>
              <div class="rank-row">
                <span :class="['rank-badge', index < 3 ? `rank-${index + 1}` : '']">{{ index + 1 }}</span>
                <span class="name">{{ item.dimension_value }}</span>
                <div class="metrics">
                  <div class="metric-row">
                    <span class="metric-label">收入</span>
                    <span class="metric-value">{{ formatNumber(item.revenue) }}</span>
                    <a-progress :percent="percent(item.revenue, overallMax)" :show-info="false" size="small" class="bar" />
                  </div>
                  <div class="metric-row">
                    <span class="metric-label">毛利额</span>
                    <span class="metric-value profit">{{ formatNumber(item.gross_profit) }}</span>
                    <a-progress :percent="percent(item.gross_profit, overallMax)" :show-info="false" size="small" stroke-color="#52c41a" class="bar" />
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
      </a-col>
      <a-col :span="12">
        <a-list :data-source="rightItems" size="small">
          <template #renderItem="{ item, index }">
            <a-list-item>
              <div class="rank-row">
                <span :class="['rank-badge', (index + 5) < 3 ? `rank-${index + 1}` : '']">{{ index + 6 }}</span>
                <span class="name">{{ item.dimension_value }}</span>
                <div class="metrics">
                  <div class="metric-row">
                    <span class="metric-label">收入</span>
                    <span class="metric-value">{{ formatNumber(item.revenue) }}</span>
                    <a-progress :percent="percent(item.revenue, overallMax)" :show-info="false" size="small" class="bar" />
                  </div>
                  <div class="metric-row">
                    <span class="metric-label">毛利额</span>
                    <span class="metric-value profit">{{ formatNumber(item.gross_profit) }}</span>
                    <a-progress :percent="percent(item.gross_profit, overallMax)" :show-info="false" size="small" stroke-color="#52c41a" class="bar" />
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
      </a-col>
    </a-row>
    <a-empty v-if="!allItems.length" />
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

const allItems = computed<BreakdownItem[]>(() => {
  const source = (props.dimension === 'customer' && props.customers?.length)
    ? props.customers
    : props.breakdowns;
  return [...(source || [])]
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 10);
});

const leftItems = computed(() => allItems.value.slice(0, 5));
const rightItems = computed(() => allItems.value.slice(5, 10));

const overallMax = computed(() => {
  const rev = Math.max(1, ...allItems.value.map((c) => c.revenue || 0));
  const gp = Math.max(1, ...allItems.value.map((c) => Math.abs(c.gross_profit || 0)));
  return Math.max(rev, gp);
});

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
  width: 100%;
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