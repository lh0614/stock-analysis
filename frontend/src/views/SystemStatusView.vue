<template>
  <div class="rb-page system-status-page">
    <h1 class="rb-page-title">系统状态</h1>
    <p class="rb-page-desc">监控系统整体运行状态、策略闭环执行情况和数据质量</p>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <StrategyCycleStatus ref="cycleStatusRef" />
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="rb-card stats-card">
          <template #header>
            <div class="rb-page-header">
              <span>策略统计</span>
              <el-button link type="primary" :loading="statsLoading" @click="loadStats">刷新</el-button>
            </div>
          </template>

          <div v-loading="statsLoading" class="stats-grid">
            <div class="stat-tile">
              <span class="stat-label">总策略数</span>
              <strong class="stat-value">{{ stats.total_strategies || 0 }}</strong>
            </div>
            <div class="stat-tile">
              <span class="stat-label">活跃策略</span>
              <strong class="stat-value stat-active">{{ stats.active_strategies || 0 }}</strong>
            </div>
            <div class="stat-tile">
              <span class="stat-label">健康策略</span>
              <strong class="stat-value stat-healthy">{{ stats.healthy_strategies || 0 }}</strong>
            </div>
            <div class="stat-tile">
              <span class="stat-label">衰减策略</span>
              <strong class="stat-value stat-degraded">{{ stats.degraded_strategies || 0 }}</strong>
            </div>
          </div>

          <el-divider />

          <div class="status-breakdown">
            <div class="breakdown-title">策略状态分布</div>
            <div class="breakdown-list">
              <div v-for="item in statusBreakdown" :key="item.status" class="breakdown-item">
                <el-tag :type="item.type" size="small">{{ item.label }}</el-tag>
                <span class="breakdown-count">{{ item.count }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="rb-card data-card">
          <template #header>
            <div class="rb-page-header">
              <span>数据仓状态</span>
              <el-button link type="primary" :loading="dataLoading" @click="loadDataStatus">刷新</el-button>
            </div>
          </template>

          <el-descriptions v-loading="dataLoading" :column="1" border size="small">
            <el-descriptions-item label="标的数量">
              {{ dataStatus.symbol_count || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="K线总数">
              {{ dataStatus.bar_count || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="最新交易日">
              {{ dataStatus.latest_trade_date || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="质量冲突数">
              <el-tag v-if="qualitySummary.conflicts > 0" type="warning" size="small">
                {{ qualitySummary.conflicts }}
              </el-tag>
              <span v-else>0</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24">
        <el-card shadow="never" class="rb-card health-overview-card">
          <template #header>
            <div class="rb-page-header">
              <span>策略健康度概览</span>
              <el-button link type="primary" :loading="healthLoading" @click="loadHealthOverview">刷新</el-button>
            </div>
          </template>

          <el-table
            v-loading="healthLoading"
            :data="healthOverview"
            stripe
            max-height="400"
          >
            <el-table-column prop="strategy_name" label="策略名称" min-width="180" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="health_score" label="健康度" width="100">
              <template #default="{ row }">
                <strong>{{ row.health_score != null ? row.health_score.toFixed(1) : '—' }}</strong>
              </template>
            </el-table-column>
            <el-table-column prop="confidence_level" label="置信度" width="100">
              <template #default="{ row }">
                <el-tag :type="getConfidenceType(row.confidence_level)" size="small">
                  {{ getConfidenceLabel(row.confidence_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="recent_signals_count" label="信号数" width="90" />
            <el-table-column prop="recent_matured_signals_count" label="成熟信号" width="100" />
            <el-table-column prop="recent_win_rate" label="胜率" width="100">
              <template #default="{ row }">{{ formatPercent(row.recent_win_rate) }}</template>
            </el-table-column>
            <el-table-column prop="recent_avg_return" label="平均收益" width="110">
              <template #default="{ row }">{{ formatPercent(row.recent_avg_return) }}</template>
            </el-table-column>
            <el-table-column label="数据质量" width="100">
              <template #default="{ row }">
                <el-tag
                  v-if="row.data_quality?.quality_grade"
                  :type="getQualityType(row.data_quality.quality_grade)"
                  size="small"
                >
                  {{ row.data_quality.quality_grade }}
                </el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="last_check" label="最近检查" width="160">
              <template #default="{ row }">{{ formatTime(row.last_check) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import StrategyCycleStatus from '@/components/StrategyCycleStatus.vue'

const cycleStatusRef = ref(null)
const statsLoading = ref(false)
const dataLoading = ref(false)
const healthLoading = ref(false)

const stats = ref({
  total_strategies: 0,
  active_strategies: 0,
  healthy_strategies: 0,
  degraded_strategies: 0,
  status_breakdown: {}
})

const dataStatus = ref({})
const qualitySummary = ref({ conflicts: 0 })
const healthOverview = ref([])

const statusBreakdown = computed(() => {
  const breakdown = stats.value.status_breakdown || {}
  const labels = {
    idea: '想法',
    generated: '已生成',
    backtested: '已回测',
    validated: '已验证',
    active: '启用中',
    watch: '观察中',
    degraded: '已衰减',
    retired: '已废弃'
  }
  const types = {
    active: 'success',
    validated: 'success',
    watch: 'warning',
    degraded: 'warning',
    retired: 'info'
  }

  return Object.entries(breakdown)
    .filter(([_, count]) => count > 0)
    .map(([status, count]) => ({
      status,
      label: labels[status] || status,
      type: types[status] || '',
      count
    }))
})

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await axios.get('/api/v1/strategy-library/stats')
    stats.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载策略统计失败')
  } finally {
    statsLoading.value = false
  }
}

async function loadDataStatus() {
  dataLoading.value = true
  try {
    const [statusRes, coverageRes, qualityRes] = await Promise.all([
      axios.get('/api/v1/data/status'),
      axios.get('/api/v1/data/coverage'),
      axios.get('/api/v1/quality/summary')
    ])
    dataStatus.value = { ...statusRes.data, ...(coverageRes.data || {}) }
    qualitySummary.value = qualityRes.data || { conflicts: 0 }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载数据状态失败')
  } finally {
    dataLoading.value = false
  }
}

async function loadHealthOverview() {
  healthLoading.value = true
  try {
    const res = await axios.get('/api/v1/strategy-monitor/strategies')
    healthOverview.value = res.data.strategies || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载健康度概览失败')
  } finally {
    healthLoading.value = false
  }
}

function getStatusLabel(status) {
  const map = { healthy: '健康', degraded: '衰减', failing: '失效' }
  return map[status] || status || '—'
}

function getStatusType(status) {
  const map = { healthy: 'success', degraded: 'warning', failing: 'danger' }
  return map[status] || 'info'
}

function getConfidenceLabel(level) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[level] || level || '—'
}

function getConfidenceType(level) {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[level] || 'info'
}

function getQualityType(grade) {
  const map = { A: 'success', B: '', C: 'warning', D: 'danger' }
  return map[grade] || 'info'
}

function formatPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

onMounted(() => {
  loadStats()
  loadDataStatus()
  loadHealthOverview()
})
</script>

<style scoped>
.system-status-page {
  padding: 20px;
}

.stats-card,
.data-card,
.health-overview-card {
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-tile {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  text-align: center;
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.stat-value.stat-active {
  color: var(--el-color-success);
}

.stat-value.stat-healthy {
  color: var(--el-color-primary);
}

.stat-value.stat-degraded {
  color: var(--el-color-warning);
}

.status-breakdown {
  margin-top: 12px;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 10px;
}

.breakdown-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.breakdown-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.breakdown-count {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
