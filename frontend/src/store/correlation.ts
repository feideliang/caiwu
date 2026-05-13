import { defineStore } from 'pinia';
import { ref } from 'vue';
import { analyzeCorrelations, getCorrelations, calibrateCorrelation as apiCalibrate } from '@/api/correlations';
import type { CorrelationAnalysisResult, CorrelationRecord, CalibrationStatus, CalibrationRequest } from '@/types/correlation';

export const useCorrelationStore = defineStore('correlation', () => {
  const records = ref<CorrelationRecord[]>([]);
  const loading = ref(false);
  const lastResult = ref<CorrelationAnalysisResult | null>(null);

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true;
    try {
      const { data } = await getCorrelations(params);
      const payload = data.data as { items?: CorrelationRecord[] };
      records.value = payload.items || [];
    } finally {
      loading.value = false;
    }
  }

  async function analyze(metricA?: string, metricB?: string, periodStart?: string, periodEnd?: string) {
    loading.value = true;
    try {
      const { data } = await analyzeCorrelations({
        metric_a: metricA || '',
        metric_b: metricB || '',
        period_start: periodStart,
        period_end: periodEnd,
        request_ai_explanation: true,
      });
      lastResult.value = data.data as CorrelationAnalysisResult;
      return lastResult.value;
    } finally {
      loading.value = false;
    }
  }

  async function calibrate(id: number, req: CalibrationRequest) {
    const { data } = await apiCalibrate(id, req);
    const record = records.value.find((r) => r.id === id);
    if (record) {
      record.calibration_status = data.data.calibration_status as CalibrationStatus | null;
      record.calibrated_at = data.data.calibrated_at;
    }
    return data.data as CorrelationRecord;
  }

  function clearResult() {
    lastResult.value = null;
  }

  return { records, loading, lastResult, fetchRecords, analyze, calibrate, clearResult };
});
