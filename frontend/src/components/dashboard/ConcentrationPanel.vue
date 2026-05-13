<template>
  <a-card title="Top 5 客户 (按收入)" size="small" class="concentration-panel">
    <a-list :data-source="topCustomers" size="small">
      <template #renderItem="{ item, index }">
        <a-list-item>
          <div class="rank-row">
            <span :class="['rank-badge', index < 3 ? `rank-${index + 1}` : '']">{{ index + 1 }}</span>
            <span class="name">{{ item.dimension_value }}</span>
            <span class="value">{{ formatNumber(item.revenue) }}</span>
            <a-progress
              :percent="percent(item.revenue, maxCustomerRevenue)"
              :show-info="false"
              size="small"
              class="bar"
            />
          </div>
        </a-list-item>
      </template>
    </a-list>
    <a-empty v-if="topCustomers.length === 0" />
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { BreakdownItem } from '@/types/metrics';
import { toWan } from '@/utils/format';

const props = defineProps<{
  customers?: BreakdownItem[];
  products?: BreakdownItem[];
  breakdowns?: BreakdownItem[];
  dimension?: string;
}>();

const topCustomers = computed<BreakdownItem[]>(() => {
  if (props.customers && props.customers.length) {
    return [...props.customers].sort((a, b) => (b.revenue || 0) - (a.revenue || 0)).slice(0, 5);
  }
  if (props.dimension === 'customer' && props.breakdowns) {
    return [...props.breakdowns].sort((a, b) => (b.revenue || 0) - (a.revenue || 0)).slice(0, 5);
  }
  return [];
});

const maxCustomerRevenue = computed(() => {
  return Math.max(1, ...topCustomers.value.map((c) => c.revenue || 0));
});

function percent(value: number | undefined, max: number): number {
  if (!value || !max) return 0;
  return Math.round((value / max) * 100);
}

function formatNumber(v: number | undefined): string {
  if (v === undefined || v === null) return '-';
  return toWan(v).toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + ' 万元';
}
</script>

<style scoped lang="less">
.concentration-panel {
  max-width: 600px;
}

.rank-row {
  display: flex;
  align-items: center;
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

    &.rank-1 { background: #ffd700; color: #fff; }
    &.rank-2 { background: #c0c0c0; color: #fff; }
    &.rank-3 { background: #cd7f32; color: #fff; }
  }
  .name {
    flex: 1;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .value {
    font-weight: 600;
    font-size: 13px;
    color: var(--color-primary, #1677ff);
  }
  .bar {
    width: 80px;
    flex-shrink: 0;
  }
}
</style>
