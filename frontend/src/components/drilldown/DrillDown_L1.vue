<template>
  <a-card class="drilldown-l1" size="small">
    <template #title>
      <a-space>
        <HomeOutlined /> L1 - 总览
        <a-tag color="blue">{{ summary?.title }}</a-tag>
      </a-space>
    </template>

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && !summary" description="暂无数据" />
      <template v-if="summary">
        <!-- Metrics summary -->
        <a-row :gutter="[16, 16]" class="metrics-row">
          <a-col v-for="(val, key) in (summary.metrics ?? {})" :key="key" :xs="12" :md="6">
            <a-statistic :title="formatKey(key)" :value="formatMetric(key, val)" :precision="formatPrecision(key)" />
          </a-col>
        </a-row>

        <!-- Department breakdown -->
        <div v-if="summary.departments?.length" class="section">
          <h4>部门维度</h4>
          <a-table
            :columns="deptColumns"
            :data-source="summary.departments"
            :pagination="false"
            size="small"
            row-key="id"
            :customRow="(record: DrillDepartment) => ({ onClick: () => onDepartmentClick(record) })"
          />
        </div>

        <!-- Product breakdown -->
        <div v-if="summary.products?.length" class="section">
          <h4>产品维度</h4>
          <a-table
            :columns="productColumns"
            :data-source="summary.products"
            :pagination="false"
            size="small"
            row-key="id"
            :customRow="(record: DrillProduct) => ({ onClick: () => onProductClick(record) })"
          />
        </div>
      </template>
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import { getDrillSummary, getDrillDepartments, getDrillProducts } from '@/api/drilldowns';
import type { DrillSummary, DrillDepartment, DrillProduct } from '@/types/drilldown';
import { HomeOutlined } from '@ant-design/icons-vue';
import { toWan, formatWan } from '@/utils/format';

const props = defineProps<{ reportId: string }>();
const emit = defineEmits<{
  navigate: [level: number, params: Record<string, unknown>];
}>();

const loading = ref(false);
const summary = ref<DrillSummary | null>(null);
const departments = ref<DrillDepartment[]>([]);
const products = ref<DrillProduct[]>([]);

const AMOUNT_KEYS = new Set(['total_revenue', 'total_cost', 'total_profit']);

function formatMetric(key: string, val: number): number {
  if (AMOUNT_KEYS.has(key)) return toWan(val);
  return val;
}

function formatPrecision(key: string): number {
  if (AMOUNT_KEYS.has(key)) return 2;
  if (key === 'avg_margin') return 2;
  return 0;
}

const deptColumns: TableColumnsType = [
  { title: '部门', dataIndex: 'name', key: 'name' },
  { title: '收入(万元)', dataIndex: 'revenue', key: 'revenue', customRender: ({ text }: { text: number }) => formatWan(text, 2) },
  { title: '成本(万元)', dataIndex: 'cost', key: 'cost', customRender: ({ text }: { text: number }) => formatWan(text, 2) },
  { title: '毛利(万元)', dataIndex: 'gross_profit', key: 'gross_profit', customRender: ({ text }: { text: number }) => formatWan(text, 2) },
];

const productColumns: TableColumnsType = [
  { title: '产品', dataIndex: 'name', key: 'name' },
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '收入(万元)', dataIndex: 'revenue', key: 'revenue', customRender: ({ text }: { text: number }) => formatWan(text, 2) },
  {
    title: '毛利率',
    dataIndex: 'margin',
    key: 'margin',
    customRender: ({ text }: { text: number }) => text != null ? `${(text * 100).toFixed(2)}%` : '-',
  },
];

function formatKey(key: string): string {
  const labels: Record<string, string> = {
    total_revenue: '总收入(万元)',
    total_cost: '总成本(万元)',
    total_profit: '总毛利(万元)',
    avg_margin: '平均毛利率(%)',
    total_orders: '总订单数',
  };
  return labels[key] || key;
}

function onDepartmentClick(row: DrillDepartment) {
  emit('navigate', 2, { department_id: row.id, department_name: row.name });
}

function onProductClick(row: DrillProduct) {
  emit('navigate', 3, { product_id: row.id, product_name: row.name });
}

onMounted(async () => {
  loading.value = true;
  try {
    const [sumRes, deptRes, prodRes] = await Promise.all([
      getDrillSummary(props.reportId),
      getDrillDepartments(props.reportId).catch(() => ({ data: { data: [] } })),
      getDrillProducts(props.reportId).catch(() => ({ data: { data: [] } })),
    ]);
    summary.value = sumRes.data.data as DrillSummary;
    departments.value = deptRes.data.data as DrillDepartment[];
    products.value = prodRes.data.data as DrillProduct[];
    if (summary.value) {
      if (departments.value.length) summary.value.departments = departments.value;
      if (products.value.length) summary.value.products = products.value;
    }
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped lang="less">
.drilldown-l1 {
  border-radius: 8px;

  .metrics-row {
    margin-bottom: 24px;
  }

  .section {
    margin-top: 24px;

    h4 {
      margin-bottom: 12px;
      font-weight: 600;
    }
  }
}
</style>
