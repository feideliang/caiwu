<template>
  <a-drawer
    :open="open"
    :title="title"
    placement="left"
    :width="280"
    @close="$emit('update:open', false)"
  >
    <div class="mobile-menu">
      <a-menu mode="inline" :selected-keys="selectedKeys" @click="handleMenuClick">
        <a-menu-item key="dashboard">
          <DashboardOutlined /> 总览仪表盘
        </a-menu-item>
        <a-menu-item key="trend-analysis">
          <LineChartOutlined /> 趋势分析
        </a-menu-item>
        <a-menu-item key="department-analysis">
          <SearchOutlined /> 部门分析
        </a-menu-item>
        <a-menu-item key="product-analysis">
          <LineChartOutlined /> 产品分析
        </a-menu-item>
        <a-menu-item key="drilldown">
          <SearchOutlined /> 数据钻取
        </a-menu-item>
        <a-menu-item v-if="isAnalyst" key="analysis">
          <LineChartOutlined /> 关联分析
        </a-menu-item>
        <a-menu-item key="reports">
          <FileTextOutlined /> 报告中心
        </a-menu-item>
        <a-menu-divider v-if="isAdmin" />
        <a-menu-item v-if="isAdmin" key="admin">
          <SettingOutlined /> 系统管理
        </a-menu-item>
      </a-menu>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/store/auth';
import {
  DashboardOutlined,
  SearchOutlined,
  LineChartOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue';

defineProps<{
  open: boolean;
  title?: string;
}>();

const emit = defineEmits<{ 'update:open': [value: boolean] }>();

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const { isAnalyst, isAdmin } = storeToRefs(authStore);
const selectedKeys = ref<string[]>([route.name as string || 'dashboard']);

const routeKeyMap: Record<string, string> = {
  Dashboard: 'dashboard',
  TrendAnalysis: 'trend-analysis',
  DepartmentAnalysis: 'department-analysis',
  ProductAnalysis: 'product-analysis',
  DrillDown: 'drilldown',
  Analysis: 'analysis',
  Reports: 'reports',
};

watch(() => route.name, (name) => {
  const key = routeKeyMap[name as string];
  if (key) selectedKeys.value = [key];
});

const menuRouteMap: Record<string, string> = {
  dashboard: '/',
  'trend-analysis': '/trend-analysis',
  'department-analysis': '/department-analysis',
  'product-analysis': '/product-analysis',
  drilldown: '/drilldown',
  analysis: '/analysis',
  reports: '/reports',
};

function handleMenuClick({ key }: { key: string }) {
  const path = menuRouteMap[key];
  if (path) router.push(path);
  emit('update:open', false);
}
</script>

<style scoped lang="less">
.mobile-menu {
  .ant-menu {
    border-right: none;
  }
}
</style>
