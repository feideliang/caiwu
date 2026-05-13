<template>
  <div class="transactions-page">
    <a-page-header title="交易/订单穿透" sub-title="合同 / 订单 / 项目 / 异常 / 大额" />

    <a-card size="small" class="filter-bar">
      <a-space>
        <a-input v-model:value="filters.entity" placeholder="客户/实体" style="width: 180px" allow-clear />
        <a-input v-model:value="filters.period" placeholder="期间 YYYY-MM" style="width: 140px" allow-clear />
        <a-button type="primary" @click="reload">查询</a-button>
      </a-space>
    </a-card>

    <a-tabs v-model:active-key="activeTab" @change="reload">
      <a-tab-pane key="orders" tab="订单">
        <a-table :columns="orderColumns" :data-source="orders" size="small" :loading="loading" :pagination="{ pageSize: 10 }" row-key="period" />
      </a-tab-pane>
      <a-tab-pane key="contracts" tab="合同">
        <a-table :columns="contractColumns" :data-source="contracts" size="small" :loading="loading" :pagination="{ pageSize: 10 }" row-key="entity" />
      </a-tab-pane>
      <a-tab-pane key="projects" tab="项目">
        <a-table :columns="projectColumns" :data-source="projects" size="small" :loading="loading" :pagination="{ pageSize: 10 }" row-key="entity" />
      </a-tab-pane>
      <a-tab-pane key="anomalies" tab="异常">
        <a-table :columns="anomalyColumns" :data-source="anomalies" size="small" :loading="loading" :pagination="{ pageSize: 10 }" row-key="metric_name" />
      </a-tab-pane>
      <a-tab-pane key="large" tab="大额">
        <a-table :columns="largeColumns" :data-source="largeAmounts" size="small" :loading="loading" :pagination="{ pageSize: 10 }" row-key="metric_name" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import {
  getContracts, getOrders, getProjects, getAnomalies, getLargeAmounts,
  type ContractItem, type OrderItem, type ProjectItem, type AnomalyItem, type LargeAmountItem,
} from '@/api/transactions';

const route = useRoute();
const activeTab = ref<string>('orders');
const loading = ref(false);
const filters = reactive<{ entity?: string; period?: string }>({});

const orders = ref<OrderItem[]>([]);
const contracts = ref<ContractItem[]>([]);
const projects = ref<ProjectItem[]>([]);
const anomalies = ref<AnomalyItem[]>([]);
const largeAmounts = ref<LargeAmountItem[]>([]);

const orderColumns = [
  { title: '期间', dataIndex: 'period' },
  { title: '收入', dataIndex: 'revenue' },
  { title: '成本', dataIndex: 'cost' },
  { title: '利润', dataIndex: 'profit' },
];
const contractColumns = [
  { title: '实体', dataIndex: 'entity' },
  { title: '应收', dataIndex: 'total_ar' },
  { title: '应付', dataIndex: 'total_ap' },
  { title: '净敞口', dataIndex: 'net_exposure' },
  { title: '期间', dataIndex: 'period' },
];
const projectColumns = [
  { title: '实体', dataIndex: 'entity' },
  { title: '总收入', dataIndex: 'total_revenue' },
  { title: '总成本', dataIndex: 'total_cost' },
  { title: '利润率', dataIndex: 'profit_margin' },
  { title: '期间', dataIndex: 'period_span' },
];
const anomalyColumns = [
  { title: '指标', dataIndex: 'metric_name' },
  { title: '期间', dataIndex: 'period' },
  { title: '值', dataIndex: 'value' },
  { title: '期望均值', dataIndex: 'expected_mean' },
  { title: 'σ距离', dataIndex: 'sigma_distance' },
  { title: '实体', dataIndex: 'entity' },
];
const largeColumns = [
  { title: '指标', dataIndex: 'metric_name' },
  { title: '值', dataIndex: 'metric_value' },
  { title: '期间', dataIndex: 'period' },
  { title: '实体', dataIndex: 'entity' },
];

async function reload() {
  loading.value = true;
  const params: Record<string, unknown> = {};
  if (filters.entity) params.entity = filters.entity;
  if (filters.period) params.period = filters.period;
  try {
    if (activeTab.value === 'orders') {
      const { data } = await getOrders(params);
      orders.value = (data.data as { items?: OrderItem[] })?.items || (data.data as OrderItem[]) || [];
    } else if (activeTab.value === 'contracts') {
      const { data } = await getContracts(params);
      contracts.value = (data.data as { items?: ContractItem[] })?.items || (data.data as ContractItem[]) || [];
    } else if (activeTab.value === 'projects') {
      const { data } = await getProjects(params);
      projects.value = (data.data as { items?: ProjectItem[] })?.items || (data.data as ProjectItem[]) || [];
    } else if (activeTab.value === 'anomalies') {
      const { data } = await getAnomalies(params);
      anomalies.value = (data.data as { items?: AnomalyItem[] })?.items || (data.data as AnomalyItem[]) || [];
    } else if (activeTab.value === 'large') {
      const { data } = await getLargeAmounts(params);
      largeAmounts.value = (data.data as { items?: LargeAmountItem[] })?.items || (data.data as LargeAmountItem[]) || [];
    }
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (route.query.entity) filters.entity = route.query.entity as string;
  if (route.query.period) filters.period = route.query.period as string;
  if (route.query.tab) activeTab.value = route.query.tab as string;
  reload();
});
</script>

<style scoped lang="less">
.transactions-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.filter-bar {
  margin-bottom: 12px;
}
</style>
