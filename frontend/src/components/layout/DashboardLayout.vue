<template>
  <a-layout class="dashboard-layout">
    <Sidebar class="sidebar" />
    <a-layout class="main-layout">
      <TopBar class="topbar" />
      <MainContent class="main-content" />
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import Sidebar from './Sidebar.vue';
import TopBar from './TopBar.vue';
import MainContent from './MainContent.vue';
</script>

<style scoped lang="less">
.dashboard-layout {
  height: 100vh;
  display: flex;
}

.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  transition: width 0.2s;
}

.main-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: var(--topbar-height);
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  overflow: auto;
}

@media (max-width: 767px) {
  .sidebar {
    display: none;
  }
}
</style>
