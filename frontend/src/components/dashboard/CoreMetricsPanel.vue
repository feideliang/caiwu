<template>
  <div class="core-metrics-panel">
    <a-spin :spinning="loading">
      <a-alert
        v-if="data && !data.data_quality.calculable"
        type="warning"
        show-icon
        :message="`数据不完整：缺失字段 ${data.data_quality.missing_fields.join(', ')}`"
        class="quality-alert"
      />
      <a-alert
        v-for="warn in (data?.data_quality.warnings || [])"
        :key="warn"
        type="info"
        show-icon
        :message="warn"
        class="quality-alert"
      />

      <!-- Section 1: 核心盈利能力 -->
      <a-card title="核心盈利能力" size="small" class="section-card">
        <a-row :gutter="[16, 16]">
          <a-col :xs="12" :sm="12" :md="8" :lg="5" v-for="item in profitabilityCards" :key="item.title">
            <KpiCard
              :title="item.title"
              :value="item.value"
              :unit="item.unit"
              :precision="item.precision"
              :trend="item.trend"
            />
          </a-col>
        </a-row>
      </a-card>

      <!-- Section 2: 结构健康度 -->
      <a-card title="结构健康度" size="small" class="section-card compact">
        <a-row :gutter="[12, 12]">
          <a-col :xs="24" :sm="12" :md="8" v-for="item in structureCards" :key="item.title">
            <KpiCard
              :title="item.title"
              :value="item.value"
              :unit="item.unit"
              :precision="item.precision"
            />
          </a-col>
        </a-row>
      </a-card>

      <!-- Section 3: 增长与质量 -->
      <a-card title="增长与质量" size="small" class="section-card">
        <a-row :gutter="[16, 16]">
          <a-col :xs="12" :sm="12" :md="6" v-for="item in growthCards" :key="item.title">
            <KpiCard
              :title="item.title"
              :value="item.value"
              :unit="item.unit"
              :precision="item.precision"
              :trend="item.trend"
            />
          </a-col>
        </a-row>
        <a-table
          v-if="marginAnalysis.length"
          :columns="marginColumns"
          :data-source="marginAnalysis"
          :pagination="false"
          size="small"
          bordered
          class="margin-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'current_revenue'">
              {{ fmtWan(record.current_revenue) }}
            </template>
            <template v-if="column.key === 'previous_revenue'">
              {{ fmtWan(record.previous_revenue) }}
            </template>
            <template v-if="column.key === 'structure_impact'">
              <span :class="impactClass(record.structure_impact)">{{ fmtImpact(record.structure_impact) }}</span>
            </template>
            <template v-if="column.key === 'margin_impact'">
              <span :class="impactClass(record.margin_impact)">{{ fmtImpact(record.margin_impact) }}</span>
            </template>
            <template v-if="column.key === 'total_impact'">
              <span :class="impactClass(record.total_impact)">{{ fmtImpact(record.total_impact) }}</span>
            </template>
          </template>
        </a-table>
      </a-card>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import KpiCard from './KpiCard.vue';
import { getCoreMetrics } from '@/api/metrics';
import type { CoreMetricsResponse, MarginChangeItem } from '@/types/metrics';
import { toWan } from '@/utils/format';
import type { TableColumnsType } from 'ant-design-vue';

const props = withDefaults(defineProps<{
  period?: string;
  dimension?: string;
  entity?: string;
  compare?: string;
}>(), {
  period: undefined,
  dimension: 'company',
  entity: undefined,
  compare: 'all',
});

const loading = ref(false);
const data = ref<CoreMetricsResponse | null>(null);

function num(v: number | undefined): number {
  return typeof v === 'number' ? v : 0;
}

const profitabilityCards = computed(() => {
  const s = data.value?.summary || {};
  return [
    { title: '收入', value: toWan(s.revenue), unit: '万元', precision: 2, trend: s.revenue_yoy_growth },
    { title: '不含税成本', value: toWan(s.tax_excluded_cost), unit: '万元', precision: 2 },
    { title: '毛利额', value: toWan(s.gross_profit), unit: '万元', precision: 2, trend: s.gross_profit_yoy_growth },
    { title: '毛利率', value: num(s.gross_margin), unit: '%', precision: 2 },
    { title: '收入环比', value: num(s.revenue_mom_growth), unit: '%', precision: 2, trend: s.revenue_mom_growth },
  ];
});

const structureCards = computed(() => {
  const s = data.value?.summary || {};
  return [
    { title: '客户集中度Top3', value: num(s.customer_concentration_top3), unit: '%', precision: 2 },
    { title: '产品集中度Top3', value: num(s.product_concentration_top3), unit: '%', precision: 2 },
    { title: '单客户收入最高占比', value: num(s.top_customer_share), unit: '%', precision: 2 },
  ];
});

const growthCards = computed(() => {
  const s = data.value?.summary || {};
  return [
    { title: '收入连续增长', value: num(s.revenue_consecutive_growth), unit: '期', precision: 0, trend: s.revenue_consecutive_growth },
    { title: '毛利连续增长', value: num(s.gross_profit_consecutive_growth), unit: '期', precision: 0, trend: s.gross_profit_consecutive_growth },
    { title: '高毛利订单占比', value: num(s.high_margin_order_ratio), unit: '%', precision: 2 },
    { title: '毛利率波动', value: num(s.gross_margin_volatility), unit: '%', precision: 2 },
  ];
});

const marginAnalysis = computed<MarginChangeItem[]>(() => {
  return data.value?.summary?.margin_change_analysis || [];
});

const marginColumns: TableColumnsType = [
  { title: '维度', dataIndex: 'dimension_value', key: 'dimension_value', width: 80, fixed: 'left' },
  { title: '当期收入(万)', key: 'current_revenue', width: 90, align: 'right' },
  { title: '当期占比%', dataIndex: 'current_share', key: 'current_share', width: 80, align: 'right', customRender: ({ text }) => text?.toFixed(2) },
  { title: '当期毛利率%', dataIndex: 'current_margin', key: 'current_margin', width: 80, align: 'right', customRender: ({ text }) => text?.toFixed(2) },
  { title: '基期收入(万)', key: 'previous_revenue', width: 90, align: 'right' },
  { title: '基期占比%', dataIndex: 'previous_share', key: 'previous_share', width: 80, align: 'right', customRender: ({ text }) => text?.toFixed(2) },
  { title: '基期毛利率%', dataIndex: 'previous_margin', key: 'previous_margin', width: 80, align: 'right', customRender: ({ text }) => text?.toFixed(2) },
  { title: '占比变化', dataIndex: 'share_change', key: 'share_change', width: 70, align: 'right', customRender: ({ text }) => text?.toFixed(2) + '%' },
  { title: '毛利率变化', dataIndex: 'margin_change', key: 'margin_change', width: 80, align: 'right', customRender: ({ text }) => text?.toFixed(2) + '%' },
  { title: '结构影响', key: 'structure_impact', width: 80, align: 'right' },
  { title: '毛利影响', key: 'margin_impact', width: 80, align: 'right' },
  { title: '合计', key: 'total_impact', width: 80, align: 'right' },
];

function fmtWan(v: number) {
  return toWan(v)?.toFixed(2) || '0';
}

function fmtImpact(v: number) {
  return v.toFixed(2) + '%';
}

function impactClass(v: number) {
  if (v > 0) return 'impact-positive';
  if (v < 0) return 'impact-negative';
  return 'impact-neutral';
}

async function fetchData() {
  loading.value = true;
  try {
    const { data: resp } = await getCoreMetrics({
      period: props.period,
      dimension: props.dimension,
      entity: props.entity,
      compare: props.compare,
    });
    data.value = resp.data as CoreMetricsResponse;
  } finally {
    loading.value = false;
  }
}

defineExpose({ data, fetchData });

watch(() => [props.period, props.dimension, props.entity], fetchData);
onMounted(fetchData);
</script>

<style scoped lang="less">
.core-metrics-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-card {
  margin-bottom: 0;
  &.compact :deep(.ant-card-body) {
    padding: 12px;
  }
}
.quality-alert {
  margin-bottom: 8px;
}
.margin-table {
  margin-top: 12px;
}
.impact-positive {
  color: #52c41a;
}
.impact-negative {
  color: #f5222d;
}
.impact-neutral {
  color: #999;
}
</style>
