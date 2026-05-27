<template>
  <a-table
    :columns="columns"
    :data-source="rows"
    :pagination="{ pageSize: 10 }"
    size="small"
    row-key="dimension_value"
    :scroll="{ x: 'max-content' }"
  >
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'revenue' || column.key === 'tax_excluded_cost' || column.key === 'gross_profit'">
        {{ formatNumber(record[column.key]) }}
      </template>
      <template v-else-if="column.key === 'gross_margin' || column.key === 'gross_margin_contribution'">
        {{ formatPercent(record[column.key]) }}
      </template>
      <template v-else-if="column.key === 'revenue_mom_growth' || column.key === 'gross_profit_mom_growth'">
        <span :class="trendClass(record[column.key])">{{ formatPercent(record[column.key]) }}</span>
      </template>
      <template v-else-if="column.key === 'calculable'">
        <a-tag v-if="record.calculable" color="green">完整</a-tag>
        <a-tooltip v-else :title="`缺失：${(record.missing_fields ?? []).join(', ')}`">
          <a-tag color="orange">缺失</a-tag>
        </a-tooltip>
      </template>
    </template>
  </a-table>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { BreakdownItem } from '@/types/metrics';
import { formatPercent, formatWan } from '@/utils/format';

const props = defineProps<{
  breakdowns: BreakdownItem[];
  dimensionLabel?: string;
}>();

const columns = computed(() => [
  { title: props.dimensionLabel || '维度', dataIndex: 'dimension_value', key: 'dimension_value', fixed: 'left', width: 180 },
  { title: '收入(万元)', dataIndex: 'revenue', key: 'revenue', sorter: (a: BreakdownItem, b: BreakdownItem) => (a.revenue || 0) - (b.revenue || 0) },
  { title: '不含税成本(万元)', dataIndex: 'tax_excluded_cost', key: 'tax_excluded_cost' },
  { title: '毛利额(万元)', dataIndex: 'gross_profit', key: 'gross_profit', sorter: (a: BreakdownItem, b: BreakdownItem) => (a.gross_profit || 0) - (b.gross_profit || 0) },
  { title: '毛利率', dataIndex: 'gross_margin', key: 'gross_margin' },
  { title: '毛利贡献度', dataIndex: 'gross_margin_contribution', key: 'gross_margin_contribution' },
    { title: '数据状态', dataIndex: 'calculable', key: 'calculable', width: 100 },
]);

const rows = computed(() => props.breakdowns || []);

function formatNumber(v: number | undefined): string {
  return formatWan(v);
}
function trendClass(v: number | undefined): string {
  if (v === undefined || v === null) return '';
  if (v > 0) return 'text-success';
  if (v < 0) return 'text-error';
  return '';
}
</script>

<style scoped lang="less">
.text-success { color: #52c41a; }
.text-error { color: #ff4d4f; }
</style>
