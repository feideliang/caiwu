<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 60vh">
    <a-result status="404" title="404" sub-title="页面不存在">
      <template #extra><a-button type="primary" @click="router.push('/')">返回首页</a-button></template>
    </a-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
