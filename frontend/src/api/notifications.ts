import { post, get } from './request';

export interface NotificationItem {
  id: number;
  title: string;
  content: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export function getNotifications(params?: Record<string, unknown>) {
  return get<NotificationItem[]>('/notifications', { params });
}

export function markNotificationRead(id: number) {
  return post(`/notifications/${id}/read`);
}

export function markAllRead() {
  return post('/notifications/read-all');
}
