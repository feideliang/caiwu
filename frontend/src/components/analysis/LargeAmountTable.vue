<template>
  <a-card title="大额交易监控" size="small" class="large-amount-card">
    <template #extra>
      <a-space>
        <span class="threshold-label">阈值(万元):</span>
        <a-input-number v-model:value="threshold" :min="0" :step="10" style="width: 140px" @change="fetchData" />
      </a-space>
    </template>
    <a-spin :spinning="store.loading.largeAmounts">
      <a-table :dataSource="filteredData" :columns="columns" rowKey="metric_name" size="small" :pagination="{ pageSize: 8 }">
        <template #metric_value="{ text }"><span class="money">{{ formatMoney(text) }}</span></template>
        <template #emptyText><a-empty description="暂无大额交易" /></template>
      </a-table>
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTransactionsStore } from '../../store/transactions'

const store = useTransactionsStore()
const threshold = ref(50)
const columns = [
  { title: '指标名称', dataIndex: 'metric_name', key: 'metric_name' },
  { title: '指标值(万元)', dataIndex: 'metric_value', key: 'metric_value', slots: { customRender: 'metric_value' } },
  { title: '所属期间', dataIndex: 'period', key: 'period' },
  { title: '所属实体', dataIndex: 'entity', key: 'entity' },
]
const filteredData = computed(() => store.largeAmounts.filter(i => i.metric_value / 10000 >= threshold.value))
function formatMoney(v: number) { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(v / 10000) + ' 万元' }
function fetchData() { store.fetchLargeAmounts() }
onMounted(fetchData)
</script>

<style scoped lang="less">
.large-amount-card { .threshold-label { font-size: 13px; color: #888; } .money { font-weight: 500; } }
</style>
