<template>
  <div class="dashboard-page">
    <!-- Filter bar: 周期维度 + 筛选周期 + 市场线 + 产品线 -->
    <div class="dashboard-header">
      <a-space wrap>
        <a-select v-model:value="periodDimension" style="width: 120px" placeholder="周期维度">
          <a-select-option value="monthly">月度</a-select-option>
          <a-select-option value="weekly">季度</a-select-option>
          <a-select-option value="yearly">年累计</a-select-option>
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
const periodDimension = ref<string>('monthly'); // monthly / weekly / yearly / custom
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

// Derived period for simple month filter (monthly mode)
// For yearly mode, period is a year string like "2026"
const period = computed(() => {
  if (periodDimension.value === 'monthly') {
    return selectedPeriod.value;
  }
  if (periodDimension.value === 'yearly') {
    // Return year only for yearly mode
    return selectedPeriod.value ? selectedPeriod.value.slice(0, 4) : undefined;
  }
  if (periodDimension.value === 'weekly') {
    return undefined; // handled by periodStart/periodEnd
  }
  return undefined;
});

// Dynamic period select options based on dimension
const periodSelectOptions = computed<Array<{ label: string; value: string }>>(() => {
  if (periodDimension.value === 'weekly') {
    // Generate week options from months: each month → ~4 weeks
    const weeks: Array<{ label: string; value: string }> = [];
    const monthSet = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const [y, m] = p.split('-');
        monthSet.add(`${y}-${m}`);
      }
    }
    for (const ym of [...monthSet].sort().reverse()) {
      const [y, m] = ym.split('-');
      const monthNum = parseInt(m);
      // Each month generates 4 week slots
      for (let w = 1; w <= 4; w++) {
        const weekLabel = `${y}年${monthNum}月第${w}周`;
        const weekValue = `${y}-W${(monthNum - 1) * 4 + w}`;
        weeks.push({ label: weekLabel, value: weekValue });
      }
    }
    return weeks;
  }
  if (periodDimension.value === 'yearly') {
    // Year options only: "2026年" etc.
    const years = new Set<string>();
    for (const p of allPeriods.value) {
      if (p.includes('-')) {
        const y = p.split('-')[0];
        years.add(y);
      }
    }
    return [...years].sort().reverse().map((y) => ({ label: `${y}年`, value: `${y}` }));
  }
  // monthly: month options like "2026年1月"
  const months = new Set<string>();
  for (const p of allPeriods.value) {
    if (p.includes('-')) {
      const [y, m] = p.split('-');
      months.add(`${y}-${m}`);
    }
  }
  return [...months].sort().reverse().map((v) => {
    const [y, m] = v.split('-');
    return { label: `${y}年${parseInt(m)}月`, value: `${y}-${m.padStart(2, '0')}` };
  });
});

function onCustomRangeChange(dates: any) {
  if (dates && dates[0] && dates[1]) {
    const fmt = (d: any) => {
      if (!d) return '';
      const y = d.year?.() ?? d.getFullYear();
      const mo = d.month?.() ?? (d.getMonth() + 1);
      return `${y}-${String(mo + 1).padStart(2, '0')}`;
    };
    periodStart.value = fmt(dates[0]);
    periodEnd.value = fmt(dates[1]);
  } else {
    periodStart.value = undefined;
    periodEnd.value = undefined;
  }
}

// Update periodStart/periodEnd when selectedPeriod changes
watch([selectedPeriod, periodDimension], () => {
  if (!selectedPeriod.value) {
    periodStart.value = undefined;
    periodEnd.value = undefined;
    return;
  }
  if (periodDimension.value === 'weekly') {
    // Convert week value like "2026-W5" to a month range
    const match = selectedPeriod.value.match(/^(\d{4})-W(\d+)$/);
    if (match) {
      const y = match[1];
      const w = parseInt(match[2]);
      const month = Math.min(12, Math.ceil(w / 4));
      periodStart.value = `${y}-${String(month).padStart(2, '0')}`;
      periodEnd.value = `${y}-${String(month).padStart(2, '0')}`;
    }
  } else if (periodDimension.value === 'monthly') {
    periodStart.value = selectedPeriod.value;
    periodEnd.value = undefined;
  } else if (periodDimension.value === 'yearly') {
    // Full year range: selectedPeriod is "2026"
    const y = selectedPeriod.value.slice(0, 4);
    periodStart.value = `${y}-01`;
    periodEnd.value = `${y}-12`;
  }
});

// When dimension changes, reset period selection
watch(periodDimension, () => {
  selectedPeriod.value = periodSelectOptions.value.length ? periodSelectOptions.value[0].value : undefined;
});

function updateSize() {
  isSmall.value = window.innerWidth < 1024;
}

const showAssistant = computed(() => !isSmall.value);

const assistantContext = computed(() => ({
  period: period.value,
  department: selectedMarketLine.value,
  product: selectedProduct.value,
  period_dimension: periodDimension.value,
  active_section: 'overview' as string,
}));

async function fetchFilterOptions() {
  loading.value = true;
  try {
    const { data: periodResp } = await getFilterOptions({ dimension: 'period' });
    const periods = ((periodResp.data as any)?.options || []) as string[];
    allPeriods.value = periods;

    // Default: select latest period
    if (!selectedPeriod.value && allPeriods.value.length) {
      if (periodDimension.value === 'yearly') {
        // Extract year from latest period
        const latest = allPeriods.value[allPeriods.value.length - 1];
        selectedPeriod.value = latest.includes('-') ? latest.slice(0, 4) : latest;
      } else {
        selectedPeriod.value = allPeriods.value[allPeriods.value.length - 1];
      }
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
