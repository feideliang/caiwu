import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { DrillDownState, DrillLevel, DrillBreadcrumb } from '@/types/drilldown';

export const useDrilldownStore = defineStore('drilldown', () => {
  const state = ref<DrillDownState>({
    report_id: '',
    current_level: 1,
    breadcrumbs: [{ label: '总览', level: 1, params: {} }],
    params: {},
  });

  const metric = ref<string>('');
  const ruleCode = ref<string>('');
  const dimension = ref<string>('');
  const dimensionValue = ref<string>('');

  const breadcrumbs = computed(() => state.value.breadcrumbs);
  const currentLevel = computed(() => state.value.current_level);
  const isMobileDrillDisabled = computed(() => {
    return window.innerWidth < 768 && state.value.current_level > 1;
  });

  function init(reportId: string, opts?: { metric?: string; rule_code?: string; dimension?: string; dimension_value?: string }) {
    if (opts) {
      if (opts.metric !== undefined) metric.value = opts.metric;
      if (opts.rule_code !== undefined) ruleCode.value = opts.rule_code;
      if (opts.dimension !== undefined) dimension.value = opts.dimension;
      if (opts.dimension_value !== undefined) dimensionValue.value = opts.dimension_value;
    }
    if (state.value.report_id) return;
    state.value = {
      report_id: reportId,
      current_level: 1,
      breadcrumbs: [{ label: '总览', level: 1, params: {} }],
      params: {},
    };
  }

  function push(level: DrillLevel, label: string, params: DrillBreadcrumb['params']) {
    state.value.breadcrumbs.push({ label, level, params });
    state.value.current_level = level;
    state.value.params = params;
    if (params.metric) metric.value = params.metric;
    if (params.rule_code) ruleCode.value = params.rule_code;
    if (params.dimension) dimension.value = params.dimension;
    if (params.dimension_value) dimensionValue.value = params.dimension_value;
  }

  function popTo(level: DrillLevel) {
    const idx = state.value.breadcrumbs.findIndex((b) => b.level === level);
    if (idx >= 0) {
      state.value.breadcrumbs = state.value.breadcrumbs.slice(0, idx + 1);
      state.value.current_level = level;
      state.value.params = state.value.breadcrumbs[idx]?.params || {};
    }
  }

  function reset() {
    state.value = {
      report_id: '',
      current_level: 1,
      breadcrumbs: [{ label: '总览', level: 1, params: {} }],
      params: {},
    };
    metric.value = '';
    ruleCode.value = '';
    dimension.value = '';
    dimensionValue.value = '';
  }

  return { state, breadcrumbs, currentLevel, isMobileDrillDisabled, metric, ruleCode, dimension, dimensionValue, init, push, popTo, reset };
});
