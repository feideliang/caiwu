<template>
  <a-space direction="vertical" style="width: 100%" :size="16">
    <a-alert
      type="info"
      show-icon
      message="邮件同步"
      description="可在此测试 IMAP 连通性、手动触发同步，并查看最近批次。"
    />

    <a-card size="small" title="同步控制">
      <a-space wrap>
        <a-select v-model:value="selectedSourceId" style="width: 280px" placeholder="选择邮件数据源">
          <a-select-option v-for="source in emailSources" :key="source.id" :value="source.id">
            {{ source.name }}
          </a-select-option>
        </a-select>
        <a-button :loading="testing" @click="handleTestConnection">测试连接</a-button>
        <a-button type="primary" :loading="syncing" @click="handleRunSync">立即同步</a-button>
        <a-button :loading="retrying" :disabled="!selectedBatch" @click="handleRetry">重试选中</a-button>
      </a-space>
    </a-card>

    <a-card size="small" title="最近同步批次">
      <a-table :dataSource="batches" :loading="loading" rowKey="id" :pagination="false" size="small" :row-selection="{ selectedRowKeys: selectedBatchKeys, onChange: onSelectBatch }">
        <a-table-column title="批次号" dataIndex="batch_no" />
        <a-table-column title="状态" dataIndex="status">
          <template #default="{ text }"><a-tag :color="statusColor(text)">{{ text }}</a-tag></template>
        </a-table-column>
        <a-table-column title="来源ID" dataIndex="source_id" />
        <a-table-column title="记录数" dataIndex="record_count" />
        <a-table-column title="文件" dataIndex="file_name" />
        <a-table-column title="处理时间" dataIndex="processed_at" />
      </a-table>
    </a-card>
  </a-space>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { getDataSources, type DataSourceItem } from '@/api/dataManagement';
import { getEmailSyncBatches, runEmailSync, testEmailConnection, retryEmailSyncBatch, type EmailSyncBatch } from '@/api/dataSync';

const loading = ref(false);
const syncing = ref(false);
const testing = ref(false);
const retrying = ref(false);
const batches = ref<EmailSyncBatch[]>([]);
const sources = ref<DataSourceItem[]>([]);
const selectedSourceId = ref<number | undefined>(undefined);
const selectedBatchKeys = ref<(string | number)[]>([]);
const selectedBatch = computed(() => batches.value.find((b) => selectedBatchKeys.value.includes(b.id)));

function onSelectBatch(keys: (string | number)[]) { selectedBatchKeys.value = keys; }

const emailSources = computed(() => sources.value.filter((s) => s.source_type === 'email_imap'));

function statusColor(status: string): string {
  if (status === 'success') return 'green';
  if (status === 'running') return 'blue';
  if (status === 'failed') return 'red';
  return 'default';
}

async function loadSources() {
  const { data } = await getDataSources();
  const payload = data.data as { items?: DataSourceItem[] } | undefined;
  sources.value = payload?.items || [];
  if (!selectedSourceId.value) {
    selectedSourceId.value = emailSources.value[0]?.id;
  }
}

async function loadBatches() {
  loading.value = true;
  try {
    const { data } = await getEmailSyncBatches({ page: 1, page_size: 20 });
    const payload = data.data as { items?: EmailSyncBatch[] } | undefined;
    batches.value = payload?.items || [];
  } finally {
    loading.value = false;
  }
}

async function handleTestConnection() {
  testing.value = true;
  try {
    await testEmailConnection(selectedSourceId.value);
    message.success('连接成功');
  } finally {
    testing.value = false;
  }
}

async function handleRunSync() {
  syncing.value = true;
  try {
    await runEmailSync();
    message.success('已触发同步');
    await loadBatches();
  } finally {
    syncing.value = false;
  }
}

async function handleRetry() {
  const batch = selectedBatch.value;
  if (!batch) return;
  retrying.value = true;
  try {
    await retryEmailSyncBatch(batch.id);
    message.success('已重试');
    await loadBatches();
  } finally {
    retrying.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadSources(), loadBatches()]);
});
</script>
