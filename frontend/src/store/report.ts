import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getReports, createReport, cancelReport, retryReport } from '@/api/reports';
import type { Report, ReportRequest } from '@/types/report';
import type { PaginatedResult } from '@/types/api';

export const useReportStore = defineStore('report', () => {
  const reports = ref<Report[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const currentReport = ref<Report | null>(null);

  async function fetchReports(params?: Record<string, unknown>) {
    loading.value = true;
    try {
      const { data } = await getReports(params);
      const result = data.data as PaginatedResult<Report>;
      reports.value = result.items;
      total.value = result.total;
    } finally {
      loading.value = false;
    }
  }

  async function create(data: ReportRequest) {
    const backendData = {
      report_type: data.type,
      period: data.date_from.substring(0, 7),  // Extract YYYY-MM from date
      output_format: data.format,
      params: { include_charts: data.include_charts, date_from: data.date_from, date_to: data.date_to },
    };
    const { data: res } = await createReport(backendData as any);
    reports.value.unshift(res.data as unknown as Report);
    return res.data as unknown as Report;
  }

  async function cancel(id: number) {
    await cancelReport(id);
    const r = reports.value.find((r) => r.id === id);
    if (r) r.status = 'cancelled';
  }

  async function retry(id: number) {
    await retryReport(id);
    const r = reports.value.find((r) => r.id === id);
    if (r) r.status = 'pending';
  }

  async function fetchDetail(id: number) {
    const { data } = await getReports({ id });
    currentReport.value = data.data as unknown as Report;
  }

  async function download(id: number) {
    const token = localStorage.getItem('access_token');
    window.open(`/api/v1/reports/${id}/download?token=${token}`, '_blank');
  }

  return { reports, total, loading, currentReport, fetchReports, create, cancel, retry, fetchDetail, download };
});
