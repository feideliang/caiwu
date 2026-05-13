<template>
  <a-layout-content class="main-content">
    <div class="content-wrapper">
      <router-view />
    </div>
  </a-layout-content>
</template>

<script setup lang="ts">
</script>

<style scoped lang="less">
.main-content {
  padding: 24px;
}

.content-wrapper {
  max-width: 100%;
}

@media (max-width: 767px) {
  .main-content {
    padding: 12px;
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .main-content {
    padding: 16px;
  }
}
</style>
