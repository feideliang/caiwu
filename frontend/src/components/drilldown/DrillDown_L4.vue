<template>
  <a-card class="drilldown-l4" size="small">
    <template #title>
      <a-space>
        <FileOutlined /> L4 - 交易明细
        <a-tag v-if="productName" color="purple">{{ productName }}</a-tag>
      </a-space>
    </template>

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && records.length === 0" description="该产品下暂无交易记录" />
      <a-table
        v-else
        :columns="columns"
        :data-source="records"
        :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
        size="small"
        row-key="id"
        :customRow="(record: DrillRecord) => ({ onClick: () => onRecordClick(record) })"
      />
    </a-spin>

    <!-- Record detail modal -->
    <a-modal
      v-model:open="detailVisible"
      title="交易详情"
      :footer="null"
      width="600px"
    >
      <a-descriptions v-if="selectedRecord" :column="1" size="small" bordered>
        <a-descriptions-item
          v-for="(val, key) in selectedRecord.fields"
          :key="key"
          :label="formatKey(key)"
        >
          {{ formatValue(val) }}
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import { getDrillRecordsByProduct, getRecord } from '@/api/drilldowns';
import type { DrillRecord } from '@/types/drilldown';
import { FileOutlined } from '@ant-design/icons-vue';

const props = defineProps<{
  reportId: string;
  departmentId?: number;
  departmentName?: string;
  productId?: number;
  productName?: string;
  recordId?: number;
  recordTitle?: string;
}>();

const loading = ref(false);
const records = ref<DrillRecord[]>([]);
const detailVisible = ref(false);
const selectedRecord = ref<DrillRecord | null>(null);

const columns: TableColumnsType = [
  { title: '交易号', dataIndex: 'id', key: 'id', width: 80 },
  { title: '摘要', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '子项数', dataIndex: 'children_count', key: 'children_count', width: 80 },
  {
    title: '操作',
    key: 'action',
    width: 80,
    customRender: () => '查看',
  },
];

async function onRecordClick(record: DrillRecord) {
  try {
    const { data } = await getRecord(record.id);
    const raw = data.data as Record<string, unknown>;
    // Flatten tags into fields for display
    selectedRecord.value = {
      ...record,
      fields: {
        record_id: raw.record_id,
        period: raw.period,
        entity: raw.entity,
        metric_name: raw.metric_name,
        metric_value: raw.metric_value,
        ...(raw.tags as Record<string, unknown>),
      },
    };
    detailVisible.value = true;
  } catch {
    selectedRecord.value = record;
    detailVisible.value = true;
  }
}

function formatKey(key: string): string {
  const labels: Record<string, string> = {
    record_id: '交易编号',
    period: '期间',
    entity: '所属部门',
    metric_name: '产品名称',
    metric_value: '金额',
    transaction_no: '交易号',
    date: '日期',
    customer: '客户',
    contract_no: '合同编号',
    region: '地区',
    status: '状态',
    payment_terms: '付款条件',
    invoice_status: '发票状态',
  };
  return labels[key] || key;
}

function formatValue(val: unknown): string {
  if (typeof val === 'number') return val.toFixed(2);
  return String(val ?? '-');
}

onMounted(async () => {
  loading.value = true;
  try {
    if (props.recordId) {
      // L4 with specific record: fetch single record
      const { data } = await getRecord(props.recordId);
      const record = data.data as DrillRecord;
      records.value = [record];
    } else if (props.departmentId && props.productId) {
      const { data } = await getDrillRecordsByProduct(props.reportId, props.departmentId, props.productId);
      const wrapper = data.data as { records?: DrillRecord[] };
      records.value = wrapper.records || [];
    }
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped lang="less">
.drilldown-l4 {
  border-radius: 8px;
}
</style>
