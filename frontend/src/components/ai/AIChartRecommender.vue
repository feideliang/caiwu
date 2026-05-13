<template>
  <a-card class="ai-chart-recommender" size="small" :bordered="false">
    <template #title>
      <RobotOutlined /> AI图表推荐
    </template>
    <template #extra>
      <a-button size="small" :loading="loading" @click="handleRecommend">
        <BulbOutlined /> 重新推荐
      </a-button>
    </template>

    <!-- Pre-screen: rule-based -->
    <div v-if="!loading && ruleBasedResult" class="rule-based">
      <a-alert
        message="规则预筛结果"
        :description="ruleBasedResult.description"
        type="info"
        show-icon
        closable
        @close="ruleBasedResult = null"
      />
    </div>

    <!-- AI recommendation result -->
    <a-spin :spinning="loading">
      <div v-if="recommendation" class="recommendation">
        <a-descriptions :column="isMobile ? 1 : 2" size="small" bordered>
          <a-descriptions-item label="推荐图表">
            <a-tag color="blue">{{ chartTypeLabel(recommendation.chart_type) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="评分">
            <a-progress
              :percent="Math.round(recommendation.score * 100)"
              size="small"
              :stroke-color="confidenceColor(recommendation.score)"
            />
          </a-descriptions-item>
        </a-descriptions>
        <p class="reason">{{ recommendation.reason }}</p>

        <!-- Alternatives -->
        <div v-if="alternatives.length" class="alternatives">
          <span class="label">备选方案:</span>
          <a-space wrap>
            <a-button
              v-for="(alt, idx) in alternatives"
              :key="idx"
              size="small"
              @click="applyRecommendation(alt.chart_type)"
            >
              {{ chartTypeLabel(alt.chart_type) }}
            </a-button>
          </a-space>
        </div>

        <!-- Apply button -->
        <a-button
          type="primary"
          block
          class="apply-btn"
          @click="applyRecommendation(recommendation.chart_type)"
        >
          <CheckOutlined /> 应用到图表
        </a-button>
      </div>

      <a-empty v-else-if="!loading" description='点击"重新推荐"获取AI推荐' />
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { recommendChart } from '@/api/ai';
import type { ChartRecommendItem } from '@/api/ai';
import { RobotOutlined, BulbOutlined, CheckOutlined } from '@ant-design/icons-vue';
import { message } from 'ant-design-vue';

const props = defineProps<{
  targetChartId?: string;
  dataType: string;
  dataSample?: Record<string, unknown>[];
}>();

const emit = defineEmits<{
  apply: [chartType: string, config: Record<string, unknown>];
}>();

const loading = ref(false);
const recommendation = ref<ChartRecommendItem | null>(null);
const alternatives = ref<ChartRecommendItem[]>([]);
const ruleBasedResult = ref<{ description: string } | null>(null);

const isMobile = computed(() => window.innerWidth < 768);

// Rule-based pre-screen
function ruleBasedScreen(): { description: string; chartType: string } | null {
  const sample = props.dataSample;
  if (!sample?.length) return null;

  const keys = Object.keys(sample[0]);
  if (keys.length === 2) {
    return { description: '二维数据，推荐柱状图或折线图', chartType: 'bar' };
  }
  if (keys.length === 1 && keys[0] === 'category') {
    return { description: '分类数据，推荐饼图', chartType: 'pie' };
  }
  if (sample.length > 12) {
    return { description: '多数据点时序，推荐折线图', chartType: 'line' };
  }
  return null;
}

// Apply rule-based screen on mount
function runRuleScreen() {
  const result = ruleBasedScreen();
  if (result) {
    ruleBasedResult.value = { description: result.description };
  }
}

async function handleRecommend() {
  loading.value = true;
  try {
    const sample = props.dataSample || [];
    const device = window.innerWidth >= 1024 ? 'web' : window.innerWidth >= 768 ? 'tablet' : 'mobile';
    const { data } = await recommendChart(sample, device);
    const result = data.data as unknown as { recommendations: ChartRecommendItem[] };
    recommendation.value = result.recommendations[0] || null;
    alternatives.value = result.recommendations.slice(1);
  } catch (e) {
    message.error('AI推荐获取失败，请稍后重试');
  } finally {
    loading.value = false;
  }
}

function applyRecommendation(chartType: string) {
  // Use config from the correct source: primary or the clicked alternative
  let config: Record<string, unknown> = {};
  if (chartType === recommendation.value?.chart_type) {
    config = recommendation.value.suggested_config || {};
  } else {
    const alt = alternatives.value.find(a => a.chart_type === chartType);
    config = alt?.suggested_config || {};
  }
  emit('apply', chartType, config);
}

function chartTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    bar: '柱状图',
    line: '折线图',
    pie: '饼图',
    scatter: '散点图',
    area: '面积图',
    radar: '雷达图',
    gauge: '仪表盘',
    table: '表格',
  };
  return labels[type] || type;
}

function confidenceColor(confidence?: number): string {
  if (confidence == null) return '#1677ff';
  if (confidence >= 0.8) return '#52c41a';
  if (confidence >= 0.6) return '#faad14';
  return '#ff4d4f';
}

onMounted(() => {
  runRuleScreen();
});
</script>

<style scoped lang="less">
.ai-chart-recommender {
  border-radius: 8px;
}

.rule-based {
  margin-bottom: 12px;
}

.recommendation {
  .reason {
    margin: 12px 0;
    color: var(--color-text-secondary);
    font-size: 13px;
    line-height: 1.6;
  }
}

.alternatives {
  margin: 12px 0;

  .label {
    font-size: 13px;
    color: var(--color-text-secondary);
    margin-right: 8px;
  }
}

.apply-btn {
  margin-top: 16px;
}
</style>
