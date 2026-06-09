<template>
  <el-card shadow="never" class="rb-card cycle-status-card">
    <template #header>
      <div class="rb-page-header">
        <span>策略自进化闭环</span>
        <div class="header-actions">
          <el-button link type="primary" :loading="loading" @click="refresh">刷新</el-button>
          <el-button
            size="small"
            type="primary"
            :loading="triggering"
            :disabled="status.is_running"
            @click="triggerCycle"
          >
            手动执行闭环
          </el-button>
        </div>
      </div>
    </template>

    <el-descriptions :column="2" border size="small" class="status-summary">
      <el-descriptions-item label="当前状态">
        <el-tag v-if="status.is_running" type="warning">运行中</el-tag>
        <el-tag
          v-else-if="status.latest_run?.status"
          :type="getStatusType(status.latest_run.status)"
        >
          {{ getStatusLabel(status.latest_run.status) }}
        </el-tag>
        <span v-else class="muted">暂无记录</span>
      </el-descriptions-item>
      <el-descriptions-item label="最近触发">
        {{ getTriggerLabel(status.latest_run?.trigger_type) }}
      </el-descriptions-item>
      <el-descriptions-item label="最近开始">
        {{ formatTime(status.latest_run?.started_at) }}
      </el-descriptions-item>
      <el-descriptions-item label="最近结束">
        {{ formatTime(status.latest_run?.finished_at) }}
      </el-descriptions-item>
      <el-descriptions-item label="策略数">
        {{ status.latest_run?.total_strategies || 0 }}
      </el-descriptions-item>
      <el-descriptions-item label="信号执行">
        {{ status.latest_run?.signal_runs || 0 }}
      </el-descriptions-item>
      <el-descriptions-item label="健康检查">
        {{ status.latest_run?.health_checks || 0 }}
      </el-descriptions-item>
      <el-descriptions-item label="优化任务">
        {{ status.latest_run?.optimization_jobs || 0 }}
      </el-descriptions-item>
      <el-descriptions-item v-if="status.latest_run?.error" label="最近错误" :span="2">
        <span class="error-text">{{ status.latest_run.error }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="status.is_running && status.progress" class="progress-panel">
      <p class="progress-phase">
        当前阶段：<strong>{{ getPhaseLabel(status.progress.phase) }}</strong>
      </p>
      <p v-if="status.progress.message" class="progress-msg">{{ status.progress.message }}</p>
      <p v-if="status.progress.sub_phase" class="progress-symbol">
        子阶段：{{ status.progress.sub_phase }}
      </p>
      <el-progress
        v-if="progressPercent != null"
        :percentage="progressPercent"
        :format="progressBarFormat"
        style="margin-top: 8px"
      />
    </div>

    <template v-if="history.length">
      <el-divider />
      <div class="section-title">执行历史</div>
      <el-table :data="history" size="small" stripe max-height="240">
        <el-table-column prop="started_at" label="开始时间" width="150">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="trigger_type" label="触发" width="80">
          <template #default="{ row }">{{ getTriggerLabel(row.trigger_type) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_strategies" label="策略" width="70" />
        <el-table-column prop="signal_runs" label="信号" width="70" />
        <el-table-column prop="health_checks" label="健康" width="70" />
        <el-table-column prop="optimization_jobs" label="优化" width="70" />
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ formatDuration(row) }}</template>
        </el-table-column>
      </el-table>
    </template>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const triggering = ref(false)
const status = ref({
  is_running: false,
  progress: null,
  latest_run: null
})
const history = ref([])
const pollTimer = ref(null)

const progressPercent = computed(() => {
  const p = status.value.progress
  if (!p || p.current == null || p.total == null || p.total <= 0) return null
  return Math.min(100, Math.round((p.current / p.total) * 100))
})

function progressBarFormat() {
  const p = status.value.progress
  return p ? `${p.current}/${p.total}` : ''
}

function getPhaseLabel(phase) {
  const map = { backfill: '回填收益', processing: '策略处理' }
  return map[phase] || phase || '—'
}

function getStatusLabel(s) {
  const map = { running: '运行中', completed: '完成', failed: '失败' }
  return map[s] || s || '—'
}

function getStatusType(s) {
  const map = { running: 'warning', completed: 'success', failed: 'danger' }
  return map[s] || 'info'
}

function getTriggerLabel(t) {
  if (t === 'scheduled') return '定时'
  if (t === 'manual') return '手动'
  if (t === 'auto') return '同步后'
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

function formatDuration(row) {
  if (!row.started_at || !row.finished_at) return '—'
  try {
    const start = new Date(row.started_at)
    const end = new Date(row.finished_at)
    const seconds = Math.round((end - start) / 1000)
    if (seconds < 60) return `${seconds}秒`
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${minutes}分${secs}秒`
  } catch {
    return '—'
  }
}

async function refresh() {
  loading.value = true
  try {
    const [statusRes, historyRes] = await Promise.all([
      axios.get('/api/v1/strategy-cycle/status'),
      axios.get('/api/v1/strategy-cycle/history', { params: { limit: 10 } })
    ])
    status.value = statusRes.data || { is_running: false, progress: null, latest_run: null }
    history.value = historyRes.data?.runs || []

    if (status.value.is_running) {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载策略闭环状态失败')
  } finally {
    loading.value = false
  }
}

async function triggerCycle() {
  triggering.value = true
  try {
    const res = await axios.post('/api/v1/strategy-cycle/trigger', {
      trigger_type: 'manual'
    })
    ElMessage.success(res.data?.message || '策略闭环已启动')
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '触发策略闭环失败')
  } finally {
    triggering.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer.value = setInterval(async () => {
    try {
      const statusRes = await axios.get('/api/v1/strategy-cycle/status')
      status.value = statusRes.data || { is_running: false, progress: null, latest_run: null }
      if (!status.value.is_running) {
        stopPolling()
        // 刷新历史记录
        const historyRes = await axios.get('/api/v1/strategy-cycle/history', { params: { limit: 10 } })
        history.value = historyRes.data?.runs || []
      }
    } catch {
      // 忽略轮询错误
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onMounted(() => {
  refresh()
})

onUnmounted(() => {
  stopPolling()
})

defineExpose({ refresh })
</script>

<style scoped>
.cycle-status-card {
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-summary {
  margin-bottom: 12px;
}

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

.section-title {
  margin-bottom: 10px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.error-text {
  color: var(--el-color-danger);
}

.muted {
  color: var(--el-text-color-secondary);
}
</style>
