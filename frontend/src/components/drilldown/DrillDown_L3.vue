<template>
  <a-card class="drilldown-l3" size="small">
    <template #title>
      <a-space>
        <AppstoreOutlined /> L3 - 产品交易
        <a-tag v-if="productName" color="orange">{{ productName }}</a-tag>
      </a-space>
    </template>

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && records.length === 0" description="该产品下暂无交易记录" />
      <a-table
        v-else
        :columns="columns"
        :data-source="records"
        :pagination="{ pageSize: 10, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
        size="small"
        row-key="id"
        :customRow="(record: DrillRecord) => ({ onClick: () => onRecordClick(record) })"
      />
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import { getDrillRecordsByProduct } from '@/api/drilldowns';
import type { DrillRecord } from '@/types/drilldown';
import { AppstoreOutlined } from '@ant-design/icons-vue';

const props = defineProps<{
  reportId: string;
  departmentId?: number;
  departmentName?: string;
  productId?: number;
  productName?: string;
}>();

const emit = defineEmits<{
  navigate: [level: 4, params: Record<string, unknown>];
}>();

const loading = ref(false);
const records = ref<DrillRecord[]>([]);

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

function onRecordClick(record: DrillRecord) {
  emit('navigate', 4, {
    department_id: props.departmentId,
    department_name: props.departmentName,
    product_id: props.productId,
    product_name: props.productName,
    record_id: record.id,
    record_title: record.title
  });
}

onMounted(async () => {
  loading.value = true;
  try {
    if (props.departmentId && props.productId) {
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
.drilldown-l3 {
  border-radius: 8px;
}
</style>
