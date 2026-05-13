<template>
  <div class="analysis-page">
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="correlation" tab="关联分析">
        <CorrelationAnalysis />
      </a-tab-pane>
      <a-tab-pane key="transaction" tab="交易分析">
        <TransactionAnalysis />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import CorrelationAnalysis from '@/components/analysis/CorrelationAnalysis.vue';
import TransactionAnalysis from '@/components/analysis/TransactionAnalysis.vue';

const activeTab = ref('correlation');
</script>

<style scoped lang="less">
.analysis-page {
  padding: 0;
}
</style>
