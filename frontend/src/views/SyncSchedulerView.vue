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
import syncSchedulerApi from '@/api/syncScheduler.js'
import BackendState from '@/components/common/BackendState.vue'

const loading = ref(false)
const statusLoadError = ref(false)
const statusLoadErrorMessage = ref('')
const saving = ref(false)
const runningNow = ref(false)
const pollTimer = ref(null)

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
      if (!data.running) stopPolling()
    } catch {
      /* ignore poll errors */
    }
  }, 2000)
}

async function refreshStatus() {
  loading.value = true
  statusLoadError.value = false
  statusLoadErrorMessage.value = ''
  try {
    const data = await syncSchedulerApi.status()
    applyStatus(data)
    if (data.running) startPolling()
  } catch (e) {
    statusLoadError.value = true
    statusLoadErrorMessage.value =
      e.response?.data?.detail || e.message || '请确认后端 API 已启动后点击重试。'
    ElMessage.error(e.response?.data?.detail || e.message || '加载状态失败')
  } finally {
    loading.value = false
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
.error-text {
  color: var(--el-color-danger);
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
