<template>
  <div class="health-score-detail">
    <div class="score-header">
      <div class="score-main">
        <div class="score-value">{{ displayScore }}</div>
        <div class="score-meta">
          <el-tag :type="getStatusType(health.status)" size="large">
            {{ getStatusLabel(health.status) }}
          </el-tag>
          <el-tag :type="getConfidenceType(health.confidence_level)" size="small" class="confidence-tag">
            置信度: {{ getConfidenceLabel(health.confidence_level) }}
          </el-tag>
        </div>
      </div>
      <div class="score-stats">
        <div class="stat-item">
          <span class="stat-label">信号数</span>
          <strong class="stat-value">{{ health.recent_signals_count || 0 }}</strong>
        </div>
        <div class="stat-item">
          <span class="stat-label">成熟信号</span>
          <strong class="stat-value">{{ health.recent_matured_signals_count || 0 }}</strong>
        </div>
        <div class="stat-item">
          <span class="stat-label">胜率</span>
          <strong class="stat-value">{{ formatPercent(health.recent_win_rate) }}</strong>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均收益</span>
          <strong class="stat-value">{{ formatPercent(health.recent_avg_return) }}</strong>
        </div>
      </div>
    </div>

    <template v-if="subScoreItems.length">
      <el-divider content-position="left">健康评分拆解（7维度）</el-divider>
      <div class="subscore-grid">
        <div v-for="item in subScoreItems" :key="item.key" class="subscore-row">
          <div class="subscore-head">
            <span class="subscore-label">{{ item.label }}</span>
            <strong class="subscore-value">{{ item.value.toFixed(1) }}</strong>
          </div>
          <el-progress
            :percentage="Math.round(item.value)"
            :status="getScoreProgressStatus(item.value)"
            :show-text="false"
          />
        </div>
      </div>
    </template>

    <template v-if="health.degradation_signals?.length">
      <el-divider content-position="left">衰减信号</el-divider>
      <div class="degradation-list">
        <el-alert
          v-for="(signal, idx) in health.degradation_signals"
          :key="idx"
          :title="signal"
          type="warning"
          :closable="false"
          show-icon
          class="degradation-alert"
        />
      </div>
    </template>

    <template v-if="health.recommendations?.length">
      <el-divider content-position="left">建议操作</el-divider>
      <div class="recommendation-list">
        <el-tag
          v-for="(item, idx) in health.recommendations"
          :key="idx"
          type="info"
          effect="plain"
          class="recommendation-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </template>

    <template v-if="health.data_quality">
      <el-divider content-position="left">数据质量</el-divider>
      <div class="quality-info">
        <div class="quality-grade">
          <span class="quality-label">综合等级:</span>
          <el-tag :type="getQualityType(health.data_quality.quality_grade)" size="large">
            {{ health.data_quality.quality_grade || '-' }}
          </el-tag>
        </div>
        <el-alert
          v-if="health.data_quality.recommendation"
          :title="health.data_quality.recommendation"
          type="info"
          show-icon
          :closable="false"
          class="quality-alert"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  health: {
    type: Object,
    required: true
  }
})

const displayScore = computed(() => {
  const score = props.health.health_score
  return score != null ? Number(score).toFixed(1) : '-'
})

const HEALTH_SUB_SCORE_LABELS = {
  signal_activity: '信号活跃度',
  signal_maturity: '信号成熟度',
  win_rate: '胜率质量',
  return_score: '收益质量',
  drawdown: '回撤控制',
  data_quality: '数据质量',
  market_fit: '市场适配'
}

const subScoreItems = computed(() => {
  const scores = props.health?.sub_scores || {}
  return Object.entries(HEALTH_SUB_SCORE_LABELS)
    .filter(([key]) => scores[key] !== undefined && scores[key] !== null)
    .map(([key, label]) => ({ key, label, value: Number(scores[key]) }))
})

function getStatusLabel(status) {
  const map = { healthy: '健康', degraded: '衰减', failing: '失效' }
  return map[status] || status || '-'
}

function getStatusType(status) {
  const map = { healthy: 'success', degraded: 'warning', failing: 'danger' }
  return map[status] || 'info'
}

function getConfidenceLabel(level) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[level] || level || '-'
}

function getConfidenceType(level) {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[level] || 'info'
}

function getScoreProgressStatus(score) {
  if (score >= 70) return 'success'
  if (score >= 50) return 'warning'
  return 'exception'
}

function getQualityType(grade) {
  const map = { A: 'success', B: '', C: 'warning', D: 'danger' }
  return map[grade] || 'info'
}

function formatPercent(value) {
  if (value === null || value === undefined) return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}
</script>

<style scoped>
.health-score-detail {
  padding: 4px 0;
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.score-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-value {
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
  color: var(--el-color-primary);
}

.score-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-tag {
  margin-left: 4px;
}

.score-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(100px, 1fr));
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  background: var(--el-fill-color-blank);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.subscore-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 12px 18px;
  margin-top: 12px;
}

.subscore-row {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-blank);
}

.subscore-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.subscore-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.subscore-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.degradation-list {
  margin-top: 12px;
}

.degradation-alert {
  margin-bottom: 8px;
}

.degradation-alert:last-child {
  margin-bottom: 0;
}

.recommendation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.recommendation-tag {
  font-size: 13px;
}

.quality-info {
  margin-top: 12px;
}

.quality-grade {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.quality-label {
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.quality-alert {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .score-header {
    flex-direction: column;
  }

  .score-stats {
    grid-template-columns: repeat(4, minmax(80px, 1fr));
  }

  .subscore-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .score-stats {
    grid-template-columns: repeat(2, minmax(80px, 1fr));
  }
}
</style>
