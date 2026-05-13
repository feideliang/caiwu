<template>
  <a-card class="drilldown-l2" size="small">
    <template #title>
      <a-space>
        <ApartmentOutlined /> L2 - 部门产品
        <a-tag v-if="departmentName" color="green">{{ departmentName }}</a-tag>
      </a-space>
    </template>

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && products.length === 0" description="该部门下暂无产品" />
      <a-table
        v-else
        :columns="columns"
        :data-source="products"
        :pagination="{ pageSize: 10, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
        size="small"
        row-key="id"
        :customRow="(record: DrillProduct) => ({ onClick: () => onProductClick(record) })"
      />
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import { getDrillProductsByDept } from '@/api/drilldowns';
import type { DrillProduct } from '@/types/drilldown';
import { ApartmentOutlined } from '@ant-design/icons-vue';

const props = defineProps<{
  reportId: string;
  departmentId?: number;
  departmentName?: string;
}>();

const emit = defineEmits<{
  navigate: [level: 3, params: Record<string, unknown>];
}>();

const loading = ref(false);
const products = ref<DrillProduct[]>([]);

const columns: TableColumnsType = [
  { title: '产品名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '收入', dataIndex: 'revenue', key: 'revenue' },
  { title: '成本', dataIndex: 'cost', key: 'cost' },
  {
    title: '毛利率',
    dataIndex: 'margin',
    key: 'margin',
    customRender: ({ text }: { text: number }) => `${(text * 100).toFixed(2)}%`,
  },
  { title: '销量', dataIndex: 'sales_count', key: 'sales_count' },
];

function onProductClick(row: DrillProduct) {
  emit('navigate', 3, { department_id: props.departmentId, department_name: props.departmentName, product_id: row.id, product_name: row.name });
}

onMounted(async () => {
  loading.value = true;
  try {
    if (props.departmentId) {
      const { data } = await getDrillProductsByDept(props.reportId, props.departmentId);
      products.value = data.data as DrillProduct[];
    }
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped lang="less">
.drilldown-l2 {
  border-radius: 8px;
}
</style>
