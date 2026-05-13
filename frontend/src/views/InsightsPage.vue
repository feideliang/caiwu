<template>
  <div class="insights-page">
    <a-page-header title="智能洞察" sub-title="基于规则与AI检测的异常与机会" />

    <a-card size="small" class="filter-bar">
      <a-space>
        <a-select v-model:value="statusFilter" :options="statusOptions" style="width: 140px" placeholder="状态" allow-clear @change="reload" />
        <a-button @click="reload">刷新</a-button>
      </a-space>
    </a-card>

    <InsightCard />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import InsightCard from '@/components/dashboard/InsightCard.vue';
import { useInsightsStore } from '@/store/insights';
import type { InsightStatus } from '@/types/insight';

const insightsStore = useInsightsStore();
const statusFilter = ref<InsightStatus | undefined>(undefined);

const statusOptions = [
  { label: '未读', value: 'unread' },
  { label: '已读', value: 'read' },
  { label: '已处理', value: 'process' },
  { label: '已忽略', value: 'ignore' },
];

function reload() {
  insightsStore.fetchInsights(statusFilter.value);
}

onMounted(reload);
</script>

<style scoped lang="less">
.insights-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.filter-bar {
  margin-bottom: 12px;
}
</style>
