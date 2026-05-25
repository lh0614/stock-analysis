<template>
  <el-card class="rb-card pipeline-card" shadow="never">
    <template #header>
      <div class="pipeline-header">
        <span>分析流水线</span>
        <div class="pipeline-header-actions">
          <el-tag v-if="loading" type="warning" size="small">运行中…</el-tag>
          <el-tag v-else-if="runId" type="success" size="small">运行 #{{ shortRunId }}</el-tag>
          <el-button
            v-if="checkpoint?.resumable && !loading"
            type="warning"
            size="small"
            @click="$emit('resume')"
          >
            继续上次分析（{{ checkpoint.failed_stage || checkpoint.next_stage }}）
          </el-button>
        </div>
      </div>
    </template>

    <el-steps :active="activeStep" finish-status="success" align-center>
      <el-step
        v-for="stage in displayStages"
        :key="stage.id"
        :title="stage.label"
        :status="stepStatus(stage.status)"
        :description="stageDesc(stage)"
      />
    </el-steps>

    <el-collapse v-if="stages?.length" class="stage-detail">
      <el-collapse-item title="阶段详情 / 数据血缘" name="detail">
        <el-timeline>
          <el-timeline-item
            v-for="s in stages"
            :key="s.id"
            :type="timelineType(s.status)"
            :timestamp="`${s.duration_ms}ms`"
          >
            <strong>{{ s.label }}</strong> — {{ statusLabel(s.status) }}
            <pre v-if="s.detail && Object.keys(s.detail).length" class="detail-json">{{
              JSON.stringify(s.detail, null, 2)
            }}</pre>
          </el-timeline-item>
        </el-timeline>
      </el-collapse-item>
    </el-collapse>

    <el-empty v-if="!loading && !stages?.length" description="选择股票后将自动运行分析流水线" />
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const DEFAULT_STAGES = [
  { id: 'ingest', label: '采集', status: 'wait' },
  { id: 'validate', label: '质检', status: 'wait' },
  { id: 'feature', label: '特征', status: 'wait' },
  { id: 'strategy', label: '策略', status: 'wait' },
  { id: 'predict', label: '预测', status: 'wait' },
  { id: 'direction', label: '方向', status: 'wait' },
  { id: 'present', label: '呈现', status: 'wait' }
]

defineEmits(['resume'])

const props = defineProps({
  stages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  runId: { type: String, default: '' },
  checkpoint: { type: Object, default: null }
})

const shortRunId = computed(() =>
  props.runId ? props.runId.slice(0, 8) : ''
)

const displayStages = computed(() => {
  if (props.stages?.length) return props.stages
  return DEFAULT_STAGES.map((s) => ({
    ...s,
    status: props.loading && s.id === 'ingest' ? 'running' : 'wait'
  }))
})

const activeStep = computed(() => {
  const list = displayStages.value
  let last = 0
  list.forEach((s, i) => {
    if (s.status === 'success') last = i + 1
    if (s.status === 'running') last = i
    if (s.status === 'failed') last = i
  })
  return last
})

function stepStatus(status) {
  const map = {
    success: 'success',
    failed: 'error',
    running: 'process',
    wait: 'wait'
  }
  return map[status] || 'wait'
}

function timelineType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'primary'
  return 'info'
}

function statusLabel(status) {
  const map = {
    success: '完成',
    failed: '失败',
    running: '进行中',
    wait: '等待'
  }
  return map[status] || status
}

function stageDesc(stage) {
  if (stage.status === 'running') return '进行中…'
  if (stage.detail?.rows) return `${stage.detail.rows} 条`
  if (stage.detail?.data_source) return stage.detail.data_source
  return ''
}
</script>

<style scoped>
.pipeline-card {
  margin-bottom: 20px;
}

.pipeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.pipeline-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stage-detail {
  margin-top: 20px;
}

.detail-json {
  font-size: 11px;
  background: var(--el-fill-color-light);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  margin-top: 6px;
}
</style>
