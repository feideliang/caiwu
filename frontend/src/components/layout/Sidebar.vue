<template>
  <a-layout-sider
    v-model:collapsed="collapsed"
    :trigger="null"
    collapsible
    theme="dark"
    :width="220"
    :collapsed-width="64"
  >
    <div class="logo">
      <span v-if="!collapsed">数智财务</span>
      <span v-else>财</span>
    </div>
    <a-menu
      v-model:selectedKeys="selectedKeys"
      mode="inline"
      theme="dark"
      @click="handleMenuClick"
    >
      <a-menu-item key="dashboard">
        <template #icon><DashboardOutlined /></template>
        <span>总览驾驶舱</span>
      </a-menu-item>
      <a-menu-item key="metrics">
        <template #icon><FundOutlined /></template>
        <span>变动分析</span>
      </a-menu-item>
      <a-menu-item key="trend-analysis">
        <template #icon><LineChartOutlined /></template>
        <span>趋势分析</span>
      </a-menu-item>
      <a-menu-item key="department-analysis">
        <template #icon><ProfileOutlined /></template>
        <span>部门分析</span>
      </a-menu-item>
      <a-menu-item key="product-analysis">
        <template #icon><AreaChartOutlined /></template>
        <span>产品分析</span>
      </a-menu-item>
      <a-menu-item key="insights">
        <template #icon><BulbOutlined /></template>
        <span>智能洞察</span>
      </a-menu-item>
      <a-menu-item key="drilldown">
        <template #icon><SearchOutlined /></template>
        <span>数据钻取</span>
      </a-menu-item>
      <a-menu-item key="transactions">
        <template #icon><ProfileOutlined /></template>
        <span>交易/订单穿透</span>
      </a-menu-item>

      <a-menu-item v-if="isAnalyst" key="analysis">
        <template #icon><LineChartOutlined /></template>
        <span>关联分析</span>
      </a-menu-item>

      <a-menu-item key="prediction">
        <template #icon><AreaChartOutlined /></template>
        <span>趋势预测</span>
      </a-menu-item>

      <a-menu-item key="reports">
        <template #icon><FileTextOutlined /></template>
        <span>报告中心</span>
      </a-menu-item>

      <a-menu-divider v-if="isAdmin" />
      <a-menu-item v-if="isAdmin" key="admin">
        <template #icon><SettingOutlined /></template>
        <span>系统管理</span>
      </a-menu-item>
    </a-menu>
    <div class="collapse-trigger" @click="collapsed = !collapsed">
      <MenuUnfoldOutlined v-if="collapsed" />
      <MenuFoldOutlined v-else />
    </div>
  </a-layout-sider>
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
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  FundOutlined,
  BulbOutlined,
  ProfileOutlined,
  AreaChartOutlined,
} from '@ant-design/icons-vue';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const { isAnalyst, isAdmin } = storeToRefs(authStore);

const collapsed = ref(window.innerWidth < 1024);
const selectedKeys = ref<string[]>([route.name as string || 'dashboard']);

const routeKeyMap: Record<string, string> = {
  Dashboard: 'dashboard',
  CoreMetrics: 'metrics',
  TrendAnalysis: 'trend-analysis',
  DepartmentAnalysis: 'department-analysis',
  ProductAnalysis: 'product-analysis',
  Insights: 'insights',
  DrillDown: 'drilldown',
  Transactions: 'transactions',
  Analysis: 'analysis',
  Prediction: 'prediction',
  Reports: 'reports',
  Admin: 'admin',
  Profile: 'profile',
};

watch(
  () => route.name,
  (name) => {
    const key = routeKeyMap[name as string];
    if (key) selectedKeys.value = [key];
  },
);

const menuRouteMap: Record<string, string> = {
  dashboard: '/',
  metrics: '/metrics',
  'trend-analysis': '/trend-analysis',
  'department-analysis': '/department-analysis',
  'product-analysis': '/product-analysis',
  insights: '/insights',
  drilldown: '/drilldown',
  transactions: '/transactions',
  analysis: '/analysis',
  prediction: '/prediction',
  reports: '/reports',
  admin: '/admin',
};

function handleMenuClick({ key }: { key: string }) {
  const path = menuRouteMap[key];
  if (path) router.push(path);
}
</script>

<style scoped lang="less">
.logo {
  height: 32px;
  margin: 16px;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  line-height: 32px;
  overflow: hidden;
  white-space: nowrap;
}

.collapse-trigger {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  font-size: 16px;
  transition: color 0.3s;

  &:hover {
    color: #fff;
  }
}

:deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.ant-menu) {
  flex: 1;
  overflow: auto;
}
</style>
