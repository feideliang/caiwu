<template>
  <div class="insight-card-container">
    <a-spin :spinning="insightsStore.loading">
      <a-empty v-if="!insightsStore.loading && insightsStore.insights.length === 0" description="暂无智能洞察" />
      <div v-else :class="['insight-list', { compact }]">
        <a-card
          v-for="insight in visibleInsights"
          :key="insight.id"
          :class="['insight-card', `severity-${insight.severity}`, `status-${insight.status}`]"
          hoverable
          size="small"
          @click="handleClick(insight)"
        >
          <template #title>
            <div class="insight-header">
              <component :is="typeIcon(insight.type)" :class="['type-icon', `type-${insight.type}`]" />
              <span class="insight-title">{{ insight.title }}</span>
              <a-badge
                :count="Math.round(insight.confidence * 100)"
                :number-style="{ backgroundColor: confidenceColor(insight.confidence) }"
                class="confidence-badge"
              />
            </div>
          </template>
          <div class="insight-body">
            <p class="description">{{ insight.description }}</p>
            <div class="insight-footer">
              <a-tag :color="severityTagColor[insight.severity]" size="small">{{ severityLabel(insight.severity) }}</a-tag>
              <a-tag :color="statusTagColor[insight.status]" size="small">{{ statusLabel(insight.status) }}</a-tag>
              <span class="text-secondary time">{{ insight.created_at }}</span>
            </div>
            <!-- Actions -->
            <div v-if="!compact" class="insight-actions">
              <a-space>
                <a-button size="small" type="primary" @click.stop="handleDrillDown(insight)">
                  <SearchOutlined /> 钻取
                </a-button>
                <a-button size="small" @click.stop="handleProcess(insight)">
                  <CheckOutlined /> 已处理
                </a-button>
                <a-button size="small" danger @click.stop="handleIgnore(insight)">
                  <CloseOutlined /> 忽略
                </a-button>
              </a-space>
            </div>
          </div>
        </a-card>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue';
import { useRouter } from 'vue-router';
import { useInsightsStore } from '@/store/insights';
import type { Insight, InsightSeverity, InsightStatus } from '@/types/insight';
import {
  WarningOutlined,
  RiseOutlined,
  LinkOutlined,
  AlertOutlined,
  LineChartOutlined,
  SearchOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue';

const props = withDefaults(defineProps<{
  compact?: boolean;
  maxCount?: number;
}>(), {
  compact: false,
  maxCount: 10,
});

const router = useRouter();
const insightsStore = useInsightsStore();

const visibleInsights = computed(() => {
  const list = insightsStore.insights.filter((i) => i.status !== 'ignore');
  return props.compact ? list.slice(0, props.maxCount) : list;
});

const iconMap: Record<string, Component> = {
  anomaly: AlertOutlined,
  trend: RiseOutlined,
  correlation: LinkOutlined,
  threshold: WarningOutlined,
  forecast: LineChartOutlined,
};

function typeIcon(type: string): Component {
  return iconMap[type] || AlertOutlined;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return '#52c41a';
  if (confidence >= 0.6) return '#faad14';
  return '#ff4d4f';
}

const severityTagColor: Record<InsightSeverity, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

function severityLabel(severity: InsightSeverity): string {
  const labels: Record<InsightSeverity, string> = { high: '高', medium: '中', low: '低' };
  return labels[severity];
}

const statusTagColor: Record<InsightStatus, string> = {
  unread: 'red',
  read: 'default',
  process: 'green',
  ignore: 'default',
};

function statusLabel(status: InsightStatus): string {
  const labels: Record<InsightStatus, string> = { unread: '未读', read: '已读', process: '已处理', ignore: '已忽略' };
  return labels[status];
}

function handleClick(insight: Insight) {
  if (insight.status === 'unread') {
    insightsStore.markRead(insight.id);
  }
}

function handleDrillDown(insight: Insight) {
  insightsStore.markRead(insight.id);
  const data = insight.data_json;
  if (data?.drill_type && data?.drill_level) {
    const query: Record<string, string> = {
      level: String(data.drill_level),
    };
    if (data.drill_type !== 'overview') {
      query.drill_type = data.drill_type as string;
    }
    const params = data.drill_params as Record<string, string> | undefined;
    if (params) {
      Object.assign(query, params);
    }
    if (data.drill_type && data.drill_type !== 'overview') {
      query.dimension = data.drill_type as string;
      if (params) {
        const dimVal =
          params.department_name ||
          params.product_name ||
          params.record_title ||
          params.department_id ||
          params.product_id ||
          params.record_id;
        if (dimVal) query.dimension_value = String(dimVal);
      }
    }
    const metric = (data.metric_name || data.metric) as string | undefined;
    if (metric) query.metric = metric;
    if (data.rule_code) query.rule_code = data.rule_code as string;
    const period = (data.period as string) || '2026-03';
    router.push({ name: 'DrillDown', params: { report_id: period }, query });
  } else if (insight.related_chart_id) {
    window.dispatchEvent(new CustomEvent('chart-highlight', { detail: { chartId: insight.related_chart_id } }));
    router.push({ name: 'DrillDown', query: { insight: String(insight.id) } });
  }
}

function handleProcess(insight: Insight) {
  insightsStore.markProcessed(insight.id);
}

function handleIgnore(insight: Insight) {
  insightsStore.markIgnored(insight.id);
}
</script>

<style scoped lang="less">
.insight-list {
  display: flex;
  flex-direction: column;
  gap: 12px;

  &.compact {
    gap: 8px;
  }
}

.insight-card {
  border-left: 4px solid transparent;
  cursor: pointer;

  &.severity-high { border-left-color: #ff4d4f; }
  &.severity-medium { border-left-color: #faad14; }
  &.severity-low { border-left-color: #1677ff; }

  &.status-process { opacity: 0.6; }
  &.status-ignore { opacity: 0.4; }
}

.insight-header {
  display: flex;
  align-items: center;
  gap: 8px;

  .type-icon {
    font-size: 16px;

    &.type-anomaly { color: #ff4d4f; }
    &.type-trend { color: #52c41a; }
    &.type-correlation { color: #1677ff; }
    &.type-threshold { color: #faad14; }
    &.type-forecast { color: #722ed1; }
  }

  .insight-title {
    flex: 1;
    font-weight: 600;
    font-size: 14px;
  }
}

.insight-body {
  .description {
    margin: 8px 0;
    color: var(--color-text-secondary);
    font-size: 13px;
  }
}

.insight-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;

  .time {
    margin-left: auto;
    font-size: 12px;
  }
}

.insight-actions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}
</style>
