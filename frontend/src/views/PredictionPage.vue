<template>
  <div class="prediction-page">
    <a-row :gutter="[16, 16]">
      <!-- Left: controls -->
      <a-col :xs="24" :md="6">
        <a-card title="预测设置" size="small">
          <a-form layout="vertical">
            <a-form-item>
              <template #label>
                预测指标
                <a-tooltip>
                  <template #title>
                    <div class="method-tooltip">
                      <p><strong>ARIMA 时间序列预测模型</strong></p>
                      <p>• 营业收入：基于历史收入时序数据，预测未来趋势</p>
                      <p>• 毛利润：根据历史毛利数据，结合季节性因素预测</p>
                      <p>• DSO：应收账款周转天数，预测资金回笼效率</p>
                      <p>• 应收账款账龄：预测各账龄段的AR分布</p>
                      <p>• 需要至少 12 期历史数据才能进行预测</p>
                      <p>• 预测结果仅供参考，实际数据可能存在较大偏差</p>
                    </div>
                  </template>
                  <QuestionCircleOutlined class="method-icon" />
                </a-tooltip>
                <span class="required-star">*</span>
              </template>
              <a-select v-model:value="metricType" placeholder="选择指标" @change="onMetricChange">
                <a-select-option value="revenue">营业收入</a-select-option>
                <a-select-option value="gross_profit">毛利润</a-select-option>
                <a-select-option value="dso">应收账款周转天数 (DSO)</a-select-option>
                <a-select-option value="ar_aging">应收账款账龄</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="预测范围">
              <a-slider v-model:value="horizonMonths" :min="1" :max="12" :marks="{ 1: '1月', 3: '3月', 6: '6月', 12: '12月' }" />
            </a-form-item>
            <a-button type="primary" block :loading="creating" @click="handlePredict">
              开始预测
            </a-button>
          </a-form>
        </a-card>

        <!-- Rejection UI -->
        <a-alert
          v-if="prediction?.rejected_reason"
          class="rejection-alert"
          message="预测已被驳回"
          :description="prediction.rejected_reason"
          type="error"
          show-icon
          closable
        />
      </a-col>

      <!-- Right: chart -->
      <a-col :xs="24" :md="18">
        <a-card title="预测趋势图" size="small" :loading="loading">
          <v-chart
            v-if="chartOption"
            class="prediction-chart"
            :option="chartOption"
            renderer="canvas"
            :autoresize="true"
          />
          <a-empty v-else description="选择指标并点击预测" />
        </a-card>

        <!-- Accuracy info -->
        <a-card v-if="prediction?.mape !== undefined && prediction.mape !== null" title="模型信息" size="small" style="margin-top: 16px">
          <a-descriptions :column="isMobile ? 1 : 4" size="small" bordered>
            <a-descriptions-item label="指标">{{ prediction.metric_name }}</a-descriptions-item>
            <a-descriptions-item label="模型类型">{{ prediction.model_type || '-' }}</a-descriptions-item>
            <a-descriptions-item label="MAPE">
              {{ prediction.mape !== undefined && prediction.mape !== null ? `${(prediction.mape * 100).toFixed(2)}%` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="训练窗口">{{ prediction.training_window || '-' }} 期</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { QuestionCircleOutlined } from '@ant-design/icons-vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components';
import type { EChartsOption } from 'echarts';
import { createPrediction, getPrediction } from '@/api/predictions';
import type { PredictionResult, PredictionType } from '@/types/prediction';

use([
  CanvasRenderer,
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
]);

const metricType = ref<PredictionType>('revenue');
const horizonMonths = ref(3);
const loading = ref(false);
const creating = ref(false);
const prediction = ref<PredictionResult | null>(null);

let pollingTimer: ReturnType<typeof setInterval> | null = null;
let currentPredictionId: number | null = null;
let pollingStartTime = 0;
const POLLING_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes max polling

const isMobile = computed(() => window.innerWidth < 768);

function onMetricChange() {
  prediction.value = null;
  stopPolling();
}

async function handlePredict() {
  creating.value = true;
  stopPolling();
  try {
    const { data } = await createPrediction({
      metric_name: metricType.value,
      prediction_type: metricType.value,
      horizon: horizonMonths.value,
    });
    const result = data.data as PredictionResult;
    currentPredictionId = result.id;
    prediction.value = result;

    // Start polling for completion
    startPolling(result.id);
  } finally {
    creating.value = false;
  }
}

async function fetchPrediction(id: number) {
  try {
    const { data } = await getPrediction(id);
    prediction.value = data.data as PredictionResult;

    // Show insufficient data message if present
    const resultData = data.data as unknown as Record<string, unknown>;
    if (resultData?.message && typeof resultData.message === 'string') {
      message.warning(resultData.message);
      stopPolling();
      return;
    }

    // Check completion using the new response format
    const isComplete = prediction.value.forecast_values && Object.keys(prediction.value.forecast_values).length > 0;
    const hasError = prediction.value.rejected_reason || prediction.value.error_message;
    if (isComplete || hasError) {
      stopPolling();
    }
  } catch {
    stopPolling();
  }
}

function startPolling(id: number) {
  stopPolling();
  pollingStartTime = Date.now();
  pollingTimer = setInterval(() => {
    if (document.hidden) return;
    // Timeout after 5 minutes — Celery may not be running
    if (Date.now() - pollingStartTime > POLLING_TIMEOUT_MS) {
      stopPolling();
      prediction.value = {
        ...prediction.value,
        status: 'failed',
        rejected_reason: '预测任务超时（5分钟未完成），请确认 Celery 工作进程是否正常运行。',
      } as PredictionResult;
      return;
    }
    if (prediction.value && (prediction.value.status === 'pending' || prediction.value.status === 'running' || prediction.value.status === 'processing')) {
      fetchPrediction(id);
    }
  }, 5000);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

const chartOption = computed<EChartsOption | null>(() => {
  if (!prediction.value) return null;
  const p = prediction.value;

  // Handle new backend response format (forecast_values + confidence_band)
  let dates: string[] = [];
  let actualValues: (number | null)[] = [];
  let forecastValues: (number | null)[] = [];
  let upper: number[] = [];
  let lower: number[] = [];

  if (p.data_points?.length) {
    // Old format: array of data points
    const points = p.data_points;
    dates = points.map((p) => p.date);
    upper = points.map((p) => p.upper_bound);
    lower = points.map((p) => p.lower_bound);
    actualValues = points.map((p) => (p.is_actual ? p.value : null));
    forecastValues = points.map((p) => (!p.is_actual ? p.value : null));
  } else if (p.forecast_values && Object.keys(p.forecast_values).length > 0) {
    // New format: combine historical + forecast for continuous chart
    const histPeriods = p.historical_values ? Object.keys(p.historical_values).sort() : [];
    const forePeriods = Object.keys(p.forecast_values).sort();

    // Historical actual values
    const histValues = histPeriods.map((period) => p.historical_values![period]);
    const histActual: (number | null)[] = histPeriods.map((_period, i) => histValues[i]);
    const histForecast: (number | null)[] = histPeriods.map(() => null);

    // Forecast values
    const foreValues = forePeriods.map((period) => p.forecast_values![period]);
    const foreActual: (number | null)[] = forePeriods.map(() => null);
    const foreForecast: (number | null)[] = forePeriods.map((_period, i) => foreValues[i]);

    // Merge dates and series
    dates = [...histPeriods, ...forePeriods];
    actualValues = [...histActual, ...foreActual];
    forecastValues = [...histForecast, ...foreForecast];

    // Confidence band only for forecast periods
    upper = [...histPeriods.map(() => 0), ...forePeriods.map((period, i) => p.confidence_band?.[period]?.upper ?? (foreValues[i] ?? 0) * 1.1)];
    lower = [...histPeriods.map(() => 0), ...forePeriods.map((period, i) => p.confidence_band?.[period]?.lower ?? (foreValues[i] ?? 0) * 0.9)];
  } else {
    return null;
  }

  // Build stacked area for confidence band (upper - lower)
  const bandUpper = upper.map((u, i) => u - lower[i]);

  return {
    tooltip: {
      trigger: 'axis',
      formatter: ((params: Array<{ seriesName: string; value: number; dataIndex: number }>) => {
        if (!Array.isArray(params) || params.length === 0) return '';
        const date = dates[params[0].dataIndex];
        const lines = params.map((p) => `${p.seriesName}: ${p.value?.toFixed(2) ?? '-'}`).join('<br/>');
        return `${date}<br/>${lines}`;
      }) as any,
    },
    legend: {
      data: ['历史值', '预测值', '置信区间'],
      bottom: 0,
    },
    grid: {
      top: 40,
      bottom: 60,
      left: 60,
      right: 20,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
    },
    series: [
      // Confidence band (stacked area)
      {
        name: '置信区间',
        type: 'line',
        stack: 'confidence',
        data: lower,
        lineStyle: { opacity: 0 },
        symbol: 'none',
        areaStyle: { color: 'rgba(22, 119, 255, 0.15)' },
        z: 1,
      },
      {
        name: '置信区间',
        type: 'line',
        stack: 'confidence',
        data: bandUpper,
        lineStyle: { opacity: 0 },
        symbol: 'none',
        areaStyle: { color: 'rgba(22, 119, 255, 0.15)' },
        z: 1,
      },
      // Historical values
      {
        name: '历史值',
        type: 'line',
        data: actualValues,
        lineStyle: { width: 2, color: '#1677ff' },
        itemStyle: { color: '#1677ff' },
        z: 2,
      },
      // Forecast values
      {
        name: '预测值',
        type: 'line',
        data: forecastValues,
        lineStyle: { width: 2, color: '#faad14', type: 'dashed' },
        itemStyle: { color: '#faad14' },
        z: 2,
      },
    ],
  };
});

onMounted(() => {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopPolling();
    } else if (currentPredictionId) {
      startPolling(currentPredictionId);
    }
  });
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped lang="less">
.prediction-page {
  .prediction-chart {
    width: 100%;
    height: 400px;
  }

  .rejection-alert {
    margin-top: 16px;
  }

  .method-icon {
    margin-left: 4px;
    color: #888;
    cursor: help;
    font-size: 14px;
  }

  .required-star {
    color: #ff4d4f;
    margin-left: 2px;
  }
}

:deep(.method-tooltip) {
  max-width: 320px;
  font-size: 12px;
  line-height: 1.8;

  p {
    margin: 0;
  }

  strong {
    font-size: 13px;
    color: #1677ff;
  }
}

@media (max-width: 767px) {
  .prediction-chart {
    height: 280px;
  }
}
</style>
