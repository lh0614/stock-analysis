<template>
  <el-card v-if="riskData" shadow="never" class="portfolio-risk-card" :class="riskClass">
    <template #header>
      <div class="card-header">
        <span class="header-title">组合风险分析</span>
        <el-tag :type="getRiskType(riskData.overall_risk_level)" size="large">
          {{ getRiskLabel(riskData.overall_risk_level) }}
        </el-tag>
      </div>
    </template>

    <div class="risk-content">
      <!-- 组合概览 -->
      <div class="overview-section">
        <div class="overview-grid">
          <div class="overview-item">
            <div class="overview-label">候选数量</div>
            <div class="overview-value">{{ riskData.total_candidates }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">选中持仓</div>
            <div class="overview-value primary">{{ riskData.selected_positions }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">策略数量</div>
            <div class="overview-value">{{ riskData.total_strategies }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">多样性评分</div>
            <div class="overview-value">{{ riskData.portfolio_metrics?.diversity_score?.toFixed(0) }}</div>
          </div>
        </div>
      </div>

      <!-- 信号重叠分析 -->
      <div v-if="riskData.overlap_analysis" class="overlap-section">
        <div class="section-title">信号重叠度</div>
        <div class="overlap-bars">
          <div
            v-for="(count, signals) in riskData.overlap_analysis"
            :key="signals"
            class="overlap-bar"
          >
            <div class="overlap-info">
              <span class="overlap-label">{{ signals }} 个策略</span>
              <span class="overlap-count">{{ count }} 只股票</span>
            </div>
            <el-progress
              :percentage="Math.round((count / riskData.total_candidates) * 100)"
              :color="getOverlapColor(parseInt(signals))"
              :stroke-width="16"
              :show-text="false"
            />
          </div>
        </div>
      </div>

      <!-- 集中度风险 -->
      <div class="concentration-section">
        <div class="section-title">集中度风险</div>
        <div class="concentration-indicator">
          <el-tag :type="getConcentrationType(riskData.risk_analysis?.concentration_risk)" size="large">
            {{ getConcentrationLabel(riskData.risk_analysis?.concentration_risk) }}
          </el-tag>
          <span class="concentration-desc">
            行业集中度: {{ (riskData.risk_analysis?.max_industry_ratio * 100)?.toFixed(1) }}%
          </span>
        </div>
      </div>

      <!-- 行业分布 -->
      <div v-if="riskData.risk_analysis?.industry_distribution" class="distribution-section">
        <div class="section-title">行业分布</div>
        <div class="distribution-list">
          <div
            v-for="(count, industry) in riskData.risk_analysis.industry_distribution"
            :key="industry"
            class="distribution-item"
          >
            <span class="distribution-name">{{ industry }}</span>
            <div class="distribution-bar">
              <el-progress
                :percentage="Math.round((count / riskData.selected_positions) * 100)"
                :stroke-width="12"
                :show-text="false"
              />
            </div>
            <span class="distribution-value">{{ count }} ({{ ((count / riskData.selected_positions) * 100).toFixed(1) }}%)</span>
          </div>
        </div>
      </div>

      <!-- 风格分布 -->
      <div v-if="riskData.risk_analysis?.style_distribution && Object.keys(riskData.risk_analysis.style_distribution).length > 0" class="distribution-section">
        <div class="section-title">风格分布</div>
        <div class="style-pills">
          <el-tag
            v-for="(count, style) in riskData.risk_analysis.style_distribution"
            :key="style"
            size="large"
            class="style-pill"
          >
            {{ style }}: {{ count }}
          </el-tag>
        </div>
      </div>

      <!-- 置信度分布 -->
      <div v-if="riskData.portfolio_metrics" class="confidence-section">
        <div class="section-title">信号置信度分布</div>
        <div class="confidence-grid">
          <div class="confidence-item high">
            <div class="confidence-label">高置信</div>
            <div class="confidence-count">{{ riskData.portfolio_metrics.high_confidence_count }}</div>
          </div>
          <div class="confidence-item medium">
            <div class="confidence-label">中置信</div>
            <div class="confidence-count">{{ riskData.portfolio_metrics.medium_confidence_count }}</div>
          </div>
          <div class="confidence-item low">
            <div class="confidence-label">低置信</div>
            <div class="confidence-count">{{ riskData.portfolio_metrics.low_confidence_count }}</div>
          </div>
        </div>
      </div>

      <!-- 风险警告 -->
      <div v-if="riskData.warnings?.length > 0" class="warnings-section">
        <div class="section-title">风险警告</div>
        <el-alert
          v-for="(warning, idx) in riskData.warnings"
          :key="idx"
          :title="warning"
          type="warning"
          show-icon
          :closable="false"
          class="warning-alert"
        />
      </div>

      <!-- 优化建议 -->
      <div v-if="riskData.recommendations?.length > 0" class="recommendations-section">
        <div class="section-title">优化建议</div>
        <ul class="recommendations-list">
          <li v-for="(rec, idx) in riskData.recommendations" :key="idx" class="recommendation-item">
            {{ rec }}
          </li>
        </ul>
      </div>

      <!-- 详细信息（可选） -->
      <div v-if="showDetails && riskData.selected_symbols" class="details-section">
        <el-divider content-position="left">选中股票</el-divider>
        <div class="symbols-list">
          <el-tag
            v-for="symbol in riskData.selected_symbols"
            :key="symbol"
            size="small"
            class="symbol-tag"
          >
            {{ symbol }}
          </el-tag>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  riskData: {
    type: Object,
    default: null
  },
  showDetails: {
    type: Boolean,
    default: false
  }
})

const riskClass = computed(() => {
  if (!props.riskData) return ''
  const riskLevel = props.riskData.overall_risk_level
  return `risk-${riskLevel}`
})

function getRiskLabel(level) {
  const labelMap = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return labelMap[level] || '未知'
}

function getRiskType(level) {
  const typeMap = {
    low: 'success',
    medium: 'warning',
    high: 'danger'
  }
  return typeMap[level] || 'info'
}

function getConcentrationLabel(level) {
  const labelMap = {
    low: '低集中度',
    medium: '中集中度',
    high: '高集中度'
  }
  return labelMap[level] || '未知'
}

function getConcentrationType(level) {
  const typeMap = {
    low: 'success',
    medium: 'warning',
    high: 'danger'
  }
  return typeMap[level] || 'info'
}

function getOverlapColor(signalCount) {
  if (signalCount >= 3) return '#67c23a'
  if (signalCount === 2) return '#e6a23c'
  return '#909399'
}
</script>

<style scoped>
.portfolio-risk-card {
  margin-bottom: 16px;
  border-left: 4px solid var(--el-border-color);
}

.portfolio-risk-card.risk-low {
  border-left-color: var(--el-color-success);
}

.portfolio-risk-card.risk-medium {
  border-left-color: var(--el-color-warning);
}

.portfolio-risk-card.risk-high {
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

.risk-content {
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

.overview-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.overview-item {
  text-align: center;
}

.overview-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.overview-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.overview-value.primary {
  color: var(--el-color-primary);
}

.overlap-section,
.concentration-section,
.distribution-section,
.confidence-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.overlap-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overlap-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overlap-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.overlap-label {
  color: var(--el-text-color-regular);
  font-weight: 600;
}

.overlap-count {
  color: var(--el-text-color-secondary);
}

.concentration-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
}

.concentration-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.distribution-item {
  display: grid;
  grid-template-columns: 100px 1fr 100px;
  align-items: center;
  gap: 12px;
}

.distribution-name {
  font-size: 13px;
  color: var(--el-text-color-regular);
  font-weight: 500;
}

.distribution-value {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: right;
}

.style-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.style-pill {
  font-size: 13px;
}

.confidence-section {
}

.confidence-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.confidence-item {
  text-align: center;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-bg-color);
}

.confidence-item.high {
  border: 2px solid var(--el-color-success);
}

.confidence-item.medium {
  border: 2px solid var(--el-color-warning);
}

.confidence-item.low {
  border: 2px solid var(--el-color-info);
}

.confidence-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.confidence-count {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.warnings-section,
.recommendations-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.warning-alert {
  margin-bottom: 8px;
}

.warning-alert:last-child {
  margin-bottom: 0;
}

.recommendations-list {
  margin: 0;
  padding-left: 20px;
}

.recommendation-item {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
  line-height: 1.6;
}

.recommendation-item:last-child {
  margin-bottom: 0;
}

.details-section {
  margin-top: 8px;
}

.symbols-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.symbol-tag {
  font-family: monospace;
}

@media (max-width: 768px) {
  .overview-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .confidence-grid {
    grid-template-columns: 1fr;
  }

  .distribution-item {
    grid-template-columns: 80px 1fr 80px;
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
