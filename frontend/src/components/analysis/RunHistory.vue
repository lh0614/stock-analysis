<template>
  <el-card shadow="never" class="rb-card run-history">
    <template #header>
      <div class="header-row">
        <span>最近分析记录</span>
        <el-button link type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="runs" size="small" stripe max-height="220">
      <el-table-column prop="created_at" label="时间" width="150" show-overflow-tooltip />
      <el-table-column prop="symbol" label="代码" width="72" />
      <el-table-column label="结果" width="64">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'" size="small">
            {{ row.success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="run_id" label="运行 ID" min-width="100" show-overflow-tooltip />
      <el-table-column label="数据源" width="88" show-overflow-tooltip>
        <template #default="{ row }">
          {{ displayText(row.data_source) }}
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="72">
        <template #default="{ row }">
          {{ displayText(row.duration_display) }}
        </template>
      </el-table-column>
      <el-table-column label="缓存" width="56">
        <template #default="{ row }">
          {{ formatCached(row.cached) }}
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !runs.length" description="暂无记录" />
  </el-card>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import analysisApi from '@/api/analysis.js'

const props = defineProps({
  symbol: { type: String, default: '' }
})

const runs = ref([])
const loading = ref(false)

const ENRICH_LIMIT = 5

function displayText(val) {
  if (val === null || val === undefined || val === '') return '—'
  return String(val)
}

function formatCached(val) {
  if (val === true) return '是'
  if (val === false) return '否'
  return '不详'
}

function formatDurationMs(ms) {
  if (ms == null || Number.isNaN(ms)) return null
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function extractIngestMeta(detail) {
  const stages = detail?.stages || []
  const ingest = stages.find((s) => s.id === 'ingest')
  const d = ingest?.detail || {}
  return {
    data_source: d.data_source ?? detail?.metadata?.data_source ?? null,
    cached: d.cached ?? detail?.metadata?.cached ?? null
  }
}

function computeDurationDisplay(detail) {
  const started = detail?.started_at
  const finished = detail?.finished_at
  if (started && finished) {
    const ms = new Date(finished).getTime() - new Date(started).getTime()
    if (!Number.isNaN(ms) && ms >= 0) return formatDurationMs(ms)
  }
  const stages = detail?.stages || []
  const withDur = stages.filter((s) => s.duration_ms != null)
  if (withDur.length) {
    const last = withDur[withDur.length - 1]
    return formatDurationMs(last.duration_ms)
  }
  return null
}

function enrichRow(row, detail) {
  if (!detail) return { ...row, data_source: null, cached: null, duration_display: null }
  const meta = extractIngestMeta(detail)
  return {
    ...row,
    data_source: meta.data_source,
    cached: meta.cached,
    duration_display: computeDurationDisplay(detail)
  }
}

async function enrichRuns(rows) {
  const base = rows.map((r) => enrichRow(r, null))
  const toFetch = base.slice(0, ENRICH_LIMIT).filter((r) => r.run_id)
  if (!toFetch.length) return base

  const details = await Promise.all(
    toFetch.map(async (r) => {
      try {
        return await analysisApi.getRun(r.run_id)
      } catch {
        return null
      }
    })
  )

  const byId = new Map(toFetch.map((r, i) => [r.run_id, details[i]]))
  return base.map((r) => (byId.has(r.run_id) ? enrichRow(r, byId.get(r.run_id)) : r))
}

async function load() {
  if (!props.symbol) {
    runs.value = []
    return
  }
  loading.value = true
  try {
    const data = await analysisApi.listRuns(props.symbol, 10)
    const rows = data.runs || []
    runs.value = await enrichRuns(rows)
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.symbol, load)
onMounted(load)

defineExpose({ load })
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.run-history {
  margin-top: 12px;
}
</style>
