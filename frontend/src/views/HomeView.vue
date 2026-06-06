<template>
  <div class="rb-page home-view premium-cockpit">

    <!-- 1. 极简顶部控制条 (48px 固定高度) -->
    <div class="top-control-bar">
      <div class="control-left">
        <el-input
          v-model="searchSymbol"
          placeholder="输入股票代码或名称"
          class="search-input"
          @keyup.enter="handleSearch"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :loading="searchLoading" @click="handleSearch">分析</el-button>
        <el-button :disabled="!currentSymbol" :loading="refreshing" @click="refreshData">刷新</el-button>
      </div>

      <div class="control-right">
        <el-select
          v-if="workflowStore.workflows.length"
          v-model="workflowStore.selectedWorkflowId"
          placeholder="工作流"
          size="default"
          style="width: 140px"
        >
          <el-option
            v-for="wf in workflowStore.workflows"
            :key="wf.id"
            :label="wf.name"
            :value="wf.id"
          />
        </el-select>
        <el-button :icon="Download" @click="exportData" title="导出数据">导出</el-button>
      </div>
    </div>

    <!-- 2. 合规免责 & 数据质量 (极简) -->
    <ComplianceDisclaimer />
    <QualityBanner :level="qualityInfo?.quality_level || ''" :hint="qualityInfo?.ui_hint || ''" />

    <!-- 3. 标的信息 + 三周期方向 (一行搞定，无边框) -->
    <div v-if="currentSymbol" class="stock-header-bar">
      <div class="stock-info">
        <h1 class="stock-name">{{ getStockName(currentSymbol) }}</h1>
        <span class="stock-code">{{ currentSymbol }}</span>
        <div class="stock-price">
          <span class="price-value">{{ summaryData?.close || '—' }}</span>
          <span class="price-change" :class="summaryData?.change_pct >= 0 ? 'up' : 'down'">
            {{ summaryData?.change_pct >= 0 ? '+' : '' }}{{ summaryData?.change_pct || '—' }}%
          </span>
        </div>
        <span class="update-time">{{ lastUpdateTime || '—' }}</span>
      </div>

      <div class="direction-summary">
        <DirectionCards
          :directions="directions"
          :loading="pipelineLoading"
          :error="directionError"
          :quality-level="qualityInfo?.quality_level || ''"
          :quality-hint="qualityInfo?.ui_hint || ''"
        />
      </div>
    </div>

    <!-- 4. K 线主图区 (600px 高度，无卡片边框) -->
    <StockChart
      v-if="currentSymbol"
      :symbol="currentSymbol"
      :chart-period="workflowStore.selectedWorkflow?.chart_period || '1y'"
      class="chart-main"
    />

    <!-- 5. 详情 Tab 区 (去掉 emoji，纯文字) -->
    <div v-if="currentSymbol" class="details-section">
      <el-tabs v-model="activeDetailTab" class="premium-tabs">
        <el-tab-pane label="支撑/压力" name="levels">
          <div class="tab-content">
            <el-row :gutter="20">
              <el-col :xs="24" :md="12">
                <PriceLevelsPanel
                  :data="priceLevels"
                  :loading="pipelineLoading"
                  :error="priceError"
                />
              </el-col>
              <el-col :xs="24" :md="12">
                <ForecastTabs :forecasts="forecasts" :loading="pipelineLoading" />
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <el-tab-pane label="数据中心" name="data-cockpit">
          <div class="tab-content">
            <DataCockpit
              :symbol="currentSymbol"
              :quality-info="qualityInfo"
              @data-updated="applyPipelineResult"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="技术指标" name="indicators">
          <div class="tab-content">
            <TechnicalIndicators
              :indicators-data="indicatorsData"
              :loading="indicatorsLoading"
              :error="indicatorsError"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="新闻资讯" name="news">
          <div class="tab-content">
            <NewsTimeline :symbol="currentSymbol" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="流水线" name="pipeline">
          <div class="tab-content">
            <AnalysisPipeline
              :stages="pipelineStages"
              :loading="pipelineLoading"
              :run-id="pipelineRunId"
              :checkpoint="resumableCheckpoint"
              @resume="resumeAnalysisPipeline"
            />
            <RunHistory ref="runHistoryRef" :symbol="currentSymbol" class="mt-20" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="历史数据" name="history">
          <div class="tab-content">
            <StockHistory :symbol="currentSymbol" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="自选股" name="watchlist">
          <div class="tab-content">
            <WatchlistPanel
              ref="watchlistRef"
              :current-symbol="currentSymbol"
              @select="onWatchlistSelect"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 策略输出、市场环境、计划草稿 (折叠到底部) -->
    <div v-if="strategyOutput || marketInfo || planDraft" class="extra-info">
      <el-collapse>
        <el-collapse-item v-if="strategyOutput" title="策略输出" name="strategy">
          <StrategyOutput :output="strategyOutput" :strategy-name="strategyName" />
        </el-collapse-item>
        <el-collapse-item v-if="interpretation" title="AI 解读" name="interpretation">
          <InterpretationCard :data="interpretation" />
        </el-collapse-item>
        <el-collapse-item v-if="marketInfo" title="市场环境" name="market">
          <p>状态：{{ marketInfo.market_regime || "—" }} · 评分：{{ marketInfo.score ?? "—" }}</p>
          <p class="text-secondary">{{ marketInfo.summary }}</p>
        </el-collapse-item>
        <el-collapse-item v-if="planDraft" title="交易计划草稿" name="plan">
          <p>触发价：{{ planDraft.trigger_price }} · 失效价：{{ planDraft.invalid_price }}</p>
          <p>第一目标：{{ planDraft.target_price_1 }}</p>
          <el-button size="small" type="primary" @click="savePlanDraft">保存为交易计划</el-button>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 后端离线遮罩 -->
    <BackendState
      v-if="showBackendState"
      :type="backendStateType"
      :title="backendStateTitle"
      :description="backendStateDesc"
      :retrying="checkingStatus"
      @retry="onBackendRetry"
    />

    <!-- 数据质量问题弹窗 -->
    <DataQualityDialog
      v-model="showQualityDialog"
      :symbol="currentSymbol"
      :quality-info="qualityInfo"
      @retry="handleQualityRetry"
      @continue="handleQualityContinue"
      @cancel="handleQualityCancel"
    />

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download } from '@element-plus/icons-vue'
import { useWorkflowStore } from '@/stores/workflow.js'
import strategyApi from '@/api/strategy.js'
import plansApi from '@/api/plans.js'

import AnalysisToolbar from '@/components/analysis/AnalysisToolbar.vue'
import StrategyOutput from '@/components/analysis/StrategyOutput.vue'
import StockChart from '@/components/StockChart.vue'
import AnalysisPipeline from '@/components/analysis/AnalysisPipeline.vue'
import RunHistory from '@/components/analysis/RunHistory.vue'
import DirectionCards from '@/components/analysis/DirectionCards.vue'
import PriceLevelsPanel from '@/components/analysis/PriceLevelsPanel.vue'
import ForecastTabs from '@/components/analysis/ForecastTabs.vue'
import InterpretationCard from '@/components/analysis/InterpretationCard.vue'
import NewsTimeline from '@/components/analysis/NewsTimeline.vue'
import WatchlistPanel from '@/components/WatchlistPanel.vue'
import DataCockpit from '@/components/analysis/DataCockpit.vue'
import analysisApi from '@/api/analysis.js'
import StockHistory from '@/components/StockHistory.vue'
import TechnicalIndicators from '@/components/TechnicalIndicators.vue'
import BackendState from '@/components/common/BackendState.vue'
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'
import QualityBanner from '@/components/common/QualityBanner.vue'
import DataQualityDialog from '@/components/common/DataQualityDialog.vue'
import stockApi from '@/api/stock.js'

const searchSymbol = ref('')
const currentSymbol = ref('000001')
const searchLoading = ref(false)
const refreshing = ref(false)
const pipelineLoading = ref(false)
const pipelineStages = ref([])
const pipelineRunId = ref('')
const resumableCheckpoint = ref(null)
const directions = ref(null)
const directionError = ref('')
const priceLevels = ref(null)
const priceError = ref('')
const forecasts = ref(null)
const strategyOutput = ref(null)
const strategyName = ref('')
const strategies = ref([])
const runHistoryRef = ref(null)
const watchlistRef = ref(null)
const interpretation = ref(null)
const qualityInfo = ref(null)
const marketInfo = ref(null)
const planDraft = ref(null)
const route = useRoute()
const workflowStore = useWorkflowStore()
const backendStatus = ref('unknown')
const backendUnreachable = ref(false)
const checkingStatus = ref(false)
const activeDetailTab = ref('levels')

const showBackendState = computed(() => backendStatus.value === 'error' || backendUnreachable.value)
const backendStateType = computed(() => (backendUnreachable.value ? 'offline' : 'error'))
const backendStateTitle = computed(() =>
  backendUnreachable.value ? '后端服务未连接' : '部分数据加载失败'
)
const backendStateDesc = computed(() =>
  backendUnreachable.value
    ? '请确认 API 服务已启动（默认 http://localhost:8000），连接后可重试加载工作流与行情。'
    : '上次请求未完全成功，可重试检查连接并刷新当前标的。'
)
const lastUpdateTime = ref('')
const showQualityDialog = ref(false)

const summaryData = ref(null)
const summaryLoading = ref(false)
const summaryError = ref('')
const indicatorsData = ref(null)
const indicatorsLoading = ref(false)
const indicatorsError = ref('')

const exampleStocks = ref([
  { code: '000001', name: '平安银行' },
  { code: '002685', name: '华东重机' },
  { code: '600519', name: '贵州茅台' },
  { code: '000858', name: '五粮液' },
  { code: '300750', name: '宁德时代' },
  { code: '002594', name: '比亚迪' },
  { code: '000002', name: '万科A' },
  { code: '601318', name: '中国平安' },
  { code: '600036', name: '招商银行' }
])

const getStockName = (code) => {
  const stock = exampleStocks.value.find(s => s.code === code)
  return stock ? stock.name : '未知股票'
}

const handleSearch = async () => {
  if (!searchSymbol.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  await loadStockData(searchSymbol.value.trim())
}

const loadStockData = async (code) => {
  try {
    searchLoading.value = true
    currentSymbol.value = code
    searchSymbol.value = code

    await Promise.all([
      fetchStockSummary(),
      fetchTechnicalIndicators(),
      runAnalysisPipeline()
    ])

    lastUpdateTime.value = new Date().toLocaleTimeString()
    await fetchResumableCheckpoint()
    ElMessage.success(`股票 ${code} 数据加载成功`)
  } catch (error) {
    backendUnreachable.value = backendStatus.value === 'error'
    ElMessage.error(`加载股票数据失败: ${error.message}`)
  } finally {
    searchLoading.value = false
  }
}

const fetchStockSummary = async () => {
  summaryLoading.value = true
  summaryError.value = ''

  try {
    const data = await stockApi.getStockSummary(currentSymbol.value)
    summaryData.value = data
  } catch (error) {
    summaryError.value = `获取摘要失败: ${error.message}`
  } finally {
    summaryLoading.value = false
  }
}

const applyPipelineResult = (result) => {
  if (!result) return
  pipelineStages.value = result.stages || []
  pipelineRunId.value = result.run_id || ''
  if (result.success) {
    directions.value = result.directions || null
    priceLevels.value = result.price_levels || null
    forecasts.value = result.forecasts || null
    strategyOutput.value = result.strategy_output || null
    strategyName.value =
      strategies.value.find((s) => s.id === workflowStore.selectedStrategyId)?.name || ''
    interpretation.value = result.interpretation || null
    qualityInfo.value = result.quality || null
    marketInfo.value = result.market || null
    planDraft.value = result.plan_draft || null
    directionError.value = ''

    // 检查质量问题并弹窗
    if (qualityInfo.value?.quality_level === 'D' && qualityInfo.value?.can_retry) {
      showQualityDialog.value = true
    }

    if (result.indicators) {
      indicatorsData.value = { symbol: currentSymbol.value, data: result.indicators }
      indicatorsError.value = ''
    }
  } else {
    directionError.value = result.error || '分析流水线未完成'
  }
}

const fetchResumableCheckpoint = async () => {
  if (!currentSymbol.value) {
    resumableCheckpoint.value = null
    return
  }
  try {
    const data = await analysisApi.getCheckpoint(currentSymbol.value)
    resumableCheckpoint.value = data.resumable ? data : null
  } catch {
    resumableCheckpoint.value = null
  }
}

const runStream = async (streamFn, onEvent) => {
  const result = await streamFn(onEvent)
  applyPipelineResult(result)
  await fetchResumableCheckpoint()
  runHistoryRef.value?.load()
  return result
}

const runAnalysisPipeline = async () => {
  pipelineLoading.value = true
  directionError.value = ''
  priceError.value = ''
  pipelineStages.value = []
  directions.value = null
  priceLevels.value = null
  forecasts.value = null
  strategyOutput.value = null
  pipelineRunId.value = ''
  interpretation.value = null

  const onEvent = (ev) => {
    if (ev.run_id) pipelineRunId.value = ev.run_id
    if (ev.stages?.length) pipelineStages.value = ev.stages
  }

  try {
    await runStream(
      (cb) =>
        analysisApi.runAnalysisStream(
          currentSymbol.value,
          workflowStore.selectedWorkflowId || null,
          workflowStore.selectedStrategyId || null,
          cb
        ),
      onEvent
    )
  } catch (error) {
    directionError.value = `分析失败: ${error.message}`
    try {
      const fallback = await analysisApi.runAnalysis(
        currentSymbol.value,
        workflowStore.selectedWorkflowId || null,
        workflowStore.selectedStrategyId || null
      )
      applyPipelineResult(fallback)
      await fetchResumableCheckpoint()
    } catch {
      /* keep stream error */
    }
  } finally {
    pipelineLoading.value = false
  }
}

const resumeAnalysisPipeline = async () => {
  const runId = resumableCheckpoint.value?.run_id
  if (!runId) return
  pipelineLoading.value = true
  directionError.value = ''
  const onEvent = (ev) => {
    if (ev.run_id) pipelineRunId.value = ev.run_id
    if (ev.stages?.length) pipelineStages.value = ev.stages
  }
  try {
    await runStream((cb) => analysisApi.resumeAnalysisStream(runId, cb), onEvent)
    ElMessage.success('已从断点继续分析')
  } catch (error) {
    directionError.value = `续跑失败: ${error.message}`
    ElMessage.error(directionError.value)
  } finally {
    pipelineLoading.value = false
  }
}

const fetchTechnicalIndicators = async () => {
  indicatorsLoading.value = true
  indicatorsError.value = ''

  try {
    const data = await stockApi.getTechnicalIndicators(currentSymbol.value)
    indicatorsData.value = data
  } catch (error) {
    indicatorsError.value = `获取技术指标失败: ${error.message}`
  } finally {
    indicatorsLoading.value = false
  }
}

const syncBackendStatus = async () => {
  try {
    const data = await stockApi.healthCheck()
    backendStatus.value = data.status
    const ok = data.status === 'healthy'
    backendUnreachable.value = !ok
    return ok
  } catch {
    backendStatus.value = 'error'
    backendUnreachable.value = true
    return false
  }
}

const onBackendRetry = async () => {
  checkingStatus.value = true
  try {
    const ok = await syncBackendStatus()
    if (!ok) {
      ElMessage.error('后端服务仍不可用')
      return
    }
    await Promise.allSettled([workflowStore.fetchWorkflows(), loadStrategies()])
    if (currentSymbol.value) {
      await loadStockData(currentSymbol.value)
    } else {
      await fetchResumableCheckpoint()
    }
    ElMessage.success('已重新连接后端')
  } catch (error) {
    ElMessage.error(`重试失败: ${error.message}`)
  } finally {
    checkingStatus.value = false
  }
}

const onWatchlistSelect = (code) => {
  searchSymbol.value = code
  loadStockData(code)
}

const refreshData = async () => {
  refreshing.value = true
  try {
    await loadStockData(currentSymbol.value)
    ElMessage.success('数据刷新成功')
  } catch (error) {
    ElMessage.error(`刷新失败: ${error.message}`)
  } finally {
    refreshing.value = false
  }
}

const savePlanDraft = async () => {
  if (!planDraft.value) return
  try {
    await plansApi.create(planDraft.value)
    ElMessage.success('成功保存交易计划草稿为正式计划')
    planDraft.value = null
  } catch (error) {
    ElMessage.error(`保存计划失败: ${error.message}`)
  }
}

const exportData = () => {
  if (!currentSymbol.value) {
    ElMessage.warning('请先选择股票')
    return
  }
  const url = stockApi.exportDownloadUrl(currentSymbol.value, 'csv', true)
  const link = document.createElement('a')
  link.href = url
  link.download = `${currentSymbol.value}_ohlcv.csv`
  link.click()
  ElMessage.success('正在下载 OHLCV + 指标 CSV')
}

async function loadStrategies() {
  try {
    const data = await strategyApi.list()
    strategies.value = data.strategies || []
    workflowStore.initFromStorage()
  } catch {
    strategies.value = []
  }
}

onMounted(async () => {
  workflowStore.initFromStorage()
  const healthy = await syncBackendStatus()

  if (healthy) {
    await Promise.allSettled([workflowStore.fetchWorkflows(), loadStrategies()])
  } else {
    workflowStore.applyFallbackWorkflows()
    await loadStrategies()
    ElMessage.warning('后端未连接，请启动 API 服务（默认 http://localhost:8000）')
  }

  const qSymbol = route.query.symbol
  if (qSymbol && typeof qSymbol === 'string') {
    currentSymbol.value = qSymbol
    searchSymbol.value = qSymbol
  }

  if (healthy) {
    const last = await import('@/api/settings.js').then((m) =>
      m.default.get().catch(() => null)
    )
    if (last?.last_symbol) {
      currentSymbol.value = last.last_symbol
      searchSymbol.value = last.last_symbol
    }
    try {
      await loadStockData(currentSymbol.value)
    } catch {
      /* loadStockData 内部已有提示 */
    }
  } else {
    await fetchResumableCheckpoint()
  }
})

watch(currentSymbol, (newVal) => {
  if (newVal) {
    document.title = `${newVal} - 股票分析系统`
  }
})

const handleQualityRetry = async (action) => {
  if (action === 'auto_fetch' || action === 'force_refetch') {
    try {
      pipelineLoading.value = true
      ElMessage.info('正在清除缓存并重新拉取数据...')

      const result = await analysisApi.refetchAndAnalyze(
        currentSymbol.value,
        workflowStore.selectedWorkflowId || null,
        workflowStore.selectedStrategyId || null
      )

      applyPipelineResult(result)
      await fetchResumableCheckpoint()

      if (result.success) {
        ElMessage.success('数据重新拉取成功')
      } else {
        ElMessage.error('数据拉取失败，请检查股票代码或数据源')
      }
    } catch (error) {
      ElMessage.error(`重新拉取数据失败: ${error.message}`)
    } finally {
      pipelineLoading.value = false
    }
  }
}

const handleQualityContinue = () => {
  ElMessage.warning('已忽略质量问题继续分析，结果仅供参考')
}

const handleQualityCancel = () => {
  ElMessage.info('已取消')
}
</script>

<style scoped>
.premium-cockpit {
  max-width: 1400px;
  margin: 0 auto;
}

/* 1. 顶部控制条 */
.top-control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  margin-bottom: 12px;
  gap: 16px;
}

.control-left,
.control-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-input {
  width: 280px;
}

/* 2. 标的信息条 */
.stock-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--rb-border);
}

.stock-info {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.stock-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--rb-text-white);
  margin: 0;
}

.stock-code {
  font-size: 14px;
  color: var(--rb-text-mid);
  font-family: monospace;
}

.stock-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.price-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--rb-text-white);
  font-family: monospace;
}

.price-change {
  font-size: 14px;
  font-weight: 600;
}

.price-change.up {
  color: var(--rb-green);
}

.price-change.down {
  color: var(--rb-red);
}

.update-time {
  font-size: 12px;
  color: var(--rb-text-light);
}

.direction-summary {
  flex-shrink: 0;
}

/* 3. K 线主图 */
.chart-main {
  margin-bottom: 20px;
}

/* 4. 详情 Tab */
.details-section {
  margin-bottom: 20px;
}

.premium-tabs :deep(.el-tabs__header) {
  background: transparent;
  border-bottom: 1px solid var(--rb-border);
  margin-bottom: 0;
}

.premium-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  color: var(--rb-text-mid);
  height: 40px;
  line-height: 40px;
  padding: 0 20px;
}

.premium-tabs :deep(.el-tabs__item:hover) {
  color: var(--rb-text-white);
}

.premium-tabs :deep(.el-tabs__item.is-active) {
  color: var(--rb-text-white);
  font-weight: 600;
}

.tab-content {
  padding: 20px 0;
}

/* 5. 额外信息折叠 */
.extra-info {
  margin-top: 20px;
}

.text-secondary {
  color: var(--rb-text-mid);
  font-size: 13px;
}

.mt-20 {
  margin-top: 20px;
}
</style>
