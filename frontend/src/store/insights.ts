import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getInsights, updateInsightStatus } from '@/api/dashboard';
import type { Insight, InsightStatus } from '@/types/insight';

export const useInsightsStore = defineStore('insights', () => {
  const insights = ref<Insight[]>([]);
  const loading = ref(false);
  const error = ref('');

  const unreadCount = computed(() => insights.value.filter((i) => i.status === 'unread').length);
  const highSeverityUnread = computed(
    () => insights.value.filter((i) => i.status === 'unread' && i.severity === 'high').length,
  );

  async function fetchInsights(status?: InsightStatus) {
    loading.value = true;
    error.value = '';
    try {
      const { data } = await getInsights(status ? { status } : undefined);
      const payload = data.data as { items?: Insight[] };
      insights.value = payload.items || [];
    } catch (e: unknown) {
      error.value = (e as Error).message;
    } finally {
      loading.value = false;
    }
  }

  async function markStatus(id: number, status: InsightStatus) {
    await updateInsightStatus(id, status);
    const insight = insights.value.find((i) => i.id === id);
    if (insight) insight.status = status;
  }

  async function markRead(id: number) {
    await markStatus(id, 'read');
  }

  async function markProcessed(id: number) {
    await markStatus(id, 'process');
  }

  async function markIgnored(id: number) {
    await markStatus(id, 'ignore');
  }

  return { insights, loading, error, unreadCount, highSeverityUnread, fetchInsights, markRead, markProcessed, markIgnored };
});
