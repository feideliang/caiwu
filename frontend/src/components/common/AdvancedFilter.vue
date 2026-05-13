<template>
  <a-card class="advanced-filter" size="small" :bordered="false">
    <template #title>
      <FilterOutlined /> 筛选条件
    </template>
    <template #extra>
      <a-space>
        <a-popover v-model:open="saveViewVisible" title="保存筛选视图">
          <template #content>
            <a-input-search
              placeholder="视图名称"
              enter-button="保存"
              @search="handleSaveView"
            />
          </template>
          <a-button size="small" :disabled="conditions.length === 0">
            <SaveOutlined /> 保存
          </a-button>
        </a-popover>
        <a-button size="small" @click="handleReset">
          <ReloadOutlined /> 重置
        </a-button>
      </a-space>
    </template>

    <!-- Saved filter views -->
    <div v-if="filtersStore.views.length > 0" class="saved-views">
      <a-space wrap>
        <a-tag
          v-for="view in filtersStore.views"
          :key="view.id"
          :color="filtersStore.activeView?.id === view.id ? 'blue' : 'default'"
          closable
          @close="handleDeleteView(view.id)"
          @click="handleSelectView(view)"
          class="view-tag"
        >
          {{ view.name }}
        </a-tag>
      </a-space>
    </div>

    <!-- Logic switch -->
    <div class="logic-switch">
      <span>组合逻辑:</span>
      <a-radio-group v-model:value="logic" size="small">
        <a-radio-button value="AND">AND</a-radio-button>
        <a-radio-button value="OR">OR</a-radio-button>
      </a-radio-group>
    </div>

    <!-- Dynamic filter conditions -->
    <div class="conditions">
      <a-row :gutter="[12, 12]">
        <a-col
          v-for="(cond, idx) in conditions"
          :key="idx"
          :xs="24"
          :sm="12"
          :md="8"
        >
          <div class="condition-row">
            <a-select
              v-model:value="cond.field"
              placeholder="选择字段"
              style="width: 120px"
              :options="fieldOptions"
              @change="onFieldChange(idx)"
            />
            <a-select
              v-model:value="cond.operator"
              placeholder="操作符"
              style="width: 100px"
              :options="operatorOptions"
            />
            <component
              :is="valueInput(cond)"
              v-model:value="(cond.value as any)"
              class="value-input"
            />
            <a-button type="text" danger size="small" @click="removeCondition(idx)">
              <DeleteOutlined />
            </a-button>
          </div>
        </a-col>
      </a-row>
      <a-button type="dashed" block style="margin-top: 12px" @click="addCondition">
        <PlusOutlined /> 添加条件
      </a-button>
    </div>

    <!-- Recent filter history -->
    <div v-if="historyEntries.length > 0" class="history">
      <a-divider orientation="left">最近使用</a-divider>
      <a-space wrap>
        <a-tag
          v-for="(h, idx) in historyEntries"
          :key="idx"
          @click="restoreHistory(h)"
        >
          {{ h.label }}
        </a-tag>
      </a-space>
    </div>

    <!-- Apply button -->
    <a-button type="primary" block style="margin-top: 16px" @click="handleApply">
      应用筛选
    </a-button>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useFiltersStore } from '@/store/filters';
import { getFilterOptions } from '@/api/filters';
import type { FilterCondition, FilterFieldConfig, FilterView } from '@/types/filter';
import { DatePicker, Input, InputNumber } from 'ant-design-vue';
import {
  FilterOutlined,
  SaveOutlined,
  ReloadOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue';

const emit = defineEmits<{
  apply: [conditions: FilterCondition[], logic: 'AND' | 'OR'];
  reset: [];
}>();

const filtersStore = useFiltersStore();
const logic = ref<'AND' | 'OR'>('AND');
const conditions = ref<FilterCondition[]>([{ field: '', operator: 'eq', value: '' }]);
const fieldConfigs = ref<FilterFieldConfig[]>([]);
const saveViewVisible = ref(false);

type HistoryEntry = { label: string; conditions: FilterCondition[]; logic: 'AND' | 'OR' };

// Merge store history with local history
const historyEntries = computed<HistoryEntry[]>(() => {
  return filtersStore.history.map((h) => ({
    label: h.conditions.map((c) => `${c.field} ${c.operator}`).join(' & '),
    conditions: h.conditions,
    logic: h.logic,
  }));
});

const fieldOptions = computed(() =>
  fieldConfigs.value.map((f) => ({ label: f.label, value: f.field })),
);

const operatorOptions = [
  { label: '等于', value: 'eq' },
  { label: '不等于', value: 'ne' },
  { label: '大于', value: 'gt' },
  { label: '大于等于', value: 'gte' },
  { label: '小于', value: 'lt' },
  { label: '小于等于', value: 'lte' },
  { label: '包含', value: 'in' },
  { label: '模糊', value: 'like' },
  { label: '区间', value: 'between' },
];

onMounted(async () => {
  await filtersStore.fetchViews();
  await loadFieldConfigs();
});

async function loadFieldConfigs() {
  try {
    const { data } = await getFilterOptions();
    const response = data.data as unknown as { dimension: string; options: string[]; total: number };
    fieldConfigs.value = response.options.map(opt => ({
      field: opt,
      label: opt,
      type: 'select' as const,
      options: []
    }));
  } catch {
    fieldConfigs.value = [
      { field: 'company', label: '公司', type: 'select', options: [] },
      { field: 'year', label: '年份', type: 'select', options: [] },
      { field: 'date', label: '日期', type: 'date_range' },
      { field: 'revenue', label: '收入', type: 'number_range' },
    ];
  }
}

function getFieldConfig(field: string): FilterFieldConfig | undefined {
  return fieldConfigs.value.find((f) => f.field === field);
}

function valueInput(cond: FilterCondition) {
  const config = getFieldConfig(cond.field);
  if (!config) return Input;

  switch (config.type) {
    case 'select':
      return Input;
    case 'date_range':
      return DatePicker.RangePicker;
    case 'number_range':
      return InputNumber;
    default:
      return Input;
  }
}

function onFieldChange(idx: number) {
  const cond = conditions.value[idx];
  const config = getFieldConfig(cond.field);
  if (config) {
    cond.operator = config.type === 'select' ? 'in' : 'eq';
    cond.value = config.type === 'date_range' ? [] : '';
  }
}

function addCondition() {
  conditions.value.push({ field: '', operator: 'eq', value: '' });
}

function removeCondition(idx: number) {
  if (conditions.value.length > 1) {
    conditions.value.splice(idx, 1);
  }
}

function handleApply() {
  const valid = conditions.value.filter((c) => c.field && c.value !== '' && c.value !== null);
  emit('apply', valid, logic.value);
  filtersStore.addToHistory(valid, logic.value);
}

function handleReset() {
  conditions.value = [{ field: '', operator: 'eq', value: '' }];
  logic.value = 'AND';
  filtersStore.setActiveView(null);
  emit('reset');
}

async function handleSaveView(name: string) {
  if (!name) return;
  const valid = conditions.value.filter((c) => c.field && c.value !== '' && c.value !== null);
  await filtersStore.saveView(name, valid, logic.value);
  saveViewVisible.value = false;
}

function handleSelectView(view: FilterView) {
  filtersStore.setActiveView(view);
  conditions.value = [...view.conditions];
  logic.value = view.logic;
}

async function handleDeleteView(id: number) {
  await filtersStore.deleteView(id);
}

function restoreHistory(h: HistoryEntry) {
  conditions.value = [...h.conditions];
  logic.value = h.logic;
}
</script>

<style scoped lang="less">
.advanced-filter {
  border-radius: 8px;
  margin-bottom: 16px;
}

.saved-views {
  margin-bottom: 12px;

  .view-tag {
    cursor: pointer;
  }
}

.logic-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;

  .value-input {
    flex: 1;
    min-width: 120px;
  }
}

.history {
  margin-top: 12px;

  .ant-tag {
    cursor: pointer;
  }
}

@media (max-width: 767px) {
  .condition-row {
    flex-direction: column;
    align-items: stretch;

    > * {
      width: 100%;
    }
  }
}
</style>
