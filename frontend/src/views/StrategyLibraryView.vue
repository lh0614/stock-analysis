<template>
  <div class="rb-page strategy-library-page">
    <h1 class="rb-page-title">策略库</h1>
    <p class="rb-page-desc">管理和监控已保存的策略，查看回测表现和生命周期状态</p>

    <el-card shadow="never" class="rb-card">
      <template #header>
        <div class="rb-page-header">
          <span>策略列表</span>
          <div class="toolbar-actions">
            <el-button size="small" type="primary" :loading="fullCycleLoading" @click="runFullCycle">
              执行完整监控闭环
            </el-button>
            <el-select v-model="filterStatus" placeholder="筛选状态" style="width: 150px" @change="loadStrategies">
              <el-option label="全部" value="" />
              <el-option label="想法" value="idea" />
              <el-option label="已生成" value="generated" />
              <el-option label="已回测" value="backtested" />
              <el-option label="已验证" value="validated" />
              <el-option label="启用中" value="active" />
              <el-option label="观察中" value="watch" />
              <el-option label="已衰减" value="degraded" />
              <el-option label="已废弃" value="retired" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="strategies" v-loading="loading" stripe>
        <el-table-column prop="name" label="策略名称" min-width="200" />
        <el-table-column prop="source" label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getSourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rating" label="评级" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.rating" :type="getRatingType(row.rating)" size="small">
              {{ row.rating }}
            </el-tag>
            <span v-else class="text-secondary">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="viewDetail(row.id)">详情</el-button>
            <el-button size="small" link type="success" @click="viewHealth(row.id)">健康度</el-button>
            <el-button size="small" link type="primary" @click="optimizeStrategy(row.id)">优化</el-button>
            <el-button
              v-if="row.status !== 'active'"
              size="small"
              type="primary"
              link
              @click="activateStrategy(row.id)"
            >
              启用
            </el-button>
            <el-button
              v-if="row.status === 'active'"
              size="small"
              type="warning"
              link
              @click="pauseStrategy(row.id)"
            >
              暂停
            </el-button>
            <el-button
              v-if="row.status !== 'retired'"
              size="small"
              type="danger"
              link
              @click="retireStrategy(row.id)"
            >
              废弃
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 策略详情对话框 -->
    <el-dialog v-model="detailVisible" title="策略详情" width="800px">
      <div v-if="currentStrategy" class="strategy-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="策略名称">{{ currentStrategy.name }}</el-descriptions-item>
          <el-descriptions-item label="评级">
            <el-tag v-if="currentStrategy.rating" :type="getRatingType(currentStrategy.rating)">
              {{ currentStrategy.rating }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="来源">{{ getSourceLabel(currentStrategy.source) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentStrategy.status)">
              {{ getStatusLabel(currentStrategy.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">
            {{ formatDate(currentStrategy.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="用户意图" :span="2">
            {{ currentStrategy.intent_text || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">策略配置</el-divider>

        <div v-if="currentStrategy.spec" class="spec-detail">
          <div class="spec-item">
            <span class="spec-label">投资周期:</span>
            <el-tag size="small">{{ getHorizonLabel(currentStrategy.spec.horizon) }}</el-tag>
          </div>

          <div class="spec-item">
            <span class="spec-label">股票池:</span>
            <span>{{ currentStrategy.spec.universe?.boards?.join(', ') || '-' }}</span>
            <el-tag v-if="currentStrategy.spec.universe?.exclude_st" size="small" type="warning">排除ST</el-tag>
          </div>

          <div v-if="currentStrategy.spec.entry_conditions?.length" class="spec-item">
            <span class="spec-label">入场条件:</span>
            <div class="conditions-list">
              <el-tag
                v-for="(cond, idx) in currentStrategy.spec.entry_conditions"
                :key="idx"
                size="small"
                style="margin-right: 8px; margin-bottom: 4px"
              >
                {{ cond.factor }} {{ cond.op }} {{ cond.value }}
              </el-tag>
            </div>
          </div>

          <div v-if="currentStrategy.spec.ranking?.length" class="spec-item">
            <span class="spec-label">排序规则:</span>
            <div class="conditions-list">
              <el-tag
                v-for="(rank, idx) in currentStrategy.spec.ranking"
                :key="idx"
                size="small"
                type="info"
                style="margin-right: 8px; margin-bottom: 4px"
              >
                {{ rank.factor }} {{ rank.direction === 'desc' ? '↓' : '↑' }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="healthVisible" title="策略健康与信号" width="980px">
      <div v-loading="healthLoading" class="health-panel">
        <template v-if="currentHealth">
          <div class="health-toolbar">
            <div>
              <div class="health-title">{{ currentHealth.strategy_name }}</div>
              <div class="health-subtitle">最近一次检查：{{ formatDate(currentHealth.last_check) }}</div>
            </div>
            <div>
              <el-button
                v-if="currentHealth.status !== 'healthy'"
                type="warning"
                :loading="autoOptimizeLoading"
                @click="runAutoOptimizeForCurrent"
              >
                一键生成优化候选
              </el-button>
              <el-button type="primary" :loading="runSignalLoading" @click="runSignalsForCurrent">
                运行并保存信号
              </el-button>
            </div>
          </div>

          <div class="metric-grid">
            <div class="metric-tile">
              <span class="metric-label">健康度</span>
              <strong>{{ currentHealth.health_score.toFixed(1) }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-label">状态</span>
              <el-tag :type="getHealthStatusType(currentHealth.status)">
                {{ getHealthStatusLabel(currentHealth.status) }}
              </el-tag>
            </div>
            <div class="metric-tile">
              <span class="metric-label">信号数</span>
              <strong>{{ currentHealth.recent_signals_count }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-label">胜率</span>
              <strong>{{ formatPercent(currentHealth.recent_win_rate) }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-label">平均收益</span>
              <strong>{{ formatPercent(currentHealth.recent_avg_return) }}</strong>
            </div>
          </div>

          <!-- 健康度历史趋势 -->
          <div class="health-section">
            <div class="section-title">健康度历史趋势</div>
            <div v-if="healthHistory.length" ref="trendChartRef" style="height: 220px; width: 100%;"></div>
            <div v-else class="empty-trend">暂无健康度历史数据（可多次执行“运行并保存信号”或触发每日健康检查来生成记录）</div>
          </div>

          <div class="health-section" v-if="currentHealth.degradation_signals?.length">
            <div class="section-title">衰减信号</div>
            <el-alert
              v-for="signal in currentHealth.degradation_signals"
              :key="signal"
              :title="signal"
              type="warning"
              :closable="false"
              show-icon
            />
          </div>

          <div class="health-section" v-if="currentHealth.recommendations?.length">
            <div class="section-title">建议</div>
            <div class="recommendation-list">
              <el-tag
                v-for="item in currentHealth.recommendations"
                :key="item"
                type="info"
                effect="plain"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>

          <!-- 自进化优化任务历史 -->
          <div class="health-section">
            <div class="section-title">自进化优化记录</div>
            <el-table :data="optimizationJobs" v-loading="jobsLoading" stripe max-height="240">
              <el-table-column prop="created_at" label="优化时间" width="160">
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
              <el-table-column prop="from_version" label="版本变更" width="130">
                <template #default="{ row }">
                  <el-tag size="small" type="info">{{ row.from_version }}</el-tag>
                  <span style="margin: 0 4px">→</span>
                  <el-tag size="small" type="success">{{ row.to_version }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="objective" label="优化目标" width="90" />
              <el-table-column label="指标改善情况" min-width="260">
                <template #default="{ row }">
                  <div style="font-size: 11px">
                    <span style="margin-right: 12px">
                      夏普比率: {{ row.metrics_before?.out_sample_sharpe?.toFixed(2) || '0.00' }}
                      → <strong>{{ row.metrics_after?.out_sample_sharpe?.toFixed(2) || '0.00' }}</strong>
                    </span>
                    <span>
                      年化收益: {{ formatPercent(row.metrics_before?.out_sample_annual_return) }}
                      → <strong style="color: #e54545">{{ formatPercent(row.metrics_after?.out_sample_annual_return) }}</strong>
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="参数变化" min-width="220">
                <template #default="{ row }">
                  <div class="change-list">
                    <el-tag
                      v-for="change in (row.changes || []).slice(0, 3)"
                      :key="`${row.optimization_id}-${change.param_path}`"
                      size="small"
                      effect="plain"
                    >
                      {{ change.param_name }}: {{ change.from_value }} -> {{ change.to_value }}
                    </el-tag>
                    <span v-if="!row.changes?.length" class="text-secondary">-</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="getJobStatusType(row.status)">
                    {{ getJobStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row }">
                  <template v-if="row.status === 'pending'">
                    <el-button size="small" link type="success" @click="promoteJob(row.optimization_id)">晋级</el-button>
                    <el-button size="small" link type="danger" @click="rejectJob(row.optimization_id)">拒绝</el-button>
                  </template>
                  <span v-else class="text-secondary" style="font-size: 12px">-</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="health-section">
            <div class="section-title">策略版本</div>
            <el-table :data="strategyVersions" v-loading="versionsLoading" stripe max-height="220">
              <el-table-column prop="created_at" label="生成时间" width="160">
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
              <el-table-column prop="version" label="版本" width="100" />
              <el-table-column prop="generated_by" label="来源" width="110" />
              <el-table-column prop="change_note" label="说明" min-width="220" />
              <el-table-column label="关键差异" min-width="260">
                <template #default="{ row }">
                  <div class="change-list">
                    <el-tag
                      v-for="diff in getVersionDiff(row).slice(0, 4)"
                      :key="`${row.id}-${diff}`"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      {{ diff }}
                    </el-tag>
                    <span v-if="!getVersionDiff(row).length" class="text-secondary">-</span>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="health-section">
            <div class="section-title">近期信号</div>
            <el-table :data="strategySignals" v-loading="signalsLoading" stripe max-height="360">
              <el-table-column prop="signal_date" label="信号日" width="110" />
              <el-table-column prop="symbol" label="代码" width="100" />
              <el-table-column prop="name" label="名称" min-width="120" />
              <el-table-column prop="rank" label="排名" width="80" />
              <el-table-column prop="score" label="评分" width="90">
                <template #default="{ row }">
                  {{ row.score != null ? row.score.toFixed(1) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="quality_level" label="质量" width="80" />
              <el-table-column prop="forward_return_5d" label="5日收益" width="100">
                <template #default="{ row }">{{ formatPercent(row.forward_return_5d) }}</template>
              </el-table-column>
              <el-table-column prop="forward_return_20d" label="20日收益" width="110">
                <template #default="{ row }">{{ formatPercent(row.forward_return_20d) }}</template>
              </el-table-column>
              <el-table-column label="条件" min-width="180">
                <template #default="{ row }">
                  <el-tag
                    v-for="cond in row.matched_conditions?.slice(0, 3)"
                    :key="`${row.id}-${cond.factor}`"
                    size="small"
                    class="condition-chip"
                  >
                    {{ cond.factor }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

const loading = ref(false)
const strategies = ref([])
const filterStatus = ref('')
const detailVisible = ref(false)
const currentStrategy = ref(null)
const healthVisible = ref(false)
const healthLoading = ref(false)
const signalsLoading = ref(false)
const runSignalLoading = ref(false)
const currentHealth = ref(null)
const currentHealthStrategyId = ref('')
const strategySignals = ref([])

const healthHistory = ref([])
const trendChartRef = ref(null)
let trendChartInstance = null

const optimizationJobs = ref([])
const jobsLoading = ref(false)
const autoOptimizeLoading = ref(false)
const strategyVersions = ref([])
const versionsLoading = ref(false)
const fullCycleLoading = ref(false)

onMounted(() => {
  loadStrategies()
})

async function loadStrategies() {
  loading.value = true
  try {
    const params = filterStatus.value ? { status: filterStatus.value } : {}
    const res = await axios.get('/api/v1/strategy-library', { params })
    strategies.value = res.data.strategies
  } catch (error) {
    ElMessage.error('加载策略列表失败')
  } finally {
    loading.value = false
  }
}

async function viewDetail(strategyId) {
  try {
    const res = await axios.get(`/api/v1/strategy-library/${strategyId}`)
    currentStrategy.value = res.data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('加载策略详情失败')
  }
}

async function activateStrategy(strategyId) {
  try {
    await ElMessageBox.confirm('确认启用该策略？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await axios.post(`/api/v1/strategy-library/${strategyId}/activate`)
    ElMessage.success('策略已启用')
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('启用失败')
    }
  }
}

async function pauseStrategy(strategyId) {
  try {
    await ElMessageBox.confirm('确认暂停该策略？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await axios.post(`/api/v1/strategy-library/${strategyId}/pause`)
    ElMessage.success('策略已暂停')
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('暂停失败')
    }
  }
}

async function retireStrategy(strategyId) {
  try {
    await ElMessageBox.confirm('确认废弃该策略？此操作不可恢复。', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'error'
    })

    await axios.post(`/api/v1/strategy-library/${strategyId}/retire`)
    ElMessage.success('策略已废弃')
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('废弃失败')
    }
  }
}

async function viewHealth(strategyId) {
  currentHealthStrategyId.value = strategyId
  healthVisible.value = true
  healthLoading.value = true
  try {
    const detailRes = await axios.get(`/api/v1/strategy-library/${strategyId}`)
    currentStrategy.value = detailRes.data
    const res = await axios.get(`/api/v1/strategy-monitor/strategies/${strategyId}`)
    currentHealth.value = res.data
    await loadStrategySignals(strategyId)
    await loadHealthHistory(strategyId)
    await loadOptimizationJobs(strategyId)
    await loadStrategyVersions(strategyId)
  } catch (error) {
    ElMessage.error('获取健康度失败')
  } finally {
    healthLoading.value = false
  }
}

async function runFullCycle() {
  fullCycleLoading.value = true
  try {
    const res = await axios.post('/api/v1/strategy-monitor/run-full-cycle', null, {
      params: { auto_optimize: true }
    })
    ElMessage.success(`闭环完成：${res.data.total_strategies} 个策略，触发优化 ${res.data.optimization_triggered_count} 个`)
    await loadStrategies()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '执行完整监控闭环失败')
  } finally {
    fullCycleLoading.value = false
  }
}

async function loadOptimizationJobs(strategyId) {
  jobsLoading.value = true
  try {
    const res = await axios.get('/api/v1/strategy-optimizer/jobs', {
      params: { strategy_id: strategyId }
    })
    optimizationJobs.value = res.data.jobs || []
  } catch (error) {
    ElMessage.error('加载优化历史失败')
  } finally {
    jobsLoading.value = false
  }
}

async function loadStrategyVersions(strategyId) {
  versionsLoading.value = true
  try {
    const res = await axios.get(`/api/v1/strategy-library/${strategyId}/versions`)
    strategyVersions.value = res.data.versions || []
  } catch (error) {
    ElMessage.error('加载策略版本失败')
  } finally {
    versionsLoading.value = false
  }
}

async function promoteJob(jobId) {
  try {
    await ElMessageBox.confirm('确认晋级此优化版本为活跃版本？这会更新策略配置！', '提示', {
      confirmButtonText: '确定晋级',
      cancelButtonText: '取消',
      type: 'success'
    })
    await axios.post(`/api/v1/strategy-optimizer/${jobId}/promote`)
    ElMessage.success('优化版本晋级成功！')
    await loadOptimizationJobs(currentHealthStrategyId.value)
    await loadStrategyVersions(currentHealthStrategyId.value)
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '晋级失败')
    }
  }
}

async function rejectJob(jobId) {
  try {
    await ElMessageBox.confirm('确认拒绝并归档此优化版本？', '提示', {
      confirmButtonText: '确定拒绝',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await axios.post(`/api/v1/strategy-optimizer/${jobId}/reject`)
    ElMessage.success('已拒绝优化版本')
    await loadOptimizationJobs(currentHealthStrategyId.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  }
}

function getJobStatusLabel(status) {
  const map = { pending: '待处理', promoted: '已晋级', rejected: '已拒绝' }
  return map[status] || status
}

function getJobStatusType(status) {
  const map = { pending: 'warning', promoted: 'success', rejected: 'info' }
  return map[status] || ''
}

async function loadHealthHistory(strategyId) {
  try {
    const res = await axios.get(`/api/v1/strategy-monitor/strategies/${strategyId}/history`, {
      params: { days: 30 }
    })
    healthHistory.value = res.data.history || []
    nextTick(() => {
      renderTrendChart()
    })
  } catch (error) {
    ElMessage.error('加载健康度历史失败')
  }
}

function renderTrendChart() {
  if (!trendChartRef.value || !healthHistory.value.length) return
  if (trendChartInstance) {
    trendChartInstance.dispose()
  }
  trendChartInstance = echarts.init(trendChartRef.value)
  const dates = healthHistory.value.map(item => formatDate(item.created_at).split(' ')[0])
  const scores = healthHistory.value.map(item => item.health_score)
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}: {c}分'
    },
    grid: {
      left: '4%',
      right: '4%',
      top: '10%',
      bottom: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLabel: { fontSize: 10, color: '#9ca3af' },
      axisLine: { lineStyle: { color: '#e5e7eb' } }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { fontSize: 10, color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#f3f4f6' } }
    },
    series: [
      {
        data: scores,
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { color: '#3b82f6', width: 3 },
        itemStyle: { color: '#3b82f6' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ])
        }
      }
    ]
  }
  trendChartInstance.setOption(option)
}

watch(healthVisible, (val) => {
  if (!val && trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }
})

onUnmounted(() => {
  if (trendChartInstance) {
    trendChartInstance.dispose()
  }
})

async function loadStrategySignals(strategyId) {
  signalsLoading.value = true
  try {
    const res = await axios.get(`/api/v1/strategy-monitor/strategies/${strategyId}/signals`, {
      params: { days: 60 }
    })
    strategySignals.value = res.data.signals || []
  } catch (error) {
    ElMessage.error('加载策略信号失败')
  } finally {
    signalsLoading.value = false
  }
}

async function runSignalsForCurrent() {
  if (!currentHealthStrategyId.value) return
  runSignalLoading.value = true
  try {
    const res = await axios.post(`/api/v1/strategy-monitor/strategies/${currentHealthStrategyId.value}/run-signals`)
    currentHealth.value = res.data.health
    await loadStrategySignals(currentHealthStrategyId.value)
    await loadHealthHistory(currentHealthStrategyId.value)
    ElMessage.success(`已保存 ${res.data.run.saved_signals} 条新信号`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '运行策略信号失败')
  } finally {
    runSignalLoading.value = false
  }
}

async function runAutoOptimizeForCurrent() {
  if (!currentHealthStrategyId.value) return
  try {
    await ElMessageBox.confirm('策略健康度出现衰减，是否立即触发参数优化以寻找最优配置？', '触发自进化优化', {
      confirmButtonText: '确定触发',
      cancelButtonText: '取消',
      type: 'warning'
    })

    autoOptimizeLoading.value = true
    ElMessage.info('正在执行策略寻优，此过程可能需要几分钟，请耐心等待...')

    const res = await axios.post(`/api/v1/strategy-monitor/strategies/${currentHealthStrategyId.value}/optimize-if-needed`)

    if (res.data.status === 'skipped') {
      ElMessageBox.alert(res.data.reason, '无需优化或已跳过', { confirmButtonText: '确定' })
    } else {
      ElMessage.success(`自动寻优任务触发成功！已生成高版本策略候选：v${res.data.to_version}`)
      await loadOptimizationJobs(currentHealthStrategyId.value)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '一键触发自进化失败')
    }
  } finally {
    autoOptimizeLoading.value = false
  }
}

async function optimizeStrategy(strategyId) {
  try {
    await ElMessageBox.confirm('开始优化该策略？这可能需要几分钟时间。', '提示', {
      confirmButtonText: '开始优化',
      cancelButtonText: '取消',
      type: 'info'
    })

    ElMessage.info('正在优化策略，请稍候...')

    const res = await axios.post('/api/v1/strategy-optimizer/optimize', {
      strategy_id: strategyId,
      objective: 'sharpe',
      search_method: 'grid',
      max_trials: 30
    })

    const result = res.data.result
    const decisionMap = { promoted: '晋级', candidate: '候选', rejected: '拒绝' }

    let message = `<div style="text-align: left;">
      <p><strong>优化决策:</strong> ${decisionMap[result.decision]}</p>
      <p><strong>原因:</strong> ${result.decision_reason}</p>
      <p><strong>尝试次数:</strong> ${result.trials_count}</p>
    `

    if (result.changes.length > 0) {
      message += `<p><strong>参数变更:</strong></p><ul style="margin: 5px 0; padding-left: 20px;">`
      result.changes.forEach(change => {
        message += `<li>${change.param_name}: ${change.from_value} → ${change.to_value}</li>`
      })
      message += `</ul>`
    }

    if (result.improvement) {
      message += `<p><strong>改进情况:</strong></p><ul style="margin: 5px 0; padding-left: 20px;">`
      for (const [key, val] of Object.entries(result.improvement)) {
        message += `<li>${key}: ${val > 0 ? '+' : ''}${(val * 100).toFixed(2)}%</li>`
      }
      message += `</ul>`
    }

    message += `</div>`

    ElMessageBox.alert(message, '优化结果', {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '关闭'
    })

    if (result.decision === 'promoted') {
      await maybePromoteOptimization(res.data.job_id, result)
      loadStrategies()
    } else if (result.decision === 'candidate') {
      await maybePromoteOptimization(res.data.job_id, result)
      loadStrategies()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '优化失败')
    }
  }
}

async function maybePromoteOptimization(jobId, result) {
  if (!jobId || !['promoted', 'candidate'].includes(result.decision)) return
  try {
    await ElMessageBox.confirm('是否将该优化候选版本晋级为当前策略版本？', '候选版本晋级', {
      confirmButtonText: '晋级',
      cancelButtonText: '暂不晋级',
      type: 'success'
    })
    await axios.post(`/api/v1/strategy-optimizer/${jobId}/promote`)
    ElMessage.success('候选版本已晋级')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '晋级失败')
    }
  }
}

function getSourceLabel(source) {
  const map = {
    generated: '系统生成',
    manual: '手动创建',
    uploaded: '上传',
    optimized: '优化生成'
  }
  return map[source] || source
}

function getStatusLabel(status) {
  const map = {
    idea: '想法',
    generated: '已生成',
    backtested: '已回测',
    validated: '已验证',
    active: '启用中',
    watch: '观察中',
    degraded: '已衰减',
    retired: '已废弃'
  }
  return map[status] || status
}

function getStatusType(status) {
  const map = {
    active: 'success',
    validated: 'success',
    backtested: '',
    watch: 'warning',
    degraded: 'warning',
    retired: 'info',
    idea: 'info'
  }
  return map[status] || ''
}

function getRatingType(rating) {
  const map = {
    A: 'success',
    B: '',
    C: 'warning',
    D: 'danger'
  }
  return map[rating] || ''
}

function getHorizonLabel(horizon) {
  const map = {
    short: '短线',
    medium: '中线',
    long: '长线'
  }
  return map[horizon] || horizon
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatPercent(value) {
  if (value === null || value === undefined) return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function getHealthStatusLabel(status) {
  const map = { healthy: '健康', degraded: '衰减', failing: '失效' }
  return map[status] || status
}

function getHealthStatusType(status) {
  const map = { healthy: 'success', degraded: 'warning', failing: 'danger' }
  return map[status] || 'info'
}

function getVersionDiff(versionRow) {
  const current = currentStrategy.value?.spec || {}
  const candidate = versionRow?.spec || {}
  const diffs = []
  if (!current.version || current.version !== candidate.version) {
    diffs.push(`版本 ${current.version || '-'} -> ${candidate.version || '-'}`)
  }
  if (current.rebalance !== candidate.rebalance) {
    diffs.push(`调仓 ${current.rebalance || '-'} -> ${candidate.rebalance || '-'}`)
  }
  if (current.position?.max_positions !== candidate.position?.max_positions) {
    diffs.push(`持仓数 ${current.position?.max_positions || '-'} -> ${candidate.position?.max_positions || '-'}`)
  }
  const currentConditions = current.entry_conditions || []
  const candidateConditions = candidate.entry_conditions || []
  candidateConditions.forEach((cond, idx) => {
    const old = currentConditions[idx]
    if (old && old.value !== cond.value) {
      diffs.push(`${cond.factor} ${old.value} -> ${cond.value}`)
    }
  })
  return diffs
}
</script>

<style scoped>
.strategy-library-page {
  padding: 20px;
}

.strategy-detail {
  padding: 10px 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.spec-detail {
  margin-top: 16px;
}

.spec-item {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.spec-label {
  font-weight: 500;
  min-width: 80px;
  color: var(--el-text-color-regular);
}

.conditions-list {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
}

.text-secondary {
  color: var(--el-text-color-secondary);
}

.health-panel {
  min-height: 220px;
}

.health-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.health-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.health-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
}

.metric-tile {
  min-height: 76px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: var(--el-fill-color-lighter);
}

.metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.metric-tile strong {
  font-size: 20px;
  line-height: 1.2;
}

.health-section {
  margin-top: 18px;
}

.health-section .el-alert + .el-alert {
  margin-top: 8px;
}

.section-title {
  margin-bottom: 10px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.recommendation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.change-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.condition-chip {
  margin-right: 6px;
  margin-bottom: 4px;
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }

  .health-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}

.empty-trend {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  background-color: var(--el-fill-color-blank);
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
}
</style>
