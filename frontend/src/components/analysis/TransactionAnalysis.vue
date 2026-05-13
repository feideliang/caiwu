<template>
  <div class="transaction-analysis">
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="contracts" tab="合同汇总">
        <a-card size="small">
          <a-spin :spinning="store.loading.contracts">
            <a-table :dataSource="store.contracts" :columns="contractColumns" rowKey="entity" size="small" :pagination="{ pageSize: 10 }">
              <template #total_ar="{ text }">{{ formatMoney(text) }}</template>
              <template #total_ap="{ text }">{{ formatMoney(text) }}</template>
              <template #net_exposure="{ text }"><span :class="text >= 0 ? 'positive' : 'negative'">{{ formatMoney(text) }}</span></template>
              <template #emptyText><a-empty description="暂无合同数据" /></template>
            </a-table>
          </a-spin>
        </a-card>
      </a-tab-pane>
      <a-tab-pane key="orders" tab="订单汇总">
        <a-card size="small">
          <a-spin :spinning="store.loading.orders">
            <a-table :dataSource="store.orders" :columns="orderColumns" rowKey="period" size="small" :pagination="{ pageSize: 12 }">
              <template #revenue="{ text }">{{ formatMoney(text) }}</template>
              <template #cost="{ text }">{{ formatMoney(text) }}</template>
              <template #profit="{ text }"><span :class="text >= 0 ? 'positive' : 'negative'">{{ formatMoney(text) }}</span></template>
              <template #emptyText><a-empty description="暂无订单数据" /></template>
            </a-table>
          </a-spin>
        </a-card>
      </a-tab-pane>
      <a-tab-pane key="projects" tab="项目汇总">
        <a-card size="small">
          <a-spin :spinning="store.loading.projects">
            <a-table :dataSource="store.projects" :columns="projectColumns" rowKey="entity" size="small" :pagination="{ pageSize: 10 }">
              <template #total_revenue="{ text }">{{ formatMoney(text) }}</template>
              <template #total_cost="{ text }">{{ formatMoney(text) }}</template>
              <template #profit_margin="{ text }">{{ (text * 100).toFixed(1) }}%</template>
              <template #emptyText><a-empty description="暂无项目数据" /></template>
            </a-table>
          </a-spin>
        </a-card>
      </a-tab-pane>
      <a-tab-pane key="anomalies" tab="异常检测">
        <AnomalyAlertList />
        <LargeAmountTable />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useTransactionsStore } from '../../store/transactions'
import AnomalyAlertList from './AnomalyAlertList.vue'
import LargeAmountTable from './LargeAmountTable.vue'

const store = useTransactionsStore()
const activeTab = ref('contracts')
const contractColumns = [
  { title: '实体', dataIndex: 'entity', key: 'entity' },
  { title: '应收总额', dataIndex: 'total_ar', key: 'total_ar', slots: { customRender: 'total_ar' } },
  { title: '应付总额', dataIndex: 'total_ap', key: 'total_ap', slots: { customRender: 'total_ap' } },
  { title: '净敞口', dataIndex: 'net_exposure', key: 'net_exposure', slots: { customRender: 'net_exposure' } },
  { title: '所属期间', dataIndex: 'period', key: 'period' },
]
const orderColumns = [
  { title: '期间', dataIndex: 'period', key: 'period' },
  { title: '收入', dataIndex: 'revenue', key: 'revenue', slots: { customRender: 'revenue' } },
  { title: '成本', dataIndex: 'cost', key: 'cost', slots: { customRender: 'cost' } },
  { title: '利润', dataIndex: 'profit', key: 'profit', slots: { customRender: 'profit' } },
]
const projectColumns = [
  { title: '项目名称', dataIndex: 'entity', key: 'entity' },
  { title: '总收入', dataIndex: 'total_revenue', key: 'total_revenue', slots: { customRender: 'total_revenue' } },
  { title: '总成本', dataIndex: 'total_cost', key: 'total_cost', slots: { customRender: 'total_cost' } },
  { title: '利润率', dataIndex: 'profit_margin', key: 'profit_margin', slots: { customRender: 'profit_margin' } },
  { title: '周期', dataIndex: 'period_span', key: 'period_span' },
]
function formatMoney(v: number) { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(v / 10000) + ' 万元' }
onMounted(() => { store.fetchContracts(); store.fetchOrders(); store.fetchProjects() })
</script>

<style scoped lang="less">
.transaction-analysis {
  .positive { color: #52c41a; font-weight: 500; }
  .negative { color: #ff4d4f; font-weight: 500; }
}
</style>
