<template>
  <a-layout-header class="topbar">
    <div class="topbar-left">
      <h2 class="page-title">{{ pageTitle }}</h2>
      <a-tag v-if="freshness" :color="freshnessTagColor" class="freshness-tag">
        <SyncOutlined :spin="freshnessLoading" />
        {{ freshnessLabel }}
      </a-tag>
    </div>
    <div class="topbar-right">
      <!-- Notifications -->
      <a-badge :count="notificationStore.unreadCount" :offset="[-4, 4]">
        <a-button type="text" shape="circle" @click="showNotifications = true">
          <template #icon><BellOutlined /></template>
        </a-button>
      </a-badge>

      <!-- Insights badge -->
      <a-badge :count="insightsStore.unreadCount" :offset="[-4, 4]" class="insights-badge">
        <a-button type="text" @click="showInsights = true">
          <template #icon><BulbOutlined /></template>
          智能洞察
        </a-button>
      </a-badge>

      <!-- User menu -->
      <a-dropdown>
        <a class="user-info" @click.prevent>
          <UserOutlined />
          <span class="username">{{ authStore.user?.username }}</span>
          <DownOutlined />
        </a>
        <template #overlay>
          <a-menu>
            <a-menu-item key="profile" @click="router.push('/profile')">
              <UserOutlined /> 个人中心
            </a-menu-item>
            <a-menu-item v-if="authStore.user?.role === 'admin'" key="admin" @click="router.push('/admin')">
              <SettingOutlined /> 管理后台
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item key="logout" @click="handleLogout">
              <LogoutOutlined /> 退出登录
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>

    <!-- Notification drawer -->
    <a-drawer
      v-model:open="showNotifications"
      title="通知"
      placement="right"
      width="360"
    >
      <a-list :loading="notificationStore.loading" item-layout="horizontal" :data-source="notificationStore.notifications">
        <template #renderItem="{ item }">
          <a-list-item class="notification-item" @click="handleReadNotification(item.id)">
            <a-list-item-meta>
              <template #title>
                <span :style="{ fontWeight: item.is_read ? 400 : 600 }">{{ item.title }}</span>
              </template>
              <template #description>{{ item.content }}</template>
            </a-list-item-meta>
            <span class="text-secondary">{{ item.created_at }}</span>
          </a-list-item>
        </template>
      </a-list>
      <template #footer>
        <a-button type="link" block @click="notificationStore.markAllAsRead()">全部已读</a-button>
      </template>
    </a-drawer>

    <!-- Insights drawer -->
    <a-drawer
      v-model:open="showInsights"
      title="智能洞察"
      placement="right"
      width="400"
    >
      <InsightCard :compact="true" />
    </a-drawer>
  </a-layout-header>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/store/auth';
import { useInsightsStore } from '@/store/insights';
import { useNotificationStore } from '@/store/notification';
import { useFreshnessStore } from '@/store/freshness';
import dayjs from 'dayjs';
import InsightCard from '@/components/dashboard/InsightCard.vue';
import {
  BellOutlined,
  BulbOutlined,
  UserOutlined,
  DownOutlined,
  LogoutOutlined,
  SyncOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const insightsStore = useInsightsStore();
const notificationStore = useNotificationStore();
const freshnessStore = useFreshnessStore();

const showNotifications = ref(false);
const showInsights = ref(false);

let notificationTimer: ReturnType<typeof setInterval> | null = null;

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    Dashboard: '财务总览',
    DrillDown: '数据钻取',
    Analysis: '关联分析',
    Reports: '报告中心',
    Login: '登录',
  };
  return titles[route.name as string] || '财务管报';
});

const freshness = computed(() => freshnessStore.freshness);
const freshnessLoading = computed(() => freshnessStore.loading);

const freshnessTagColor = computed(() => {
  if (!freshness.value) return 'default';
  const map: Record<string, string> = { fresh: 'green', stale: 'orange', error: 'red' };
  return map[freshness.value.status] || 'default';
});

const freshnessLabel = computed(() => {
  if (!freshness.value) return '';
  return `数据更新于 ${dayjs(freshness.value.last_sync).fromNow()}`;
});

onMounted(async () => {
  // Only fetch data if user is logged in
  if (!authStore.isLoggedIn) return;

  await Promise.all([
    insightsStore.fetchInsights(),
    notificationStore.fetch(),
    freshnessStore.fetch(),
  ]);

  // Poll notifications every 30s
  notificationTimer = setInterval(() => {
    notificationStore.fetch();
  }, 30_000);
});

onUnmounted(() => {
  if (notificationTimer) {
    clearInterval(notificationTimer);
    notificationTimer = null;
  }
});

function handleReadNotification(id: number) {
  notificationStore.markRead(id);
}

function handleLogout() {
  authStore.logout();
}
</script>

<style scoped lang="less">
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--color-bg-container);
  border-bottom: 1px solid #f0f0f0;
  height: var(--topbar-height);
  position: relative;
}

.topbar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #c41d1d, #ff4d4f);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;

  .page-title {
    font-size: 18px;
    font-weight: 600;
    margin: 0;
  }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.insights-badge {
  margin-right: 4px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text);
  cursor: pointer;

  .username {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.freshness-tag {
  font-size: 12px;
}

.notification-item {
  cursor: pointer;

  &:hover {
    background: #f5f5f5;
  }
}

@media (max-width: 767px) {
  .topbar {
    padding: 0 12px;

    .page-title {
      font-size: 14px;
    }
  }

  .user-info .username {
    display: none;
  }
}
</style>
