import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getNotifications, markNotificationRead, markAllRead } from '@/api/notifications';

export interface Notification {
  id: number;
  title: string;
  content: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([]);
  const loading = ref(false);
  const unreadCount = ref(0);

  async function fetch() {
    loading.value = true;
    try {
      const { data } = await getNotifications({ page_size: 20 });
      const response = data.data as unknown as { items: Notification[]; unread_count: number };
      notifications.value = response.items || [];
      unreadCount.value = response.unread_count || 0;
    } finally {
      loading.value = false;
    }
  }

  async function markRead(id: number) {
    await markNotificationRead(id);
    const n = notifications.value.find((n) => n.id === id);
    if (n) n.is_read = true;
  }

  async function markAllAsRead() {
    await markAllRead();
    notifications.value.forEach((n) => (n.is_read = true));
  }

  return { notifications, loading, unreadCount, fetch, markRead, markAllAsRead };
});
