<template>
  <div>
    <a-button type="primary" @click="handleAdd" style="margin-bottom: 16px">添加数据源</a-button>
    <a-table :dataSource="dataSource" :loading="loading" rowKey="id" :pagination="{ current: page, pageSize: 20, total }">
      <a-table-column title="名称" dataIndex="name" />
      <a-table-column title="类型" dataIndex="source_type">
        <template #default="{ text }">
          <a-tag :color="sourceTypeColor(text)">{{ sourceTypeLabel(text) }}</a-tag>
        </template>
      </a-table-column>
      <a-table-column title="连接配置" dataIndex="connection_config">
        <template #default="{ text }">
          <span>{{ formatConfig(text) }}</span>
        </template>
      </a-table-column>
      <a-table-column title="优先级" dataIndex="priority" />
      <a-table-column title="状态" dataIndex="is_active">
        <template #default="{ text }"><a-tag :color="text ? 'green' : 'red'">{{ text ? '启用' : '停用' }}</a-tag></template>
      </a-table-column>
      <a-table-column title="最后同步" dataIndex="last_sync_at">
        <template #default="{ text }">{{ text || '从未同步' }}</template>
      </a-table-column>
      <a-table-column title="操作">
        <template #default="{ record }">
          <a-button type="link" @click="handleEdit(record)">编辑</a-button>
          <a-button type="link" danger @click="handleDelete(record.id)">删除</a-button>
        </template>
      </a-table-column>
    </a-table>

    <a-modal v-model:visible="modalVisible" :title="isEdit ? '编辑数据源' : '添加数据源'" @ok="handleSave">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="editing.source_type">
            <a-select-option value="email_imap">邮件IMAP</a-select-option>
            <a-select-option value="bi_platform">BI平台</a-select-option>
            <a-select-option value="erp">ERP</a-select-option>
            <a-select-option value="internal_system">内部系统</a-select-option>
            <a-select-option value="excel">Excel上传</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级"><a-input-number v-model:value="editing.priority" :min="0" style="width: 100%" /></a-form-item>
        <a-form-item label="启用"><a-switch v-model:checked="editing.is_active" /></a-form-item>
        <a-form-item label="连接配置(JSON)">
          <a-textarea v-model:value="editing.connection_config_text" :rows="8" placeholder='{"host":"imap.example.com","port":993}' />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { getDataSources, createDataSource, updateDataSource, deleteDataSource } from '../../api/dataManagement';
import type { DataSourceItem } from '../../api/dataManagement';

type DataSourceForm = Partial<DataSourceItem> & { connection_config_text: string };

const dataSource = ref<DataSourceItem[]>([]);
const loading = ref(false);
const modalVisible = ref(false);
const editing = ref<DataSourceForm>({ name: '', source_type: 'email_imap', is_active: true, priority: 0, connection_config_text: '{}' });
const isEdit = ref(false);
const page = ref(1);
const total = ref(0);

function sourceTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    email_imap: '邮件IMAP',
    bi_platform: 'BI平台',
    erp: 'ERP',
    internal_system: '内部系统',
    excel: 'Excel上传',
  };
  return labels[value] || value;
}

function sourceTypeColor(value: string): string {
  if (value === 'email_imap') return 'blue';
  if (value === 'bi_platform') return 'green';
  if (value === 'erp') return 'purple';
  if (value === 'internal_system') return 'orange';
  return 'default';
}

function formatConfig(config: unknown): string {
  if (!config) return '—';
  if (typeof config === 'string') return config;
  try {
    const text = JSON.stringify(config);
    return text.length > 24 ? `${text.slice(0, 24)}...` : text;
  } catch {
    return '—';
  }
}

const loadData = async () => {
  loading.value = true;
  try {
    const r = await getDataSources();
    const d = r.data?.data as { items?: DataSourceItem[]; total?: number } | undefined;
    dataSource.value = d?.items || [];
    total.value = d?.total || 0;
  } finally {
    loading.value = false;
  }
};

const handleAdd = () => {
  isEdit.value = false;
  editing.value = { name: '', source_type: 'email_imap', is_active: true, priority: 0, connection_config_text: '{}' };
  modalVisible.value = true;
};

const handleEdit = (record: DataSourceItem) => {
  isEdit.value = true;
  editing.value = {
    ...record,
    connection_config_text: JSON.stringify(record.connection_config || {}, null, 2),
  };
  modalVisible.value = true;
};

const handleSave = async () => {
  let connectionConfig: Record<string, unknown> | null = null;
  try {
    const raw = editing.value.connection_config_text?.trim() || '{}';
    connectionConfig = raw ? JSON.parse(raw) : null;
  } catch {
    message.error('连接配置不是有效 JSON');
    return;
  }

  const payload = {
    name: editing.value.name,
    source_type: editing.value.source_type,
    is_active: editing.value.is_active,
    priority: editing.value.priority,
    connection_config: connectionConfig,
  };

  try {
    if (isEdit.value && editing.value.id) {
      await updateDataSource(editing.value.id, payload);
    } else {
      await createDataSource(payload);
    }
    message.success(isEdit.value ? '已更新' : '已创建');
    modalVisible.value = false;
    await loadData();
  } catch {
    message.error('操作失败');
  }
};

const handleDelete = (id: number) => {
  Modal.confirm({
    title: '确认删除？',
    onOk: async () => {
      await deleteDataSource(id);
      message.success('已删除');
      await loadData();
    },
  });
};

onMounted(loadData);
</script>
