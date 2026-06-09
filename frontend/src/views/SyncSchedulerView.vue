<template>
  <div class="rb-page sync-scheduler-page">
    <h1 class="rb-page-title">数据同步</h1>
    <p class="rb-page-desc">定时同步股票列表与 K 线，支持手动立即触发</p>

    <BackendState
      v-if="statusLoadError"
      type="error"
      title="无法加载同步状态"
      :description="statusLoadErrorMessage"
      :retrying="loading"
      @retry="refreshStatus"
    />

    <el-row :gutter="16">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="rb-card" v-loading="loading">
          <template #header>
            <span class="rb-page-header__title">定时配置</span>
          </template>
          <el-form class="rb-form" label-width="120px">
            <el-form-item label="启用定时同步">
              <el-switch v-model="form.enabled" active-text="开" inactive-text="关" />
            </el-form-item>
            <el-form-item label="每日同步时间">
              <el-time-picker
                v-model="timeValue"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="同步模式">
              <el-select v-model="form.sync_mode" style="width: 100%">
                <el-option label="增量（推荐）" value="incremental" />
                <el-option label="全量（含断点续传）" value="full" />
              </el-select>
              <p class="rb-hint">增量仅补已有全量文件的落后日 K；全量含列表与断点续传</p>
            </el-form-item>
            <el-form-item label="同步范围">
              <el-select v-model="scope" style="width: 100%">
                <el-option label="全市场" value="all" />
                <el-option label="自选股" value="watchlist" />
                <el-option label="自定义池" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
              <el-button
                type="success"
                :loading="runningNow"
                :disabled="status.running"
                @click="runNow"
              >
                立即同步
              </el-button>
              <el-button :loading="runningNow" @click="runDataSync">按范围同步</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="rb-card" v-loading="loading">
          <template #header>
            <div class="rb-page-header">
              <span>同步状态</span>
              <el-button link type="primary" :loading="loading" @click="refreshStatus">刷新</el-button>
            </div>
          </template>

          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="当前状态">
              <el-tag v-if="status.running" type="warning">运行中</el-tag>
              <el-tag v-else-if="status.last_status === 'success'" type="success">成功</el-tag>
              <el-tag v-else-if="status.last_status === 'failed'" type="danger">失败</el-tag>
              <el-tag v-else-if="status.last_status === 'skipped'" type="info">跳过</el-tag>
              <span v-else class="muted">空闲</span>
            </el-descriptions-item>
            <el-descriptions-item label="定时同步">
              {{ status.enabled ? '已启用' : '未启用' }}
            </el-descriptions-item>
            <el-descriptions-item label="每日时间">
              {{ status.time_of_day || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="同步模式">
              {{ syncModeLabel(status.sync_mode) }}
            </el-descriptions-item>
            <el-descriptions-item label="下次执行">
              {{ formatTime(status.next_run_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近开始">
              {{ formatTime(status.last_started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近结束">
              {{ formatTime(status.last_finished_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近触发">
              {{ triggerLabel(status.last_trigger) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近结果">
              {{ status.last_message || '—' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="status.last_error" label="最近错误">
              <span class="error-text">{{ status.last_error }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="status.running && status.progress" class="progress-panel">
            <p class="progress-phase">
              当前阶段：<strong>{{ phaseLabel(status.progress.phase) }}</strong>
            </p>
            <p v-if="progressMessage" class="progress-msg">{{ progressMessage }}</p>
            <p v-if="status.progress.symbol" class="progress-symbol">
              正在处理：{{ status.progress.symbol }}
            </p>
            <el-progress
              v-if="showProgressBar"
              :percentage="progressPercent"
              :format="progressBarFormat"
              style="margin-top: 8px"
            />
          </div>

          <el-divider />
          <p class="muted">raw/curated/quality 三段进度</p>
          <el-steps :active="Object.values(stageProgress).filter(v => v==='success').length" finish-status="success" align-center>
            <el-step title="raw" :status="getStepStatus(stageProgress.raw)" />
            <el-step title="klines" :status="getStepStatus(stageProgress.klines)" />
            <el-step title="curated" :status="getStepStatus(stageProgress.curated)" />
            <el-step title="quality" :status="getStepStatus(stageProgress.quality)" />
          </el-steps>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="数据仓标的数">{{ dataStatus.symbol_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="K线总条数">{{ dataStatus.bar_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="最新交易日">{{ dataStatus.latest_trade_date || '—' }}</el-descriptions-item>
            <el-descriptions-item label="质量冲突数">{{ qualitySummary.conflicts || 0 }}</el-descriptions-item>
          </el-descriptions>

          <el-divider />
          <div class="rb-page-header cycle-header">
            <span>策略自进化闭环</span>
            <div>
              <el-button link type="primary" :loading="cycleLoading" @click="loadCycleStatus()">刷新</el-button>
              <el-button
                size="small"
                type="primary"
                :loading="cycleTriggering"
                :disabled="cycleStatus.is_running"
                @click="triggerStrategyCycle"
              >
                手动执行闭环
              </el-button>
            </div>
          </div>

          <el-descriptions :column="2" border size="small" class="cycle-summary">
            <el-descriptions-item label="当前状态">
              <el-tag v-if="cycleStatus.is_running" type="warning">运行中</el-tag>
              <el-tag
                v-else-if="cycleStatus.latest_run?.status"
                :type="cycleStatusType(cycleStatus.latest_run.status)"
              >
                {{ cycleStatusLabel(cycleStatus.latest_run.status) }}
              </el-tag>
              <span v-else class="muted">暂无记录</span>
            </el-descriptions-item>
            <el-descriptions-item label="最近触发">
              {{ cycleTriggerLabel(cycleStatus.latest_run?.trigger_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近开始">
              {{ formatTime(cycleStatus.latest_run?.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近结束">
              {{ formatTime(cycleStatus.latest_run?.finished_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="策略数">
              {{ cycleStatus.latest_run?.total_strategies || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="优化任务">
              {{ cycleStatus.latest_run?.optimization_jobs || 0 }}
            </el-descriptions-item>
            <el-descriptions-item v-if="cycleStatus.latest_run?.error" label="最近错误" :span="2">
              <span class="error-text">{{ cycleStatus.latest_run.error }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="cycleStatus.is_running && cycleStatus.progress" class="progress-panel">
            <p class="progress-phase">
              当前阶段：<strong>{{ strategyCyclePhaseLabel(cycleStatus.progress.phase) }}</strong>
            </p>
            <p v-if="cycleStatus.progress.message" class="progress-msg">{{ cycleStatus.progress.message }}</p>
            <p v-if="cycleStatus.progress.sub_phase" class="progress-symbol">
              子阶段：{{ cycleStatus.progress.sub_phase }}
            </p>
            <el-progress
              v-if="cycleProgressPercent != null"
              :percentage="cycleProgressPercent"
              :format="cycleProgressBarFormat"
              style="margin-top: 8px"
            />
          </div>

          <el-table
            v-if="cycleHistory.length"
            :data="cycleHistory"
            size="small"
            stripe
            max-height="180"
            class="cycle-history"
          >
            <el-table-column prop="started_at" label="开始时间" width="150">
              <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column prop="trigger_type" label="触发" width="80">
              <template #default="{ row }">{{ cycleTriggerLabel(row.trigger_type) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="cycleStatusType(row.status)">
                  {{ cycleStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total_strategies" label="策略" width="70" />
            <el-table-column prop="signal_runs" label="信号" width="70" />
            <el-table-column prop="health_checks" label="健康" width="70" />
            <el-table-column prop="optimization_jobs" label="优化" width="70" />
          </el-table>

          <el-alert
            title="选股器页面的手动同步按钮仍然可用；本页用于定时任务与统一状态查看。"
            type="info"
            show-icon
            :closable="false"
            class="hint-alert"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import syncSchedulerApi from '@/api/syncScheduler.js'
import dataApi from '@/api/data.js'
import qualityApi from '@/api/quality.js'
import BackendState from '@/components/common/BackendState.vue'

const loading = ref(false)
const statusLoadError = ref(false)
const statusLoadErrorMessage = ref('')
const saving = ref(false)
const runningNow = ref(false)
const pollTimer = ref(null)
const scope = ref('all')
const dataStatus = ref({})
const qualitySummary = ref({})
const stageProgress = ref({ raw: "wait", klines: "wait", curated: "wait", quality: "wait", factors: "wait" })
const cycleStatus = ref({ is_running: false, progress: null, latest_run: null })
const cycleHistory = ref([])
const cycleLoading = ref(false)
const cycleTriggering = ref(false)

const form = ref({
  enabled: false,
  sync_mode: 'incremental'
})
const timeValue = ref('15:30')

const status = ref({
  enabled: false,
  time_of_day: '15:30',
  sync_mode: 'incremental',
  running: false,
  last_started_at: null,
  last_finished_at: null,
  last_status: null,
  last_message: null,
  last_error: null,
  next_run_at: null,
  last_trigger: null,
  progress: null
})

const PHASE_LABELS = {
  starting: '启动中',
  list: '列表同步',
  klines: 'K 线同步'
}

function phaseLabel(phase) {
  if (!phase) return '—'
  return PHASE_LABELS[phase] || phase
}

const showProgressBar = computed(() => {
  const p = status.value.progress
  if (!p) return false
  const cur = p.current
  const tot = p.total
  return cur != null && tot != null && tot > 0
})

const progressPercent = computed(() => {
  const p = status.value.progress
  if (!showProgressBar.value) return 0
  return Math.min(100, Math.round((p.current / p.total) * 100))
})

function progressBarFormat() {
  const p = status.value.progress
  return `${p.current}/${p.total}`
}

const progressMessage = computed(() => {
  const msg = status.value.progress?.message
  return msg && String(msg) !== 'undefined' ? msg : ''
})

const cycleProgressPercent = computed(() => {
  const p = cycleStatus.value.progress
  if (!p || p.current == null || p.total == null || p.total <= 0) return null
  return Math.min(100, Math.round((p.current / p.total) * 100))
})

function syncModeLabel(mode) {
  if (mode === 'full') return '全量'
  if (mode === 'incremental') return '增量'
  return mode || '—'
}

function triggerLabel(t) {
  if (t === 'scheduled') return '定时'
  if (t === 'manual') return '手动'
  return t || '—'
}

function cycleTriggerLabel(t) {
  if (t === 'scheduled') return '定时'
  if (t === 'manual') return '手动'
  if (t === 'auto') return '同步后'
  return t || '—'
}

function cycleStatusLabel(s) {
  const map = { running: '运行中', completed: '完成', failed: '失败' }
  return map[s] || s || '—'
}

function cycleStatusType(s) {
  const map = { running: 'warning', completed: 'success', failed: 'danger' }
  return map[s] || 'info'
}

function strategyCyclePhaseLabel(phase) {
  const map = { backfill: '回填收益', processing: '策略处理' }
  return map[phase] || phase || '—'
}

function cycleProgressBarFormat() {
  const p = cycleStatus.value.progress
  return p ? `${p.current}/${p.total}` : ''
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

function getStepStatus(stage) {
  if (stage === 'running') return 'process'
  if (stage === 'success') return 'success'
  return 'wait'
}

function applyStatus(data) {
  status.value = { ...status.value, ...data }
  form.value.enabled = !!data.enabled
  form.value.sync_mode = data.sync_mode || 'incremental'
  if (data.time_of_day) {
    timeValue.value = data.time_of_day
  }
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer.value = setInterval(async () => {
    try {
      const data = await syncSchedulerApi.status()
      applyStatus(data)
      await loadCycleStatus(false)
      if (!data.running && !cycleStatus.value.is_running) stopPolling()
    } catch {
      /* ignore poll errors */
    }
  }, 2000)
}

async function loadCycleStatus(showLoading = true) {
  if (showLoading) cycleLoading.value = true
  try {
    const [statusRes, historyRes] = await Promise.all([
      axios.get('/api/v1/strategy-cycle/status'),
      axios.get('/api/v1/strategy-cycle/history', { params: { limit: 8 } })
    ])
    cycleStatus.value = statusRes.data || { is_running: false, progress: null, latest_run: null }
    cycleHistory.value = historyRes.data?.runs || []
  } catch (e) {
    if (showLoading) {
      ElMessage.error(e.response?.data?.detail || e.message || '加载策略闭环状态失败')
    }
  } finally {
    if (showLoading) cycleLoading.value = false
  }
}

async function refreshStatus() {
  loading.value = true
  statusLoadError.value = false
  statusLoadErrorMessage.value = ''
  try {
    const data = await syncSchedulerApi.status()
    applyStatus(data)
    dataStatus.value = await dataApi.status()
    const cv = await dataApi.coverage()
    dataStatus.value = { ...dataStatus.value, ...(cv || {}) }
    qualitySummary.value = await qualityApi.summary()
    await loadCycleStatus(false)
    if (data.running || cycleStatus.value.is_running) startPolling()
  } catch (e) {
    statusLoadError.value = true
    statusLoadErrorMessage.value =
      e.response?.data?.detail || e.message || '请确认后端 API 已启动后点击重试。'
    ElMessage.error(e.response?.data?.detail || e.message || '加载状态失败')
  } finally {
    loading.value = false
  }
}

async function triggerStrategyCycle() {
  cycleTriggering.value = true
  try {
    const res = await axios.post('/api/v1/strategy-cycle/trigger', {
      trigger_type: 'manual'
    })
    ElMessage.success(res.data?.message || '策略闭环已启动')
    await loadCycleStatus(false)
    startPolling()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '触发策略闭环失败')
  } finally {
    cycleTriggering.value = false
  }
}

async function runDataSync() {
  runningNow.value = true
  try {
    await dataApi.syncDailyBarsStream({ scope: scope.value, mode: form.value.sync_mode }, (ev) => {
      if (ev.event === "phase_start") stageProgress.value[ev.phase] = "running"
      if (ev.event === "phase_complete") stageProgress.value[ev.phase] = "success"
      if (ev.event === "error") stageProgress.value.klines = "failed"
    })
    ElMessage.success('数据仓同步完成')
    await refreshStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '数据仓同步失败')
  } finally {
    runningNow.value = false
  }
}

async function saveConfig() {
  if (!timeValue.value) {
    ElMessage.warning('请选择每日同步时间')
    return
  }
  saving.value = true
  try {
    const data = await syncSchedulerApi.saveConfig({
      enabled: form.value.enabled,
      time_of_day: timeValue.value,
      sync_mode: form.value.sync_mode
    })
    applyStatus(data)
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function runNow() {
  runningNow.value = true
  try {
    const data = await syncSchedulerApi.runNow()
    applyStatus(data)
    if (data.accepted) {
      ElMessage.success(data.message || '同步已启动')
      startPolling()
    } else {
      ElMessage.warning(data.message || '同步未启动')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '触发失败')
  } finally {
    runningNow.value = false
  }
}

onMounted(() => {
  refreshStatus()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.progress-panel {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 13px;
}

.progress-phase {
  margin: 0 0 6px;
}

.progress-msg,
.progress-symbol {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.45;
}

.hint-alert {
  margin-top: 16px;
}

.cycle-header {
  margin-bottom: 12px;
}

.cycle-summary {
  margin-bottom: 12px;
}

.cycle-history {
  margin-top: 12px;
}

.error-text {
  color: var(--el-color-danger);
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
