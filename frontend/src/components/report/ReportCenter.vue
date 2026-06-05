<template>
  <a-card class="report-center" :bordered="false">
    <template #title>
      <a-space>
        <FileTextOutlined /> 报告中心
      </a-space>
    </template>
    <template #extra>
      <a-button type="primary" size="small" @click="showCreateModal = true">
        <PlusOutlined /> 新建报告
      </a-button>
    </template>

    <!-- Report task list -->
    <a-table
      :columns="columns"
      :data-source="reportStore.reports"
      :loading="reportStore.loading"
      :pagination="{ pageSize: 10, showTotal: (t: number) => `共 ${t} 条` }"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <!-- Report type label -->
        <template v-if="column.key === 'report_type'">
          <a-tag>{{ reportTypeLabels[record.report_type] || record.report_type }}</a-tag>
        </template>

        <!-- Derived title from report_type + period -->
        <template v-if="column.key === 'title'">
          <span>{{ record.file_name || `${reportTypeLabels[record.report_type] || record.report_type}${record.period ? ' - ' + record.period : ''}` }}</span>
        </template>

        <!-- Status badge -->
        <template v-if="column.key === 'status'">
          <a-badge :status="statusBadge(record.status)" :text="statusLabel(record.status)" />
        </template>

        <!-- Step progress indicator -->
        <template v-if="column.key === 'progress'">
          <a-steps :current="currentStep(record)" size="small" :items="stepItems" direction="vertical" />
        </template>

        <!-- Actions -->
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button
              v-if="canCancel(record.status)"
              type="link"
              danger
              size="small"
              :loading="cancellingId === record.id"
              @click="handleCancel(record.id)"
            >
              取消
            </a-button>
            <a-button
              v-if="record.status === 'failed'"
              type="link"
              size="small"
              :loading="retryingId === record.id"
              @click="handleRetry(record.id)"
            >
              重试
            </a-button>
            <a-button
              v-if="record.status === 'completed' && record.file_path"
              type="link"
              size="small"
              @click="handleDownload(record.id)"
            >
              下载
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- Create report modal -->
    <a-modal
      v-model:open="showCreateModal"
      title="新建报告"
      @ok="handleCreate"
      :confirm-loading="creating"
    >
      <a-form :model="createForm" layout="vertical">
        <a-form-item label="报告类型" required>
          <a-select v-model:value="createForm.type" placeholder="选择报告类型">
            <a-select-option value="revenue_daily">收入日报</a-select-option>
            <a-select-option value="gross_profit_daily">毛利日报</a-select-option>
            <a-select-option value="department_daily">部门经营日报</a-select-option>
            <a-select-option value="product_bgbu_daily">产品线分析日报</a-select-option>
            <a-select-option value="custom">自定义</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="报告标题">
          <a-input v-model:value="createForm.title" placeholder="可选，留空自动生成" />
        </a-form-item>
        <a-form-item label="日期范围" required>
          <a-range-picker v-model:value="createForm.dateRange" value-format="YYYY-MM-DD" />
        </a-form-item>
        <a-form-item label="导出格式" required>
          <a-radio-group v-model:value="createForm.format">
            <a-radio-button value="word">Word</a-radio-button>
            <a-radio-button value="pdf">PDF</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="包含图表">
          <a-switch v-model:checked="createForm.include_charts" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { useReportStore } from '@/store/report';
import type { ReportType, ReportStatus, ReportFormat } from '@/types/report';
import type { TableColumnsType } from 'ant-design-vue';
import { FileTextOutlined, PlusOutlined } from '@ant-design/icons-vue';
import dayjs from 'dayjs';

const reportStore = useReportStore();
const showCreateModal = ref(false);
const creating = ref(false);
const cancellingId = ref<number | null>(null);
const retryingId = ref<number | null>(null);

const createForm = ref({
  type: 'revenue_daily' as ReportType,
  title: '',
  dateRange: [dayjs().subtract(1, 'month').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')] as [string, string],
  format: 'word' as ReportFormat,
  include_charts: true,
});

let pollingTimer: ReturnType<typeof setInterval> | null = null;

const stepItems = [
  { title: '数据采集' },
  { title: 'AI分析' },
  { title: '文档生成' },
  { title: '完成' },
];

const reportTypeLabels: Record<string, string> = {
  revenue_daily: '收入日报',
  gross_profit_daily: '毛利日报',
  department_daily: '部门经营日报',
  product_bgbu_daily: '产品线分析日报',
  custom: '自定义',
};

const columns: TableColumnsType = [
  { title: '类型', dataIndex: 'report_type', key: 'report_type', width: 80 },
  { title: '标题', key: 'title', ellipsis: true },
  { title: '状态', key: 'status', width: 120 },
  { title: '进度', key: 'progress', width: 200 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 160 },
];

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    pending: 'default',
    generating: 'processing',
    running: 'processing',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
  };
  return map[status] || 'default';
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    generating: '生成中',
    running: '生成中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return map[status] || status;
}

function currentStep(report: { status: ReportStatus; current_step?: number }): number {
  if (report.current_step !== undefined) return report.current_step;
  const stepMap: Record<ReportStatus, number> = {
    pending: 0,
    generating: 1,
    running: 1,
    completed: 3,
    failed: -1,
    cancelled: -1,
  };
  return stepMap[report.status] ?? 0;
}

function canCancel(status: string): boolean {
  return status === 'pending' || status === 'generating' || status === 'running';
}

async function handleCreate() {
  if (!createForm.value.dateRange || createForm.value.dateRange.length < 2) return;
  creating.value = true;
  try {
    await reportStore.create({
      type: createForm.value.type,
      title: createForm.value.title || undefined,
      date_from: createForm.value.dateRange[0],
      date_to: createForm.value.dateRange[1],
      format: createForm.value.format,
      include_charts: createForm.value.include_charts,
    });
    showCreateModal.value = false;
    message.success('报告已提交，正在生成中...');
    createForm.value = {
      type: 'revenue_daily',
      title: '',
      dateRange: [dayjs().subtract(1, 'month').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
      format: 'word',
      include_charts: true,
    };
  } finally {
    creating.value = false;
  }
}

async function handleCancel(id: number) {
  cancellingId.value = id;
  try {
    await reportStore.cancel(id);
  } finally {
    cancellingId.value = null;
  }
}

async function handleRetry(id: number) {
  retryingId.value = id;
  try {
    await reportStore.retry(id);
  } finally {
    retryingId.value = null;
  }
}

function handleDownload(id: number) {
  reportStore.download(id);
}

// Polling: 5s interval, pause when tab is hidden
function startPolling() {
  stopPolling();
  pollingTimer = setInterval(() => {
    if (document.hidden) return;
    const hasRunning = reportStore.reports.some(
      (r) => r.status === 'pending' || r.status === 'generating' || r.status === 'running',
    );
    if (hasRunning) {
      reportStore.fetchReports();
    }
  }, 5000);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

onMounted(() => {
  reportStore.fetchReports();
  startPolling();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling();
    }
  });
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped lang="less">
.report-center {
  border-radius: 8px;
}
</style>
