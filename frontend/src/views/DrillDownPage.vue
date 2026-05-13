<template>
  <div class="drilldown-page">
    <!-- Metric/Rule context header -->
    <a-card v-if="drilldownStore.metric || drilldownStore.ruleCode" size="small" class="metric-header">
      <a-space>
        <a-tag v-if="drilldownStore.metric" color="blue">指标：{{ drilldownStore.metric }}</a-tag>
        <a-tag v-if="drilldownStore.ruleCode" color="orange">规则：{{ drilldownStore.ruleCode }}</a-tag>
        <a-tag v-if="drilldownStore.dimension">维度：{{ drilldownStore.dimension }}</a-tag>
        <a-tag v-if="drilldownStore.dimensionValue">值：{{ drilldownStore.dimensionValue }}</a-tag>
      </a-space>
    </a-card>

    <!-- Breadcrumb navigation -->
    <a-breadcrumb class="breadcrumb" separator=">">
      <a-breadcrumb-item v-for="crumb in drilldownStore.breadcrumbs" :key="crumb.level">
        <a @click="navigateTo(crumb.level)">{{ crumb.label }}</a>
      </a-breadcrumb-item>
    </a-breadcrumb>

    <!-- Level components -->
    <DrillDown_L1
      v-if="drilldownStore.currentLevel === 1"
      :report-id="reportId"
      @navigate="onNavigate"
    />
    <DrillDown_L2
      v-if="drilldownStore.currentLevel === 2"
      :report-id="reportId"
      :department-id="drilldownStore.state.params.department_id"
      :department-name="drilldownStore.state.params.department_name"
      @navigate="onNavigate"
    />
    <DrillDown_L3
      v-if="drilldownStore.currentLevel === 3"
      :report-id="reportId"
      :department-id="drilldownStore.state.params.department_id"
      :department-name="drilldownStore.state.params.department_name"
      :product-id="drilldownStore.state.params.product_id"
      :product-name="drilldownStore.state.params.product_name"
      @navigate="onNavigate"
    />
    <DrillDown_L4
      v-if="drilldownStore.currentLevel === 4"
      :report-id="reportId"
      :department-id="drilldownStore.state.params.department_id"
      :department-name="drilldownStore.state.params.department_name"
      :product-id="drilldownStore.state.params.product_id"
      :product-name="drilldownStore.state.params.product_name"
      :record-id="drilldownStore.state.params.record_id"
      :record-title="drilldownStore.state.params.record_title"
    />

    <!-- Empty state for invalid level -->
    <a-result v-if="drilldownStore.currentLevel < 1 || drilldownStore.currentLevel > 4" status="404" title="无效的钻取层级" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDrilldownStore } from '@/store/drilldown';
import DrillDown_L1 from '@/components/drilldown/DrillDown_L1.vue';
import DrillDown_L2 from '@/components/drilldown/DrillDown_L2.vue';
import DrillDown_L3 from '@/components/drilldown/DrillDown_L3.vue';
import DrillDown_L4 from '@/components/drilldown/DrillDown_L4.vue';

const route = useRoute();
const router = useRouter();
const drilldownStore = useDrilldownStore();

const reportId = computed(() => (route.params.report_id as string) || '2026-03');

function onNavigate(level: number, params: Record<string, unknown>) {
  const labels: Record<number, string> = {
    1: '总览',
    2: (params.department_name as string) || (params.product_name as string) || '部门详情',
    3: (params.record_title as string) || '产品详情',
    4: '交易明细',
  };
  drilldownStore.push(level as 1 | 2 | 3 | 4, labels[level] || `L${level}`, params);

  const query: Record<string, string> = { level: String(level) };
  if (params.department_id) query.drill_type = 'department';
  if (params.product_id) query.drill_type = 'product';
  if (params.department_name) query.drill_param = params.department_name as string;
  if (params.product_name) query.drill_param = params.product_name as string;
  if (params.record_title) query.drill_param = params.record_title as string;
  if (params.record_id) query.record_id = String(params.record_id);

  router.push({ name: 'DrillDown', params: { report_id: reportId.value }, query });
}

function navigateTo(level: number) {
  drilldownStore.popTo(level as 1 | 2 | 3 | 4);
  router.push({ name: 'DrillDown', params: { report_id: reportId.value }, query: { level: String(level) } });
}

watch(
  () => route.query.level,
  (level) => {
    const lvl = parseInt(String(level), 10);
    if (lvl >= 1 && lvl <= 4) {
      drilldownStore.popTo(lvl as 1 | 2 | 3 | 4);
    }
  },
);

onMounted(() => {
  const lvl = parseInt(String(route.query.level), 10);

  // Only init on first load (when store state is empty)
  if (!drilldownStore.state.report_id) {
    drilldownStore.init(reportId.value, {
      metric: route.query.metric as string | undefined,
      rule_code: route.query.rule_code as string | undefined,
      dimension: route.query.dimension as string | undefined,
      dimension_value: route.query.dimension_value as string | undefined,
    });
  }

  // If URL specifies a level > 1, rebuild breadcrumbs to that level
  if (lvl && lvl > 1 && lvl <= 4) {
    // Reset and rebuild from URL params
    drilldownStore.state.breadcrumbs = [{ label: '总览', level: 1, params: {} }];
    const params: Record<string, unknown> = {};
    const departmentName = (route.query.department_name as string | undefined) ||
      (route.query.drill_type === 'department' ? (route.query.drill_param as string | undefined) : undefined) ||
      (route.query.dimension === 'department' ? (route.query.dimension_value as string | undefined) : undefined);
    const productName = (route.query.product_name as string | undefined) ||
      (route.query.drill_type === 'product' ? (route.query.drill_param as string | undefined) : undefined) ||
      (route.query.dimension === 'product' ? (route.query.dimension_value as string | undefined) : undefined);
    const recordTitle = (route.query.record_title as string | undefined) ||
      (route.query.dimension === 'record' ? (route.query.dimension_value as string | undefined) : undefined);
    if (departmentName) params.department_name = departmentName;
    if (productName) params.product_name = productName;
    if (recordTitle) params.record_title = recordTitle;
    if (route.query.department_id) params.department_id = route.query.department_id as string;
    if (route.query.product_id) params.product_id = route.query.product_id as string;
    if (route.query.record_id) params.record_id = parseInt(route.query.record_id as string, 10);
    const label = (lvl === 2 ? (departmentName || productName) : lvl === 3 ? (productName || recordTitle) : recordTitle) || `L${lvl}`;
    drilldownStore.push(lvl as 1 | 2 | 3 | 4, label, params);
  }

  if (window.innerWidth < 768 && drilldownStore.currentLevel > 1) {
    router.replace({ name: 'MobileNoDrill' });
  }
});
</script>

<style scoped lang="less">
.drilldown-page {
  .metric-header {
    margin-bottom: 12px;
  }
  .breadcrumb {
    margin-bottom: 16px;

    a {
      cursor: pointer;
      color: var(--color-primary);

      &:hover {
        color: #4096ff;
      }
    }
  }
}
</style>
