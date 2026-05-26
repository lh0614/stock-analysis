<template>
  <div class="screener-page">
    <div class="screener-page__head">
      <h1 class="rb-page-title">选股器</h1>
      <p class="rb-page-desc">股票池来自本地库；左侧按状态、操作与帮助分区说明。</p>
    </div>

    <el-row :gutter="12" class="screener-body">
      <el-col :xs="24" :lg="7" class="screener-col">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="preset-header">
              <span>选股预设</span>
              <el-button link type="primary" size="small" @click="selectAllPresets">全选</el-button>
              <el-button link size="small" @click="presetIds = []">清空</el-button>
            </div>
          </template>
          <div class="panel-scroll">
            <section class="panel-section">
              <h3 class="panel-section__title">状态区</h3>
              <p class="universe-stats">
                本地股票库共 {{ universeStats.total || 0 }} 只
                <span v-if="universeStats.klines_complete != null">
                  · 全量已完成 {{ universeStats.klines_complete }}
                </span>
                <span v-if="universeStats.klines_pending_incremental">
                  · 可增量 {{ universeStats.klines_pending_incremental }}
                </span>
                <span v-if="universeStats.klines_pending_full">
                  · 待全量 {{ universeStats.klines_pending_full }}
                </span>
              </p>
              <p class="board-hint">
                <span v-if="universeStats.last_sync_display">
                  上次同步：{{ universeStats.last_sync_display }}
                </span>
                <span v-else>尚未同步</span>
              </p>
              <p v-if="universeStats.history_range" class="board-hint">
                K 线范围：{{ universeStats.history_range }}（上市首日至今）
              </p>
              <p v-if="universeStats.sync_reminder" class="sync-reminder">
                {{ universeStats.sync_reminder }}
              </p>
            </section>

            <el-divider />

            <section class="panel-section">
              <h3 class="panel-section__title">操作区</h3>
              <el-checkbox-group v-model="presetIds" class="preset-list">
                <el-checkbox
                  v-for="p in presets"
                  :key="p.id"
                  :value="p.id"
                  class="preset-item"
                >
                  <strong>{{ p.name }}</strong>
                  <p class="preset-desc">{{ p.description }}</p>
                </el-checkbox>
              </el-checkbox-group>
              <p v-if="!presetIds.length" class="preset-warn">请至少勾选一个预设</p>
              <div class="universe-panel__head sync-row">
                <span>数据同步</span>
                <div class="universe-actions">
                  <el-button
                    size="small"
                    type="primary"
                    :loading="syncing"
                    @click="syncUniverse('incremental')"
                  >
                    增量更新
                  </el-button>
                  <el-button size="small" :loading="syncing" @click="syncUniverse('full')">
                    全量续传
                  </el-button>
                </div>
              </div>
              <el-form label-width="88px" size="small" class="scan-form">
                <el-form-item label="仅本地K线">
                  <el-switch v-model="preferLocalCache" />
                </el-form-item>
                <el-form-item label="扫描板块">
                  <div class="board-toggles">
                    <el-checkbox v-model="includeChinext">创业板</el-checkbox>
                    <el-checkbox v-model="includeStar">科创板</el-checkbox>
                    <el-checkbox v-model="includeBse">北交所</el-checkbox>
                  </div>
                </el-form-item>
                <el-form-item label="排除 ST">
                  <el-switch v-model="excludeSt" />
                </el-form-item>
                <el-form-item label="扫描范围">
                  <el-radio-group v-model="scanScope">
                    <el-radio value="filtered">按板块筛选</el-radio>
                    <el-radio value="custom">自定义股票</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item v-if="scanScope === 'custom'" label="代码列表">
                  <el-input
                    v-model="customSymbolsText"
                    type="textarea"
                    :rows="2"
                    placeholder="每行或逗号分隔"
                    @blur="saveCustomPool"
                  />
                </el-form-item>
              </el-form>
            </section>

            <el-divider />

            <section class="panel-section panel-section--help">
              <h3 class="panel-section__title">帮助区</h3>
              <ul class="help-list">
                <li>多选预设为<strong>交集</strong>：须同时满足所有已勾条件。</li>
                <li>
                  <strong>增量</strong>仅补已有全量 pkl 的落后日 K；<strong>全量</strong>含列表与断点续传，用于首次或未完成全量。
                </li>
                <li>开启「仅本地 K 线」时不访问外网；某只股票无 pkl 缓存则扫描时跳过。</li>
                <li>K 线须先在驾驶舱或本页同步生成 pkl 后，扫描结果才可靠。</li>
              </ul>
            </section>
          </div>
          <div class="panel-footer">
            <el-button
              type="primary"
              :loading="scanning"
              :disabled="!presetIds.length"
              style="width: 100%"
              @click="runScan"
            >
              开始扫描
            </el-button>
            <el-progress
              v-if="scanning || (syncing && progressTotal)"
              :percentage="progressPct"
              :format="() => `${progressCurrent}/${progressTotal}`"
              style="margin-top: 8px"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="9" class="screener-col">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <span>扫描过程</span>
            <el-tag v-if="currentSymbol" size="small" type="warning" class="head-tag">
              正在扫 {{ currentSymbol }} {{ currentName }}
            </el-tag>
          </template>
          <div ref="logScrollRef" class="panel-scroll scan-log">
            <div
              v-for="(line, i) in scanLog"
              :key="i"
              class="scan-log__line"
              :class="`scan-log__line--${line.status}`"
            >
              <span class="scan-log__sym">{{ line.symbol }}</span>
              <span class="scan-log__name">{{ line.name }}</span>
              <span class="scan-log__msg">{{ line.message }}</span>
            </div>
            <el-empty v-if="!scanLog.length && !scanning" description="开始扫描后显示进度" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8" class="screener-col">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="result-header">
              <span>命中结果</span>
              <el-tag v-if="matchedTotal" type="success">{{ matchedTotal }} 只</el-tag>
            </div>
          </template>
          <div class="panel-scroll result-table-wrap">
            <el-table :data="displayResults" border size="small" height="100%">
              <el-table-column prop="symbol" label="代码" width="72" />
              <el-table-column prop="name" label="名称" min-width="72" show-overflow-tooltip />
              <el-table-column label="预设" min-width="88">
                <template #default="{ row }">
                  <el-tag
                    v-for="p in row.matched_presets || []"
                    :key="p.id"
                    size="small"
                    type="success"
                    class="metric-tag"
                  >
                    {{ p.name }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="goAnalyze(row.symbol)">
                    分析
                  </el-button>
                  <el-button link size="small" @click="addWatch(row)">自选</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty
              v-if="!displayResults.length && !scanning"
              description="命中股票将实时出现在此"
            />
          </div>
          <AppPagination
            v-if="resultTotal > 0"
            v-model:page="resultPage"
            v-model:page-size="resultPageSize"
            :total="resultTotal"
            :hide-on-single-page="false"
            @change="onResultPageChange"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import screenerApi from '@/api/screener.js'
import universeApi from '@/api/universe.js'
import watchlistApi from '@/api/watchlist.js'
import AppPagination from '@/components/common/AppPagination.vue'

const router = useRouter()
const presets = ref([])
const presetIds = ref(['rsi_oversold'])
const scanning = ref(false)
const runId = ref(null)
const progressCurrent = ref(0)
const progressTotal = ref(0)
const preferLocalCache = ref(true)
const includeChinext = ref(false)
const includeStar = ref(false)
const includeBse = ref(false)
const excludeSt = ref(true)
const scanScope = ref('filtered')
const customSymbolsText = ref('')
const syncing = ref(false)
const universeStats = ref({
  total: 0,
  boards: {},
  st: 0,
  last_sync: null,
  last_sync_display: null,
  synced_today: false,
  stale_sync: true,
  sync_reminder: null,
  klines_full: 0,
  klines_complete: 0,
  klines_pending: 0,
  klines_pending_incremental: 0,
  klines_pending_full: 0,
  history_range: '1990-01-01 ~ 今日'
})

const scanLog = ref([])
const logScrollRef = ref(null)
const currentSymbol = ref('')
const currentName = ref('')

const allResults = ref([])
const serverResults = ref([])
const resultPage = ref(1)
const resultPageSize = ref(20)
const resultTotal = ref(0)
const matchedTotal = ref(0)
const useServerPagination = ref(false)

const progressPct = computed(() => {
  if (!progressTotal.value) return 0
  return Math.round((progressCurrent.value / progressTotal.value) * 100)
})

const displayResults = computed(() =>
  useServerPagination.value ? serverResults.value : paginateClient(allResults.value)
)

function paginateClient(list) {
  const start = (resultPage.value - 1) * resultPageSize.value
  return list.slice(start, start + resultPageSize.value)
}

function statusLabel(item) {
  if (item.status === 'matched') return '符合'
  if (item.status === 'not_matched') return '不符合'
  if (item.status === 'no_data') return '无数据'
  if (item.status === 'ok') {
    if (item.incremental && item.bars_added != null) {
      return `增量 +${item.bars_added} 根 (${item.fetch_start}~${item.fetch_end})`
    }
    return `K线 ${item.bars} 根 (${item.first_date}~${item.last_date})`
  }
  if (item.status === 'skipped') {
    return item.message || `已至最新 ${item.last_date || ''}`
  }
  if (item.status === 'failed') return `K线失败: ${item.error || ''}`
  return item.message || item.status
}

function klinesLogStatus(item) {
  if (item.status === 'ok') return 'matched'
  if (item.status === 'skipped') return 'not_matched'
  return 'no_data'
}

function pushLog(item) {
  scanLog.value.push({
    symbol: item.symbol,
    name: item.name || '',
    status: item.status || 'no_data',
    message: statusLabel(item)
  })
  if (scanLog.value.length > 400) scanLog.value.shift()
  nextTick(() => {
    const el = logScrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadUniverseStats() {
  try {
    universeStats.value = await universeApi.stats()
  } catch {
    universeStats.value = {
      total: 0,
      boards: {},
      st: 0,
      last_sync: null,
      last_sync_display: null,
      synced_today: false,
      stale_sync: true,
      sync_reminder: '无法读取本地股票库状态，请确认后端已启动。'
    }
  }
}

async function syncUniverse(syncMode = 'incremental') {
  scanning.value = false
  syncing.value = true
  scanLog.value = []
  progressCurrent.value = 0
  progressTotal.value = 0
  try {
    const { final, interrupted, lastProgress } = await universeApi.syncStream((ev) => {
      if (ev.event === 'klines_start') {
        progressTotal.value = ev.total || 0
        if (ev.message) ElMessage.info(ev.message)
      }
      if (ev.event === 'klines_scanning') {
        currentSymbol.value = ev.symbol
        currentName.value = '全量K线'
        progressCurrent.value = ev.current
        progressTotal.value = ev.total
      }
      if (ev.event === 'klines_item') {
        pushLog({
          symbol: ev.symbol,
          name: '',
          status: klinesLogStatus(ev),
          message: statusLabel(ev)
        })
      }
      if (ev.event === 'list_complete') {
        ElMessage.info(ev.message || `列表 ${ev.count} 只`)
      }
    }, { syncMode })
    await loadUniverseStats()
    const text = final?.message
    if (final?.success === false) {
      ElMessage.error(text || '同步失败')
      return
    }
    if (interrupted || final?.paused || final?.resumable) {
      ElMessage.warning(
        text ||
          `进度已保存（${lastProgress}/${progressTotal.value || '?'}），再次点击「同步数据」将优先续传未完成股票`
      )
    } else {
      ElMessage.success(text || '同步完成')
    }
  } catch (e) {
    await loadUniverseStats()
    ElMessage.error(e.message || '同步失败')
  } finally {
    syncing.value = false
    currentSymbol.value = ''
    currentName.value = ''
  }
}

async function loadCustomPool() {
  try {
    const data = await universeApi.getCustom()
    customSymbolsText.value = (data.symbols || []).join('\n')
  } catch {
    customSymbolsText.value = ''
  }
}

async function saveCustomPool() {
  const symbols = customSymbolsText.value
    .split(/[\n,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  try {
    await universeApi.setCustom(symbols)
  } catch {
    /* ignore */
  }
}

async function loadPresets() {
  const data = await screenerApi.presets()
  presets.value = data.presets || []
}

function selectAllPresets() {
  presetIds.value = presets.value.map((p) => p.id)
}

async function fetchResultPage(page = resultPage.value) {
  if (!runId.value) return
  const data = await screenerApi.runResults(runId.value, page, resultPageSize.value)
  serverResults.value = data.items || []
  resultTotal.value = data.total ?? 0
  matchedTotal.value = data.matched ?? resultTotal.value
  resultPage.value = data.page ?? page
}

async function onResultPageChange({ page, pageSize }) {
  resultPage.value = page
  resultPageSize.value = pageSize
  if (useServerPagination.value) {
    await fetchResultPage(page)
  }
}

async function runScan() {
  if (!presetIds.value.length) {
    ElMessage.warning('请至少选择一个预设')
    return
  }
  scanning.value = true
  runId.value = null
  scanLog.value = []
  allResults.value = []
  serverResults.value = []
  resultPage.value = 1
  resultTotal.value = 0
  matchedTotal.value = 0
  useServerPagination.value = false
  progressCurrent.value = 0
  progressTotal.value = 0
  currentSymbol.value = ''
  currentName.value = ''

  try {
    const final = await screenerApi.runStream(
      presetIds.value,
      (ev) => {
        if (ev.event === 'start') {
          runId.value = ev.run_id
          progressTotal.value = ev.total || 0
        }
        if (ev.event === 'scanning') {
          currentSymbol.value = ev.symbol
          currentName.value = ev.name || ''
          progressCurrent.value = ev.current
          progressTotal.value = ev.total
        }
        if (ev.event === 'scan_item') {
          pushLog(ev)
        }
        if (ev.event === 'match' && ev.item) {
          allResults.value.push(ev.item)
          resultTotal.value = allResults.value.length
          matchedTotal.value = ev.matched_total ?? resultTotal.value
        }
      },
      {
        includeChinext: includeChinext.value,
        includeStar: includeStar.value,
        includeBse: includeBse.value,
        excludeSt: excludeSt.value,
        useCustomPool: scanScope.value === 'custom',
        preferLocalCache: preferLocalCache.value
      }
    )
    if (final?.run_id) {
      runId.value = final.run_id
      matchedTotal.value = final.matched ?? matchedTotal.value
      useServerPagination.value = true
      await fetchResultPage(1)
    }
    ElMessage.success(`扫描完成，命中 ${matchedTotal.value} 只`)
  } catch (e) {
    ElMessage.error(e.message || '扫描失败')
  } finally {
    scanning.value = false
    currentSymbol.value = ''
    currentName.value = ''
  }
}

function goAnalyze(symbol) {
  router.push({ path: '/', query: { symbol } })
}

async function addWatch(row) {
  await watchlistApi.add(row.symbol, 'default', row.name || '')
  ElMessage.success('已加入自选')
}

onMounted(async () => {
  await Promise.all([loadPresets(), loadUniverseStats(), loadCustomPool()])
})
</script>

<style scoped>
.screener-page {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: -8px 0 0;
}

.screener-page__head {
  flex-shrink: 0;
}

.screener-page__head .rb-page-title {
  margin: 0 0 4px;
}

.screener-page__head .rb-page-desc {
  margin: 0 0 10px;
  font-size: 13px;
}

.screener-body {
  flex: 1;
  min-height: 0;
}

.screener-col {
  height: 100%;
}

.panel-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.el-card__header) {
  flex-shrink: 0;
  padding: 10px 14px;
}

.panel-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 10px 14px 12px;
  overflow: hidden;
}

.panel-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.panel-footer {
  flex-shrink: 0;
  padding-top: 8px;
}

.preset-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-header span {
  flex: 1;
}

.preset-list {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
}

.preset-item {
  margin-bottom: 8px;
  height: auto;
  white-space: normal;
  align-items: flex-start;
}

.preset-item :deep(.el-checkbox__label) {
  white-space: normal;
  line-height: 1.35;
}

.preset-warn {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-color-warning);
}

.preset-desc {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.board-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.35;
}

.board-toggles {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.panel-section__title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.panel-section--help {
  margin-bottom: 4px;
}

.help-list {
  margin: 0;
  padding-left: 1.1em;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.help-list li {
  margin-bottom: 6px;
}

.sync-row {
  margin: 10px 0 8px;
}

.scan-form {
  margin-top: 4px;
}

.universe-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-weight: 600;
}

.universe-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.universe-stats {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.sync-reminder {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-color-warning);
}

.scan-log {
  font-size: 12px;
  line-height: 1.6;
}

.scan-log__line {
  display: flex;
  gap: 6px;
  padding: 2px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.scan-log__sym {
  font-family: ui-monospace, monospace;
  min-width: 52px;
}

.scan-log__name {
  min-width: 56px;
  color: var(--el-text-color-secondary);
}

.scan-log__line--matched .scan-log__msg {
  color: var(--el-color-success);
}

.scan-log__line--not_matched .scan-log__msg {
  color: var(--el-text-color-secondary);
}

.scan-log__line--no_data .scan-log__msg {
  color: var(--el-color-warning);
}

.head-tag {
  margin-left: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-table-wrap {
  display: flex;
  flex-direction: column;
}

.result-table-wrap :deep(.el-table) {
  flex: 1;
}

.metric-tag {
  margin: 1px 2px 1px 0;
}
</style>
