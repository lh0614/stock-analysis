<template>
  <el-card v-if="prediction" shadow="never" class="prediction-card" :class="predictionClass">
    <template #header>
      <div class="card-header">
        <span class="header-title">AI 预测</span>
        <el-tag :type="getPredictionType(prediction.prediction.predicted_class)" size="large">
          {{ getPredictionLabel(prediction.prediction.predicted_class) }}
        </el-tag>
      </div>
    </template>

    <div class="prediction-content">
      <!-- 概率展示 -->
      <div class="probability-section">
        <div class="probability-item">
          <div class="probability-label">上涨概率</div>
          <div class="probability-value up">
            {{ (prediction.prediction.up_probability * 100).toFixed(1) }}%
          </div>
          <el-progress
            :percentage="Math.round(prediction.prediction.up_probability * 100)"
            :show-text="false"
            :color="'#67c23a'"
          />
        </div>
        <div class="probability-item">
          <div class="probability-label">下跌概率</div>
          <div class="probability-value down">
            {{ (prediction.prediction.down_probability * 100).toFixed(1) }}%
          </div>
          <el-progress
            :percentage="Math.round(prediction.prediction.down_probability * 100)"
            :show-text="false"
            :color="'#f56c6c'"
          />
        </div>
      </div>

      <!-- 置信度 -->
      <div class="confidence-section">
        <span class="confidence-label">预测置信度:</span>
        <el-tag :type="getConfidenceType(prediction.prediction.confidence)" size="small">
          {{ (prediction.prediction.confidence * 100).toFixed(1) }}%
        </el-tag>
      </div>

      <!-- 主要贡献因子 -->
      <div v-if="prediction.feature_importance?.length" class="feature-section">
        <div class="section-title">主要贡献因子</div>
        <div class="feature-list">
          <div
            v-for="(item, idx) in prediction.feature_importance"
            :key="idx"
            class="feature-item"
          >
            <span class="feature-name">{{ formatFeatureName(item.feature) }}</span>
            <el-progress
              :percentage="Math.round(item.importance * 100)"
              :show-text="false"
              :stroke-width="6"
            />
            <span class="feature-importance">{{ (item.importance * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <!-- 数据质量 -->
      <div class="quality-section">
        <span class="quality-label">数据质量:</span>
        <el-tag :type="getQualityType(prediction.data_quality)" size="small">
          {{ formatQualityScore(prediction.data_quality) }}
        </el-tag>
      </div>

      <!-- 警告信息 -->
      <el-alert
        v-if="prediction.warning"
        :title="prediction.warning"
        :type="getWarningType(prediction.warning)"
        show-icon
        :closable="false"
        class="prediction-warning"
      />

      <!-- 模型信息 -->
      <div v-if="showModelInfo" class="model-info">
        <el-divider content-position="left">模型信息</el-divider>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">模型版本:</span>
            <span class="info-value">{{ prediction.model_version }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">预测周期:</span>
            <span class="info-value">{{ prediction.target_horizon }} 天</span>
          </div>
          <div class="info-item">
            <span class="info-label">预测日期:</span>
            <span class="info-value">{{ prediction.trade_date }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  prediction: {
    type: Object,
    default: null
  },
  showModelInfo: {
    type: Boolean,
    default: false
  }
})

const predictionClass = computed(() => {
  if (!props.prediction) return ''
  const predictedClass = props.prediction.prediction?.predicted_class
  return predictedClass === 'up' ? 'prediction-up' : 'prediction-down'
})

function getPredictionLabel(predictedClass) {
  return predictedClass === 'up' ? '看涨' : '看跌'
}

function getPredictionType(predictedClass) {
  return predictedClass === 'up' ? 'success' : 'danger'
}

function getConfidenceType(confidence) {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.6) return 'warning'
  return 'danger'
}

function getQualityType(qualityScore) {
  if (qualityScore >= 0.9) return 'success'
  if (qualityScore >= 0.7) return ''
  if (qualityScore >= 0.5) return 'warning'
  return 'danger'
}

function formatQualityScore(score) {
  if (score >= 0.9) return 'A 级'
  if (score >= 0.7) return 'B 级'
  if (score >= 0.5) return 'C 级'
  return 'D 级'
}

function getWarningType(warning) {
  if (warning.includes('不可靠')) return 'error'
  if (warning.includes('低')) return 'warning'
  return 'info'
}

function formatFeatureName(feature) {
  const nameMap = {
    'return_5d': '5日收益',
    'return_20d': '20日收益',
    'return_60d': '60日收益',
    'volatility_20d': '20日波动率',
    'volatility_60d': '60日波动率',
    'volume_ratio_5_20': '5/20日量比',
    'volume_ratio_20_60': '20/60日量比',
    'rsi6': 'RSI6',
    'rsi12': 'RSI12',
    'macd': 'MACD',
    'macd_signal': 'MACD信号',
    'ma5': 'MA5',
    'ma10': 'MA10',
    'ma20': 'MA20',
    'ma60': 'MA60',
    'ma_bullish_alignment': '均线多头',
    'price_position_60d': '60日价格位置',
    'high_52w_distance': '52周高点距离',
    'breakout_20d_high': '20日突破',
    'pullback_to_ma20': '回踩MA20',
    'market_trend': '市场趋势',
    'market_volatility': '市场波动',
    'market_volume': '市场成交量',
    'industry_strength': '行业强度',
    'data_quality_score': '数据质量',
    'data_completeness': '数据完整度',
    'data_stale_days': '数据滞后天数',
  }
  return nameMap[feature] || feature
}
</script>

<style scoped>
.prediction-card {
  margin-bottom: 16px;
  border-left: 4px solid var(--el-border-color);
}

.prediction-card.prediction-up {
  border-left-color: var(--el-color-success);
}

.prediction-card.prediction-down {
  border-left-color: var(--el-color-danger);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-weight: 600;
  font-size: 15px;
}

.prediction-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.probability-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.probability-item {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.probability-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.probability-value {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 8px;
}

.probability-value.up {
  color: var(--el-color-success);
}

.probability-value.down {
  color: var(--el-color-danger);
}

.confidence-section,
.quality-section {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  font-size: 13px;
}

.confidence-label,
.quality-label {
  color: var(--el-text-color-secondary);
}

.feature-section {
  margin-top: 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: grid;
  grid-template-columns: 120px 1fr 60px;
  align-items: center;
  gap: 12px;
}

.feature-name {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.feature-importance {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-align: right;
}

.prediction-warning {
  margin-top: 8px;
}

.model-info {
  margin-top: 8px;
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.info-label {
  color: var(--el-text-color-secondary);
}

.info-value {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

@media (max-width: 600px) {
  .probability-section {
    grid-template-columns: 1fr;
  }

  .feature-item {
    grid-template-columns: 100px 1fr 50px;
    gap: 8px;
  }
}
</style>
