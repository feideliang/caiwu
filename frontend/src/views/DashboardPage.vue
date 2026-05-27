<template>
  <div class="dashboard-page">
    <!-- Filter bar: 周期维度 + 筛选周期 + 市场线 + 产品线 -->
    <div class="dashboard-header">
      <a-space wrap>
        <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
          <a-select-option value="monthly">月度</a-select-option>
          <a-select-option value="quarterly">季度</a-select-option>
          <a-select-option value="cumulative">年累计</a-select-option>
          <a-select-option value="custom">自定义期间</a-select-option>
        </a-select>
        <a-range-picker
          v-if="periodDimension === 'custom'"
          v-model:value="customRange"
          picker="month"
          :allow-clear="true"
          style="width: 280px"
          format="YYYY年M月"
          @change="onCustomRangeChange"
        />
        <a-select
          v-else
          v-model:value="selectedPeriod"
          :options="periodSelectOptions"
          style="width: 160px"
          placeholder="筛选周期"
          allow-clear
        />
        <a-divider type="vertical" />
        <a-select v-model:value="selectedMarketLine" :options="marketLineOptions" style="width: 160px" placeholder="市场线" allow-clear />
        <a-select v-model:value="selectedProduct" :options="productOptions" style="width: 160px" placeholder="产品线" allow-clear />
      </a-space>
    </div>
    <!-- Content: left = overview, right = assistant -->
    <div class="dashboard-content">
      <FinancialOverview
        :period="period"
        :period-dimension="periodDimension"
        :period-start="periodStart"
        :period-end="periodEnd"
        :department="selectedMarketLine"
        :product="selectedProduct"
      />
    </div>
    <div v-if="showAssistant" class="dashboard-assistant">
      <FinancialAssistantPanel :context="assistantContext" :recommendations="recommendations" />
    </div>
  </div>
</template>

<script setup lang="ts">
import FinancialOverview from '@/components/dashboard/FinancialOverview.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getFilterOptions } from '@/api/filters';
import { getAnalysisRecommendations } from '@/api/ai';
import type { AnalysisRecommendations } from '@/types/analysis';
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import {
  buildPeriodOptions,
  formatMonthValue,
  getDefaultPeriod,
  normalizePeriodDimension,
} from '@/utils/period';

const isSmall = ref(window.innerWidth < 1024);
const loading = ref(false);

// Filter state
const periodDimension = ref<string>('monthly');
const selectedPeriod = ref<string | undefined>();
const customRange = ref<[any, any] | null>(null);
const periodStart = ref<string | undefined>();
const periodEnd = ref<string | undefined>();
const selectedMarketLine = ref<string | undefined>();
const selectedProduct = ref<string | undefined>();
const marketLineOptions = ref<Array<{ label: string; value: string }>>([]);
const productOptions = ref<Array<{ label: string; value: string }>>([]);

// Raw period list from backend
const allPeriods = ref<string[]>([]);

const period = computed(() => {
  if (periodDimension.value === 'custom') return undefined;
  return selectedPeriod.value;
});

const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  return buildPeriodOptions(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

function onCustomRangeChange(dates: any) {
  if (dates && dates[0] && dates[1]) {
    periodStart.value = formatMonthValue(dates[0]);
    periodEnd.value = formatMonthValue(dates[1]);
  } else {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
}

watch([selectedPeriod, periodDimension], () => {
  if (periodDimension.value !== 'custom') {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
  if (!selectedPeriod.value && periodDimension.value !== 'custom') {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
  loadRecommendations();
});

watch(periodDimension, () => {
  selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
});

function updateSize() {
  isSmall.value = window.innerWidth < 1024;
}

const showAssistant = computed(() => !isSmall.value);

const assistantContext = computed(() => ({
  period: period.value,
  period_dimension: periodDimension.value,
  period_start: periodStart.value,
  period_end: periodEnd.value,
  department: selectedMarketLine.value,
  product: selectedProduct.value,
  active_section: 'overview' as string,
}));

const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'dashboard',
      period: period.value,
      period_compare_type: 'yoy',
      department: selectedMarketLine.value,
      product: selectedProduct.value,
    });
    recommendations.value = data.data || null;
  } catch { /* non-critical */ }
}

async function fetchFilterOptions() {
  loading.value = true;
  try {
    const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
    const periods = ((periodResp.data as any)?.options || []) as string[];
    allPeriods.value = periods;

    // Default: select latest period
    if (!selectedPeriod.value && allPeriods.value.length) {
      selectedPeriod.value = getDefaultPeriod(allPeriods.value, normalizePeriodDimension(periodDimension.value));
    }

    // Market line options
    const { data: deptResp } = await getFilterOptions({ dimension: 'department' });
    const depts = ((deptResp.data as any)?.options || []) as string[];
    marketLineOptions.value = depts.map((v) => ({ label: v, value: v }));

    // Product line options
    const { data: prodResp } = await getFilterOptions({ dimension: 'product_line' });
    const prods = ((prodResp.data as any)?.options || []) as string[];
    productOptions.value = prods.map((v) => ({ label: v, value: v }));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  window.addEventListener('resize', updateSize);
  fetchFilterOptions();
  loadRecommendations();
});
onUnmounted(() => window.removeEventListener('resize', updateSize));
</script>

<style scoped lang="less">
.dashboard-page {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: auto 1fr;

  .dashboard-header {
    grid-column: 1 / -1;
    padding: 16px;
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--color-bg-layout);
  }

  .dashboard-content {
    min-width: 0;
    padding: 0 16px;
  }

  .dashboard-assistant {
    min-width: 0;
  }
}

@media (max-width: 1023px) {
  .dashboard-page {
    grid-template-columns: 1fr;
    .dashboard-assistant {
      width: 100%;
    }
  }
}
</style>
