<template>
  <a-card title="异常检测" size="small" class="anomaly-card">
    <a-spin :spinning="store.loading.anomalies">
      <a-list v-if="store.anomalies.length" :dataSource="store.anomalies" size="small" bordered>
        <template #renderItem="{ item }">
          <a-list-item>
            <a-alert :type="item.sigma_distance > 3 ? 'error' : item.sigma_distance > 2 ? 'warning' : 'info'"
              :message="`${item.metric_name} - ${item.entity || '未知'}`"
              :description="`期间: ${item.period} | 实际值: ${(item.value ?? 0).toFixed(2)} | 期望均值: ${(item.expected_mean ?? 0).toFixed(2)} | 偏离: ${(item.sigma_distance ?? 0).toFixed(1)}σ`"
              show-icon class="anomaly-alert" />
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-else description="暂无异常" />
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useTransactionsStore } from '../../store/transactions'
const store = useTransactionsStore()
onMounted(() => store.fetchAnomalies())
</script>

<style scoped lang="less">
.anomaly-card { margin-bottom: 16px; .anomaly-alert { width: 100%; margin-bottom: 8px; } }
</style>
