import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getDataFreshness } from '@/api/dashboard';

export interface DataFreshness {
  last_sync: string;
  status: 'fresh' | 'stale' | 'error';
  source: string;
  next_sync: string;
}

export const useFreshnessStore = defineStore('freshness', () => {
  const freshness = ref<DataFreshness | null>(null);
  const loading = ref(false);

  async function fetch() {
    loading.value = true;
    try {
      const { data } = await getDataFreshness();
      freshness.value = data.data as DataFreshness;
    } finally {
      loading.value = false;
    }
  }

  return { freshness, loading, fetch };
});
