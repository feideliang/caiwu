<template>
  <div>
    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :span="6"><a-card><a-statistic title="总检查数" :value="summary.total_checks" /></a-card></a-col>
      <a-col :span="6"><a-card><a-statistic title="通过" :value="summary.passed" value-style="color:#3f8600" /></a-card></a-col>
      <a-col :span="6"><a-card><a-statistic title="警告" :value="summary.warnings" value-style="color:#faad14" /></a-card></a-col>
      <a-col :span="6"><a-card><a-statistic title="失败" :value="summary.failed" value-style="color:#cf1322" /></a-card></a-col>
    </a-row>
    <a-progress :percent="Math.round(summary.pass_rate * 100)" :stroke-color="summary.pass_rate >= 0.9 ? '#3f8600' : summary.pass_rate >= 0.7 ? '#faad14' : '#cf1322'" style="margin-bottom: 24px" />
    <a-empty v-if="!errors.length && !loading" description="暂无数据质量记录" />
    <a-table v-else :dataSource="errors" :loading="loading" rowKey="id">
      <a-table-column title="规则" dataIndex="rule_name" />
      <a-table-column title="状态" dataIndex="status"><template #default="{ text }"><a-tag :color="text === 'PASSED' ? 'green' : text === 'WARNING' ? 'orange' : 'red'">{{ text }}</a-tag></template></a-table-column>
      <a-table-column title="消息" dataIndex="message" />
      <a-table-column title="时间" dataIndex="created_at" />
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getDataQualitySummary, getDataQualityErrors } from '../../api/dataManagement'

const summary = ref({ total_checks: 0, passed: 0, warnings: 0, failed: 0, pass_rate: 0, by_rule: [] })
const errors = ref<any[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const [s, e] = await Promise.all([getDataQualitySummary(), getDataQualityErrors({ page: 1, page_size: 50 })])
    if (s.data?.data) summary.value = s.data.data as typeof summary.value
    errors.value = (e.data?.data as { items?: any[] })?.items || []
  } finally { loading.value = false }
})
</script>
