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
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>核心市场线</span>
              </div>
              <div class="market-card-value">{{ data?.summary?.core_market_line || '-' }}</div>
              <div class="market-card-sub">贡献收入 <strong>¥{{ formatWan(data?.summary?.core_market_line_revenue) }}万</strong></div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="market-card">
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>最具价值市场线</span>
              </div>
              <div class="market-card-value">{{ data?.summary?.highest_value_market_line || '-' }}</div>
              <div class="market-card-sub">贡献毛利 <strong>¥{{ formatWan(data?.summary?.highest_value_market_profit) }}万</strong></div>
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
              :precision="0"
              :label-display="`收入占比 ${(data?.summary?.direct_sign_revenue_pct || 0).toFixed(2)}%`"
            />
          </a-col>
          <a-col :span="12">
            <KpiCard
              title="直签客户毛利"
              :value="toWan(data?.summary?.direct_sign_profit)"
              unit="万元"
              :precision="0"
              :label-display="`毛利率 ${(data?.summary?.direct_sign_margin || 0).toFixed(2)}%`"
            />
          </a-col>
        </a-row>
      </a-card>

      <!-- Section 2: 结构健康度 -->
      <a-card title="结构健康度" size="small" class="section-card">
        <a-row :gutter="[16, 16]" class="health-cards-row">
          <a-col :span="8">
            <div class="market-card">
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>客户集中度 Top10</span>
              </div>
              <div class="market-card-value">{{ ((data?.summary?.customer_concentration_top10 ?? 0).toFixed(2)) + '%' }}</div>
              <div class="market-card-sub">前10客户收入占比</div>
            </div>
          </a-col>
          <a-col :span="8">
            <div class="market-card">
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>产品集中度 Top10</span>
              </div>
              <div class="market-card-value">{{ ((data?.summary?.product_concentration_top10 ?? 0).toFixed(2)) + '%' }}</div>
              <div class="market-card-sub">前10产品毛利占比</div>
            </div>
          </a-col>
          <a-col :span="8">
            <div class="market-card">
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>单客户最高占比</span>
              </div>
              <div class="market-card-value">{{ ((data?.summary?.top_customer_share ?? 0).toFixed(2)) + '%' }}</div>
              <div class="market-card-sub">{{ topCustomerName }}</div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- Section 3: 增长与质量 -->
      <a-card title="增长与质量" size="small" class="section-card">
        <a-row :gutter="[16, 16]">
          <a-col :xs="12" :sm="12" :md="6" v-for="item in growthCards" :key="item.title">
            <div class="market-card">
              <div class="market-card-header">
                <svg class="market-card-icon" viewBox="0 0 24 24" width="14" height="14">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span>{{ item.title }}</span>
              </div>
              <div class="market-card-value">{{ item.value }}{{ item.unit }}</div>
              <div class="market-card-sub">{{ item.sub }}</div>
            </div>
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
import type { CoreMetricsResponse, BreakdownItem } from '@/types/metrics';
import { toWan, formatWan } from '@/utils/format';

const emit = defineEmits<{
  customerData: [customers: BreakdownItem[]];
}>();

const props = withDefaults(defineProps<{
  period?: string;
  dimension?: string;
  entity?: string;
  compare?: string;
  periodDimension?: string;
  product?: string;
  department?: string;
}>(), {
  period: undefined,
  dimension: 'company',
  entity: undefined,
  compare: 'all',
  periodDimension: 'monthly',
  product: undefined,
  department: undefined,
});

const loading = ref(false);
const data = ref<CoreMetricsResponse | null>(null);
const customerTop5 = ref<BreakdownItem[]>([]);

function num(v: number | undefined): number {
  return typeof v === 'number' ? v : 0;
}

const topCustomerName = computed(() => {
  const customers = data.value?.customer_breakdown || [];
  return customers.length ? customers[0].dimension_value : '';
});

function calcStreakAvg(trend: any[], field: string, streakMonths: number): number {
  // Calculate average growth over the consecutive growth streak ending at the last positive month
  // Example: if months 2,3 grew and month 4 dropped, streakMonths=2, average months 2,3 growth
  if (!trend || trend.length === 0 || streakMonths === 0) return 0;

  // Find the last positive month (end of streak)
  let lastPositive = -1;
  for (let i = trend.length - 1; i >= 0; i--) {
    const val = trend[i]?.[field];
    if (val !== null && val !== undefined && val > 0) {
      lastPositive = i;
      break;
    }
  }

  if (lastPositive === -1) return 0;

  // Average the growth rates from (lastPositive - streakMonths + 1) to lastPositive
  let sum = 0;
  let count = 0;
  const startIdx = Math.max(0, lastPositive - streakMonths + 1);

  for (let i = startIdx; i <= lastPositive; i++) {
    const val = trend[i]?.[field];
    if (val !== null && val !== undefined) {
      sum += val;
      count++;
    }
  }

  return count > 0 ? sum / count : 0;
}

const growthCards = computed(() => {
  const s = data.value?.summary || {};
  const trend = data.value?.trend_series || [];
  const isMonthly = props.periodDimension === 'monthly';
  const revConsec = s.revenue_consecutive_growth ?? null;
  const gpConsec = s.gross_profit_consecutive_growth ?? null;

  // Use backend-computed avg (based on monthly MoM) when available;
  // fall back to frontend calcStreakAvg for backward compat
  const revAvg = !isMonthly && revConsec != null
    ? (s.revenue_consecutive_growth_avg ?? calcStreakAvg(trend, 'revenue_mom_growth', revConsec))
    : 0;
  const gpAvg = !isMonthly && gpConsec != null
    ? (s.gross_profit_consecutive_growth_avg ?? calcStreakAvg(trend, 'gross_profit_mom_growth', gpConsec))
    : 0;

  const makeGrowthCard = (title: string, value: number | null, avg: number) => ({
    title,
    value: isMonthly || value == null ? '-' : value,
    unit: isMonthly || value == null ? '' : '月',
    sub: isMonthly || value == null ? '—' : `平均月度增长 ${avg.toFixed(2)}%`,
  });

  return [
    makeGrowthCard('收入连续增长', revConsec, revAvg),
    makeGrowthCard('毛利连续增长', gpConsec, gpAvg),
    {
      title: '负毛利订单占比',
      value: num(s.negative_margin_order_ratio),
      unit: '%',
      sub: `负毛利金额 ${formatWan(s.negative_margin_order_amount)}万`,
    },
    {
      title: '负毛利产品数量占比',
      value: num(s.negative_margin_product_ratio),
      unit: '%',
      sub: `负毛利金额 ${formatWan(s.negative_margin_product_amount)}万`,
    },
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
      period_dimension: props.periodDimension,
      product: props.product,
      department: props.department,
    });
    data.value = resp.data as CoreMetricsResponse;
    const customers = (resp.data as CoreMetricsResponse).customer_breakdown?.slice(0, 5) || [];
    customerTop5.value = customers;
    emit('customerData', customers);
  } finally {
    loading.value = false;
  }
}

defineExpose({ data, customerTop5, fetchData });

watch(() => [props.period, props.dimension, props.entity, props.periodDimension, props.product, props.department], fetchData);
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
  padding: 16px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  &-header {
    display: flex;
    align-items: center;
    color: #666666;
    font-size: 12px;
    margin-bottom: 12px;
  }
  &-icon {
    margin-right: 6px;
    fill: #666;
  }
  &-value {
    font-size: 32px;
    font-weight: 600;
    color: #D98D35;
    line-height: 1.2;
    margin-bottom: 4px;
  }
  &-sub {
    font-size: 14px;
    color: #607D8B;
    font-weight: 400;
  }
}
.direct-sign-row {
  margin-bottom: 0;
}

.health-cards-row {
  margin-bottom: 0;
}

</style>
