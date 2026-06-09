<template>
  <el-card v-if="environmentData" shadow="never" class="environment-card" :class="fitClass">
    <template #header>
      <div class="card-header">
        <span class="header-title">市场环境适配</span>
        <el-tag :type="getFitType(environmentData.fit_analysis?.fit_status)" size="large">
          {{ getFitLabel(environmentData.fit_analysis?.fit_status) }}
        </el-tag>
      </div>
    </template>

    <div class="environment-content">
      <!-- 策略环境标签 -->
      <div class="labels-section">
        <div class="section-title">策略适用环境</div>
        <div class="labels-grid">
          <div class="label-group">
            <span class="label-title">市场状态:</span>
            <div class="tag-list">
              <el-tag
                v-for="state in environmentData.strategy_labels?.market_states"
                :key="state"
                size="small"
                class="label-tag"
              >
                {{ formatMarketState(state) }}
              </el-tag>
            </div>
          </div>
          <div class="label-group">
            <span class="label-title">投资风格:</span>
            <div class="tag-list">
              <el-tag
                v-for="style in environmentData.strategy_labels?.styles"
                :key="style"
                size="small"
                type="info"
                class="label-tag"
              >
                {{ formatStyle(style) }}
              </el-tag>
            </div>
          </div>
        </div>
        <div class="适用说明">
          {{ environmentData.strategy_labels?.适用说明 }}
        </div>
      </div>

      <!-- 当前市场状态 -->
      <div class="market-section">
        <div class="section-title">当前市场状态</div>
        <div class="market-grid">
          <div class="market-item">
            <span class="market-label">状态:</span>
            <el-tag :type="getMarketStateType(environmentData.current_market?.state)" size="small">
              {{ formatMarketState(environmentData.current_market?.state) }}
            </el-tag>
          </div>
          <div class="market-item">
            <span class="market-label">趋势:</span>
            <el-tag :type="getTrendType(environmentData.current_market?.trend)" size="small">
              {{ formatTrend(environmentData.current_market?.trend) }}
            </el-tag>
          </div>
          <div class="market-item">
            <span class="market-label">波动:</span>
            <el-tag :type="getVolatilityType(environmentData.current_market?.volatility_level)" size="small">
              {{ formatVolatility(environmentData.current_market?.volatility_level) }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 适配度分析 -->
      <div class="fit-section">
        <div class="fit-score-bar">
          <div class="score-label">适配度评分</div>
          <el-progress
            :percentage="Math.round((environmentData.fit_analysis?.fit_score || 0) * 100)"
            :color="getFitColor(environmentData.fit_analysis?.fit_score)"
            :stroke-width="20"
          >
            <span class="score-text">{{ ((environmentData.fit_analysis?.fit_score || 0) * 100).toFixed(0) }}</span>
          </el-progress>
        </div>
        <div class="fit-message">
          {{ environmentData.fit_analysis?.fit_message }}
        </div>
      </div>

      <!-- 建议 -->
      <el-alert
        v-if="environmentData.fit_analysis?.recommendation"
        :title="environmentData.fit_analysis.recommendation"
        :type="getRecommendationType(environmentData.fit_analysis.fit_status)"
        show-icon
        :closable="false"
        class="recommendation-alert"
      />

      <!-- 详细信息（可选） -->
      <div v-if="showDetails" class="details-section">
        <el-divider content-position="left">详细信息</el-divider>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">持有周期:</span>
            <span class="info-value">{{ environmentData.strategy_labels?.horizon }} 天</span>
          </div>
          <div class="info-item">
            <span class="info-label">调仓频率:</span>
            <span class="info-value">{{ environmentData.strategy_labels?.rebalance }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">分析日期:</span>
            <span class="info-value">{{ environmentData.current_market?.trade_date }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  environmentData: {
    type: Object,
    default: null
  },
  showDetails: {
    type: Boolean,
    default: false
  }
})

const fitClass = computed(() => {
  if (!props.environmentData) return ''
  const fitStatus = props.environmentData.fit_analysis?.fit_status
  return fitStatus === 'matched' ? 'fit-matched' : (fitStatus === 'mismatched' ? 'fit-mismatched' : 'fit-uncertain')
})

function getFitLabel(fitStatus) {
  const labelMap = {
    matched: '适配',
    mismatched: '不适配',
    uncertain: '不确定'
  }
  return labelMap[fitStatus] || '未知'
}

function getFitType(fitStatus) {
  const typeMap = {
    matched: 'success',
    mismatched: 'danger',
    uncertain: 'warning'
  }
  return typeMap[fitStatus] || 'info'
}

function getFitColor(fitScore) {
  if (fitScore >= 0.8) return '#67c23a'
  if (fitScore >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

function getRecommendationType(fitStatus) {
  const typeMap = {
    matched: 'success',
    mismatched: 'warning',
    uncertain: 'info'
  }
  return typeMap[fitStatus] || 'info'
}

function formatMarketState(state) {
  const stateMap = {
    trend: '趋势市',
    oscillation: '震荡市',
    high_volatility: '高波动',
    low_volatility: '低波动',
    unknown: '未知'
  }
  return stateMap[state] || state
}

function formatStyle(style) {
  const styleMap = {
    growth: '成长',
    value: '价值',
    momentum: '动量',
    mean_reversion: '均值回归'
  }
  return styleMap[style] || style
}

function formatTrend(trend) {
  const trendMap = {
    bullish: '上涨',
    bearish: '下跌',
    neutral: '中性'
  }
  return trendMap[trend] || trend
}

function formatVolatility(level) {
  const levelMap = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return levelMap[level] || level
}

function getMarketStateType(state) {
  if (state === 'trend') return 'success'
  if (state === 'oscillation') return 'warning'
  if (state === 'high_volatility') return 'danger'
  return 'info'
}

function getTrendType(trend) {
  if (trend === 'bullish') return 'success'
  if (trend === 'bearish') return 'danger'
  return 'info'
}

function getVolatilityType(level) {
  if (level === 'high') return 'danger'
  if (level === 'low') return 'success'
  return 'warning'
}
</script>

<style scoped>
.environment-card {
  margin-bottom: 16px;
  border-left: 4px solid var(--el-border-color);
}

.environment-card.fit-matched {
  border-left-color: var(--el-color-success);
}

.environment-card.fit-mismatched {
  border-left-color: var(--el-color-danger);
}

.environment-card.fit-uncertain {
  border-left-color: var(--el-color-warning);
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

.environment-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}

.labels-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.labels-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.label-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  min-width: 80px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.label-tag {
  font-size: 12px;
}

.适用说明 {
  font-size: 13px;
  color: var(--el-text-color-regular);
  padding: 8px;
  background: var(--el-bg-color);
  border-radius: 4px;
  border-left: 3px solid var(--el-color-primary);
}

.market-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.market-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.market-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.market-label {
  color: var(--el-text-color-secondary);
}

.fit-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.fit-score-bar {
  margin-bottom: 12px;
}

.score-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.score-text {
  font-weight: 700;
  font-size: 14px;
}

.fit-message {
  font-size: 13px;
  color: var(--el-text-color-regular);
  padding: 8px;
  background: var(--el-bg-color);
  border-radius: 4px;
}

.recommendation-alert {
  margin-top: 8px;
}

.details-section {
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
  .market-grid {
    grid-template-columns: 1fr;
  }

  .label-group {
    flex-direction: column;
    align-items: flex-start;
  }

  .label-title {
    min-width: auto;
  }
}
</style>
