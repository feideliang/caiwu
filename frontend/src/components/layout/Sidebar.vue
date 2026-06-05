<template>
  <a-layout-sider
    v-model:collapsed="collapsed"
    :trigger="null"
    collapsible
    theme="light"
    :width="220"
    :collapsed-width="64"
    :style="{ background: '#fff', borderRight: '1px solid #f0f0f0' }"
  >
    <div class="logo">
      <span v-if="!collapsed">数智财务</span>
      <span v-else>财</span>
    </div>
    <a-menu
      v-model:selectedKeys="selectedKeys"
      mode="inline"
      theme="light"
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
      <a-menu-item key="customer-analysis">
        <template #icon><TeamOutlined /></template>
        <span>客户分析</span>
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
  TeamOutlined,
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
  CustomerAnalysis: 'customer-analysis',
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
  'customer-analysis': '/customer-analysis',
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
  height: 48px;
  margin: 0;
  padding: 0 16px;
  color: #c41d1d;
  font-size: 20px;
  font-weight: 700;
  text-align: center;
  line-height: 48px;
  overflow: hidden;
  white-space: nowrap;
  border-bottom: 1px solid #f0f0f0;
  letter-spacing: 2px;
}

.collapse-trigger {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(0, 0, 0, 0.45);
  cursor: pointer;
  font-size: 16px;
  transition: color 0.3s;

  &:hover {
    color: #c41d1d;
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
  border-right: none !important;
}

:deep(.ant-menu-item-selected) {
  background-color: #c41d1d !important;
  color: #fff !important;
  font-weight: 600;
}

:deep(.ant-menu-item-selected::after) {
  border-right-color: #c41d1d !important;
}

:deep(.ant-menu-item:hover) {
  color: #c41d1d !important;
}

:deep(.ant-menu-item-selected:hover) {
  color: #fff !important;
}

:deep(.ant-menu-item) {
  border-radius: 0 !important;
  margin: 0 !important;
  width: 100% !important;
}
</style>
