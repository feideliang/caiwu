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
        <!-- 市场线卡片 -->
        <a-row :gutter="[16, 16]" class="market-line-row">
          <a-col :span="12">
            <div class="market-card">
              <div class="market-card-label">核心市场线</div>
              <div class="market-card-value">{{ data?.summary?.core_market_line || '-' }}</div>
              <div class="market-card-sub">收入贡献 <strong>{{ toWan(data?.summary?.core_market_line_revenue) || 0 }}万</strong></div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="market-card">
              <div class="market-card-label">最具价值市场线</div>
              <div class="market-card-value">{{ data?.summary?.highest_value_market_line || '-' }}</div>
              <div class="market-card-sub">毛利贡献 <strong>{{ toWan(data?.summary?.highest_value_market_profit) || 0 }}万</strong></div>
            </div>
          </a-col>
        </a-row>
        <!-- 直签客户 -->
        <a-row :gutter="[16, 16]" class="direct-sign-row">
          <a-col :span="12">
            <KpiCard
              title="直签客户收入"
              :value="toWan(data?.summary?.direct_sign_revenue)"
              unit="万元"
              :precision="2"
              :label-display="`收入占比 ${(data?.summary?.direct_sign_revenue_pct || 0).toFixed(1)}%`"
            />
          </a-col>
          <a-col :span="12">
            <KpiCard
              title="直签客户毛利"
              :value="toWan(data?.summary?.direct_sign_profit)"
              unit="万元"
              :precision="2"
              :label-display="`毛利率 ${(data?.summary?.direct_sign_margin || 0).toFixed(1)}%`"
            />
          </a-col>
        </a-row>
      </a-card>

      <!-- Section 2: 结构健康度 (Top 10) -->
      <a-card title="结构健康度" size="small" class="section-card compact">
        <div class="concentration-list">
          <div class="concentration-title">客户收入 Top 10</div>
          <div
            v-for="(item, idx) in customerTop10"
            :key="item.name"
            class="concentration-item"
          >
            <span class="rank-badge" :class="idx < 3 ? 'top' : 'normal'">{{ idx + 1 }}</span>
            <span class="name">{{ item.name }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: item.percent + '%' }"></div>
            </div>
            <span class="pct">{{ item.percent.toFixed(1) }}%</span>
          </div>
        </div>
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
      </a-card>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import KpiCard from './KpiCard.vue';
import { getCoreMetrics } from '@/api/metrics';
import type { CoreMetricsResponse } from '@/types/metrics';
import { toWan } from '@/utils/format';

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

// Top 10 customer concentration list
const customerTop10 = computed(() => {
  const breakdowns = data.value?.customer_breakdown || [];
  if (!breakdowns.length) return [];
  const maxRevenue = Math.max(...breakdowns.map((b) => b.revenue || 0), 1);
  const totalRevenue = breakdowns.reduce((sum, b) => sum + (b.revenue || 0), 0) || 1;
  return breakdowns.slice(0, 10).map((b) => ({
    name: b.dimension_value,
    percent: ((b.revenue || 0) / totalRevenue * 100),
    width: ((b.revenue || 0) / maxRevenue * 100),
  }));
});

const growthCards = computed(() => {
  const s = data.value?.summary || {};
  const avgMonthlyGrowth = num(s.revenue_mom_growth); // reuse existing MoM growth as avg monthly growth
  return [
    { title: '平均月度增长', value: Math.abs(avgMonthlyGrowth), unit: `%`, precision: 2, trend: avgMonthlyGrowth, trendNote: '月' },
    { title: '负毛利订单占比', value: num(s.negative_margin_order_ratio), unit: '%', precision: 2, trendNote: `负毛利金额 ${toWan(s.negative_margin_order_amount) || 0}万` },
    { title: '负毛利产品占比', value: num(s.negative_margin_product_ratio), unit: '%', precision: 2, trendNote: `负毛利金额 ${toWan(s.negative_margin_product_amount) || 0}万` },
  ];
});

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

// Market line cards
.market-line-row {
  margin-bottom: 12px;
}
.market-card {
  padding: 12px 16px;
  background: var(--color-bg-layout);
  border-radius: 8px;
  &-label {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-bottom: 4px;
  }
  &-value {
    font-size: 18px;
    font-weight: 600;
    color: var(--color-text);
  }
  &-sub {
    font-size: 13px;
    color: var(--color-text-secondary);
    margin-top: 4px;
  }
}
.direct-sign-row {
  margin-bottom: 0;
}

// Concentration list
.concentration-list {
  .concentration-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--color-text);
  }
  .concentration-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    .rank-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      font-size: 11px;
      font-weight: 600;
      color: #fff;
      &.top {
        background: #faad14;
      }
      &.normal {
        background: #d9d9d9;
        color: #666;
      }
    }
    .name {
      width: 80px;
      font-size: 13px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .progress-bar {
      flex: 1;
      height: 8px;
      background: #f0f0f0;
      border-radius: 4px;
      overflow: hidden;
      .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #1677ff, #4096ff);
        border-radius: 4px;
      }
    }
    .pct {
      font-size: 12px;
      color: var(--color-text-secondary);
      min-width: 45px;
      text-align: right;
    }
  }
}
</style>
