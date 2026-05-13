import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getContracts, getOrders, getProjects, getAnomalies, getLargeAmounts } from '../api/transactions'
import type { ContractItem, OrderItem, ProjectItem, AnomalyItem, LargeAmountItem } from '../api/transactions'

export const useTransactionsStore = defineStore('transactions', () => {
  const contracts = ref<ContractItem[]>([])
  const orders = ref<OrderItem[]>([])
  const projects = ref<ProjectItem[]>([])
  const anomalies = ref<AnomalyItem[]>([])
  const largeAmounts = ref<LargeAmountItem[]>([])
  const loading = ref({ contracts: false, orders: false, projects: false, anomalies: false, largeAmounts: false })

  async function fetchContracts(params?: Record<string, unknown>) {
    loading.value.contracts = true
    try { const r = await getContracts(params); contracts.value = (r.data?.data as { items?: ContractItem[] })?.items || [] } catch { contracts.value = [] }
    finally { loading.value.contracts = false }
  }
  async function fetchOrders(params?: Record<string, unknown>) {
    loading.value.orders = true
    try { const r = await getOrders(params); orders.value = (r.data?.data as { items?: OrderItem[] })?.items || [] } catch { orders.value = [] }
    finally { loading.value.orders = false }
  }
  async function fetchProjects(params?: Record<string, unknown>) {
    loading.value.projects = true
    try { const r = await getProjects(params); projects.value = (r.data?.data as { items?: ProjectItem[] })?.items || [] } catch { projects.value = [] }
    finally { loading.value.projects = false }
  }
  async function fetchAnomalies(params?: Record<string, unknown>) {
    loading.value.anomalies = true
    try { const r = await getAnomalies(params); anomalies.value = (r.data?.data as AnomalyItem[]) || [] } catch { anomalies.value = [] }
    finally { loading.value.anomalies = false }
  }
  async function fetchLargeAmounts(params?: Record<string, unknown>) {
    loading.value.largeAmounts = true
    try { const r = await getLargeAmounts(params); largeAmounts.value = (r.data?.data as { items?: LargeAmountItem[] })?.items || [] } catch { largeAmounts.value = [] }
    finally { loading.value.largeAmounts = false }
  }

  return { contracts, orders, projects, anomalies, largeAmounts, loading, fetchContracts, fetchOrders, fetchProjects, fetchAnomalies, fetchLargeAmounts }
})
