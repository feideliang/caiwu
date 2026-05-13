<template>
  <div class="dashboard-page">
    <!-- Filter bar + divider: full-width header row -->
    <div class="dashboard-header">
      <a-space wrap>
        <a-select v-model:value="selectedYear" :options="yearOptions" style="width: 120px" placeholder="年" allow-clear />
        <a-select v-model:value="selectedMonth" :options="monthOptions" style="width: 120px" placeholder="月" allow-clear />
        <a-divider type="vertical" />
        <a-select v-model:value="selectedMarketLine" :options="marketLineOptions" style="width: 160px" placeholder="市场线" allow-clear />
        <a-select v-model:value="selectedProduct" :options="productOptions" style="width: 160px" placeholder="产品线" allow-clear />
      </a-space>
    </div>
    <!-- Content: left = overview, right = assistant -->
    <div class="dashboard-content">
      <FinancialOverview :period="period" :period-compare-type="periodCompareType" :department="selectedMarketLine" :product="selectedProduct" />
    </div>
    <div v-if="showAssistant" class="dashboard-assistant">
      <FinancialAssistantPanel :context="assistantContext" />
    </div>
  </div>
</template>

<script setup lang="ts">
import FinancialOverview from '@/components/dashboard/FinancialOverview.vue';
import FinancialAssistantPanel from '@/components/ai/FinancialAssistantPanel.vue';
import { getFilterOptions } from '@/api/filters';
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';

const isSmall = ref(window.innerWidth < 1024);
const loading = ref(false);

// Filter state
const selectedYear = ref<string | undefined>();
const selectedMonth = ref<string | undefined>();
const selectedMarketLine = ref<string | undefined>();
const selectedProduct = ref<string | undefined>();

// Derived period string (e.g. '2026-03')
const period = computed(() => {
  if (selectedYear.value && selectedMonth.value) {
    return `${selectedYear.value}-${selectedMonth.value}`;
  }
  return undefined;
});

// Period compare type is NOT shown in UI, kept as AI context default
const periodCompareType = ref<'yoy' | 'mom' | 'cumulative'>('mom');

// Filter options
const yearOptions = ref<Array<{ label: string; value: string }>>([]);
const monthOptions = ref<Array<{ label: string; value: string }>>([]);
const marketLineOptions = ref<Array<{ label: string; value: string }>>([]);
const productOptions = ref<Array<{ label: string; value: string }>>([]);

// Raw period list from backend
const allPeriods = ref<string[]>([]);

function updateSize() {
  isSmall.value = window.innerWidth < 1024;
}

const showAssistant = computed(() => !isSmall.value);

const assistantContext = computed(() => ({
  period: period.value,
  department: selectedMarketLine.value,
  product: selectedProduct.value,
  period_compare_type: periodCompareType.value,
  active_section: 'overview' as string,
}));

// Year change → update month options and select latest month
watch(selectedYear, () => {
  const monthMap = new Map<string, string[]>();
  for (const p of allPeriods.value) {
    if (p.includes('-')) {
      const [y, m] = p.split('-');
      if (!monthMap.has(y)) monthMap.set(y, []);
      monthMap.get(y)!.push(m);
    }
  }
  const months = monthMap.get(selectedYear.value || '') || [];
  monthOptions.value = [...new Set(months)].sort().reverse().map((v) => ({ label: v + '月', value: v }));
  selectedMonth.value = monthOptions.value.length ? monthOptions.value[0].value : undefined;
});

async function fetchFilterOptions() {
  loading.value = true;
  try {
    // Period options → extract years and months
    const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
    const periods = ((periodResp.data as any)?.options || []) as string[];
    allPeriods.value = periods;

    // Extract unique years
    const years = new Set<string>();
    const monthMap = new Map<string, Set<string>>();
    for (const p of periods) {
      if (p.includes('-')) {
        const [y, m] = p.split('-');
        years.add(y);
        if (!monthMap.has(y)) monthMap.set(y, new Set());
        monthMap.get(y)!.add(m);
      }
    }
    yearOptions.value = [...years].sort().reverse().map((v) => ({ label: v + '年', value: v }));

    // Default: select latest year
    if (yearOptions.value.length && !selectedYear.value) {
      selectedYear.value = yearOptions.value[0].value;
    }

    // Update month options based on selected year
    function updateMonths() {
      const months = monthMap.get(selectedYear.value || '') || new Set<string>();
      monthOptions.value = [...months].sort().reverse().map((v) => ({ label: v + '月', value: v }));
    }
    updateMonths();

    // Default: select latest month
    if (monthOptions.value.length && !selectedMonth.value) {
      selectedMonth.value = monthOptions.value[0].value;
    }

    // Market line (department) options
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
