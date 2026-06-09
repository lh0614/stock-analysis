<template>
  <el-card v-if="qualitySummary" shadow="never" class="data-quality-card" :class="qualityClass">
    <template #header>
      <div class="card-header">
        <span class="header-title">数据质量</span>
        <el-tag :type="getQualityType(qualitySummary.quality_grade)" size="large">
          {{ qualitySummary.quality_grade || '-' }}
        </el-tag>
      </div>
    </template>

    <div class="quality-content">
      <div v-if="qualitySummary.total_symbols > 0" class="quality-distribution">
        <div class="distribution-title">质量分布</div>
        <div class="distribution-grid">
          <div class="distribution-item">
            <el-tag type="success" size="small">A级</el-tag>
            <span class="distribution-count">{{ qualityCounts.A || 0 }}</span>
          </div>
          <div class="distribution-item">
            <el-tag type="" size="small">B级</el-tag>
            <span class="distribution-count">{{ qualityCounts.B || 0 }}</span>
          </div>
          <div class="distribution-item">
            <el-tag type="warning" size="small">C级</el-tag>
            <span class="distribution-count">{{ qualityCounts.C || 0 }}</span>
          </div>
          <div class="distribution-item">
            <el-tag type="danger" size="small">D级</el-tag>
            <span class="distribution-count">{{ qualityCounts.D || 0 }}</span>
          </div>
        </div>
        <div class="total-info">
          总计: <strong>{{ qualitySummary.total_symbols }}</strong> 个标的
        </div>
      </div>

      <el-alert
        v-if="qualitySummary.recommendation"
        :title="qualitySummary.recommendation"
        :type="getRecommendationType(qualitySummary.quality_grade)"
        show-icon
        :closable="false"
        class="quality-recommendation"
      />

      <div v-if="qualitySummary.backtest_period_days" class="quality-meta">
        <span class="meta-label">回测周期:</span>
        <span class="meta-value">{{ qualitySummary.backtest_period_days }} 天</span>
      </div>

      <div v-if="showDetails && detailedItems.length" class="quality-details">
        <el-divider content-position="left">详细信息</el-divider>
        <div class="detail-items">
          <div v-for="item in detailedItems" :key="item.label" class="detail-item">
            <span class="detail-label">{{ item.label }}:</span>
            <span class="detail-value">{{ item.value }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  qualitySummary: {
    type: Object,
    default: null
  },
  showDetails: {
    type: Boolean,
    default: false
  }
})

const qualityClass = computed(() => {
  const grade = props.qualitySummary?.quality_grade
  return grade ? `quality-${grade.toLowerCase()}` : ''
})

const qualityCounts = computed(() => {
  const summary = props.qualitySummary || {}
  return summary.quality_distribution || {
    A: summary.A || 0,
    B: summary.B || 0,
    C: summary.C || 0,
    D: summary.D || 0
  }
})

const detailedItems = computed(() => {
  if (!props.qualitySummary) return []
  const items = []
  const summary = props.qualitySummary

  if (summary.avg_completeness != null) {
    items.push({
      label: '平均完整度',
      value: `${(summary.avg_completeness * 100).toFixed(1)}%`
    })
  }

  if (summary.avg_consistency != null) {
    items.push({
      label: '平均一致性',
      value: `${(summary.avg_consistency * 100).toFixed(1)}%`
    })
  }

  if (summary.avg_recency_score != null) {
    items.push({
      label: '平均时效性',
      value: summary.avg_recency_score.toFixed(1)
    })
  }

  if (summary.average_stale_days != null) {
    items.push({
      label: '平均滞后天数',
      value: `${summary.average_stale_days} 天`
    })
  }

  if (summary.latest_trade_date) {
    items.push({
      label: '最新交易日',
      value: summary.latest_trade_date
    })
  }

  if (summary.missing_factor_data != null) {
    items.push({
      label: '缺失数据标的',
      value: `${summary.missing_factor_data} 个`
    })
  }

  return items
})

function getQualityType(grade) {
  const map = { A: 'success', B: '', C: 'warning', D: 'danger' }
  return map[grade] || 'info'
}

function getRecommendationType(grade) {
  const map = { A: 'success', B: 'info', C: 'warning', D: 'error' }
  return map[grade] || 'info'
}
</script>

<style scoped>
.data-quality-card {
  border-left: 4px solid var(--el-border-color);
}

.data-quality-card.quality-a {
  border-left-color: var(--el-color-success);
}

.data-quality-card.quality-b {
  border-left-color: var(--el-color-primary);
}

.data-quality-card.quality-c {
  border-left-color: var(--el-color-warning);
}

.data-quality-card.quality-d {
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

.quality-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quality-distribution {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.distribution-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
}

.distribution-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

.distribution-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background: var(--el-fill-color-blank);
  border-radius: 4px;
}

.distribution-count {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.total-info {
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.total-info strong {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.quality-recommendation {
  margin-top: 4px;
}

.quality-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  font-size: 13px;
}

.meta-label {
  color: var(--el-text-color-secondary);
}

.meta-value {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.quality-details {
  margin-top: 8px;
}

.detail-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}

.detail-label {
  color: var(--el-text-color-secondary);
}

.detail-value {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

@media (max-width: 600px) {
  .distribution-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
