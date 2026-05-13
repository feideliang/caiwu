import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getFilterViews, saveFilterView, deleteFilterView as apiDeleteFilterView } from '@/api/filters';
import type { FilterView, FilterCondition } from '@/types/filter';

export const useFiltersStore = defineStore('filters', () => {
  const views = ref<FilterView[]>([]);
  const activeView = ref<FilterView | null>(null);
  const loading = ref(false);

  // Recent filter history (last 5)
  const history = ref<Array<{ conditions: FilterCondition[]; logic: 'AND' | 'OR'; appliedAt: string }>>([]);

  const maxHistory = 5;

  async function fetchViews() {
    loading.value = true;
    try {
      const { data } = await getFilterViews();
      const payload = data.data as { items?: FilterView[] };
      views.value = payload.items || [];
    } finally {
      loading.value = false;
    }
  }

  async function saveView(name: string, conditions: FilterCondition[], logic: 'AND' | 'OR') {
    const { data } = await saveFilterView({ name, conditions, logic });
    views.value.push(data.data as FilterView);
    return data.data as FilterView;
  }

  async function deleteView(id: number) {
    await apiDeleteFilterView(id);
    views.value = views.value.filter((v) => v.id !== id);
    if (activeView.value?.id === id) {
      activeView.value = null;
    }
  }

  function setActiveView(view: FilterView | null) {
    activeView.value = view;
  }

  function addToHistory(conditions: FilterCondition[], logic: 'AND' | 'OR') {
    history.value.unshift({
      conditions,
      logic,
      appliedAt: new Date().toISOString(),
    });
    if (history.value.length > maxHistory) {
      history.value = history.value.slice(0, maxHistory);
    }
  }

  function clearHistory() {
    history.value = [];
  }

  return {
    views,
    activeView,
    loading,
    history,
    fetchViews,
    saveView,
    deleteView,
    setActiveView,
    addToHistory,
    clearHistory,
  };
});
