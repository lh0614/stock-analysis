<template>
  <div class="rb-page home-view">
    <div class="home-hero">
      <div class="home-hero__text">
        <h1 class="rb-page-title">分析驾驶舱</h1>
        <p class="rb-page-desc">输入标的自动运行流水线，查看短 / 中 / 长线方向与价格结构</p>
      </div>
      <AnalysisToolbar
        v-if="currentSymbol"
        class="home-hero__toolbar"
        v-model:workflow-id="workflowStore.selectedWorkflowId"
        v-model:strategy-id="workflowStore.selectedStrategyId"
        :workflows="workflowStore.workflows"
        :strategies="strategies"
        :loading="pipelineLoading"
        @run="runAnalysisPipeline"
      />
    </div>

    <BackendState
      v-if="showBackendState"
      :type="backendStateType"
      :title="backendStateTitle"
      :description="backendStateDesc"
      :retrying="checkingStatus"
      @retry="onBackendRetry"
    />

    <el-row :gutter="16" class="cockpit-top">
      <el-col :xs="24" :md="6">
        <WatchlistPanel
          ref="watchlistRef"
          :current-symbol="currentSymbol"
          @select="onWatchlistSelect"
        />
      </el-col>
      <el-col :xs="24" :md="18">
        <StockSearch
          v-model:search-symbol="searchSymbol"
          :current-symbol="currentSymbol"
          :search-loading="searchLoading"
          :refreshing="refreshing"
          :example-stocks="exampleStocks"
          @search="handleSearch"
          @show-example="showExample"
          @select-example="selectExample"
          @refresh="refreshData"
        />
      </el-col>
    </el-row>

    <StrategyOutput
      v-if="strategyOutput"
      :output="strategyOutput"
      :strategy-name="strategyName"
    />

    <!-- 分析流水线 -->
    <AnalysisPipeline
      v-if="currentSymbol"
      :stages="pipelineStages"
      :loading="pipelineLoading"
      :run-id="pipelineRunId"
      :checkpoint="resumableCheckpoint"
      @resume="resumeAnalysisPipeline"
    />

    <RunHistory v-if="currentSymbol" ref="runHistoryRef" :symbol="currentSymbol" />

    <InterpretationCard v-if="interpretation" :data="interpretation" />

    <!-- 分析方向 -->
    <DirectionCards
      v-if="currentSymbol"
      :directions="directions"
      :loading="pipelineLoading"
      :error="directionError"
    />

    <!-- 股票摘要信息 -->
    <StockSummary
      :symbol="currentSymbol"
      :stock-name="getStockName(currentSymbol)"
      :summary-data="summaryData"
      :loading="summaryLoading"
      :error="summaryError"
      :selected-period="selectedPeriod"
      @change-period="changePeriod"
    />

    <!-- 主图表区域 -->
    <div v-if="currentSymbol" class="chart-section">
      <StockChart
        :symbol="currentSymbol"
        :chart-period="workflowStore.selectedWorkflow?.chart_period || '1y'"
      />
    </div>

    <NewsTimeline v-if="currentSymbol" :symbol="currentSymbol" />

    <el-row v-if="currentSymbol" :gutter="20" class="analysis-row">
      <el-col :xs="24" :lg="12">
        <PriceLevelsPanel
          :data="priceLevels"
          :loading="pipelineLoading"
          :error="priceError"
        />
      </el-col>
      <el-col :xs="24" :lg="12">
        <ForecastTabs :forecasts="forecasts" :loading="pipelineLoading" />
      </el-col>
    </el-row>

    <!-- 历史数据详情 -->
    <StockHistory :symbol="currentSymbol" />

    <!-- 技术指标和系统状态 -->
    <div v-if="currentSymbol" class="bottom-section">
      <el-row :gutter="20">
        <el-col :xs="24" :lg="12">
          <TechnicalIndicators
            :indicators-data="indicatorsData"
            :loading="indicatorsLoading"
            :error="indicatorsError"
          />
        </el-col>
        <el-col :xs="24" :lg="12">
          <SystemStatus
            :backend-status="backendStatus"
            :current-symbol="currentSymbol"
            :last-update-time="lastUpdateTime"
            :checking-status="checkingStatus"
            @check-status="checkBackendStatus"
            @clear-data="clearData"
            @export-data="exportData"
          />
        </el-col>
      </el-row>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkflowStore } from '@/stores/workflow.js'
import strategyApi from '@/api/strategy.js'

import AnalysisToolbar from '@/components/analysis/AnalysisToolbar.vue'
import StrategyOutput from '@/components/analysis/StrategyOutput.vue'
import StockSearch from '@/components/StockSearch.vue'
import StockSummary from '@/components/StockSummary.vue'
import StockChart from '@/components/StockChart.vue'
import AnalysisPipeline from '@/components/analysis/AnalysisPipeline.vue'
import RunHistory from '@/components/analysis/RunHistory.vue'
import DirectionCards from '@/components/analysis/DirectionCards.vue'
import PriceLevelsPanel from '@/components/analysis/PriceLevelsPanel.vue'
import ForecastTabs from '@/components/analysis/ForecastTabs.vue'
import InterpretationCard from '@/components/analysis/InterpretationCard.vue'
import NewsTimeline from '@/components/analysis/NewsTimeline.vue'
import WatchlistPanel from '@/components/WatchlistPanel.vue'
import analysisApi from '@/api/analysis.js'
import StockHistory from '@/components/StockHistory.vue'
import TechnicalIndicators from '@/components/TechnicalIndicators.vue'
import SystemStatus from '@/components/SystemStatus.vue'
import BackendState from '@/components/common/BackendState.vue'
import stockApi from '@/api/stock.js'
import '@/styles/home.css'

// 响应式数据
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
const route = useRoute()
const workflowStore = useWorkflowStore()
const backendStatus = ref('unknown')
const backendUnreachable = ref(false)
const checkingStatus = ref(false)

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
const selectedPeriod = ref('1m')
const lastUpdateTime = ref('')

// 数据状态
const summaryData = ref(null)
const summaryLoading = ref(false)
const summaryError = ref('')
const indicatorsData = ref(null)
const indicatorsLoading = ref(false)
const indicatorsError = ref('')

// 示例股票列表
const exampleStocks = ref([
  { code: '000001', name: '平安银行', type: 'primary' },
  { code: '002685', name: '华东重机', type: 'primary' },
  { code: '600519', name: '贵州茅台', type: 'success' },
  { code: '000858', name: '五粮液', type: 'warning' },
  { code: '300750', name: '宁德时代', type: 'info' },
  { code: '002594', name: '比亚迪', type: 'danger' },
  { code: '000002', name: '万科A', type: '' },
  { code: '601318', name: '中国平安', type: 'primary' },
  { code: '600036', name: '招商银行', type: 'success' }
])

// 获取股票名称
const getStockName = (code) => {
  const stock = exampleStocks.value.find(s => s.code === code)
  return stock ? stock.name : '未知股票'
}

// 搜索股票
const handleSearch = async () => {
  if (!searchSymbol.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  await loadStockData(searchSymbol.value.trim())
}

// 加载股票数据
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

// 获取股票摘要
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
    directionError.value = ''
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

// 获取技术指标
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

/** 用户手动点击「检查后端连接」时调用 */
const checkBackendStatus = async () => {
  checkingStatus.value = true
  try {
    const ok = await syncBackendStatus()
    if (ok) {
      ElMessage.success('后端服务正常')
    } else {
      ElMessage.error('后端服务不可用')
    }
  } catch (error) {
    ElMessage.error(`检查失败: ${error.message}`)
  } finally {
    checkingStatus.value = false
  }
}

// 显示示例股票
const showExample = () => {
  const randomIndex = Math.floor(Math.random() * exampleStocks.value.length)
  const randomStock = exampleStocks.value[randomIndex]
  searchSymbol.value = randomStock.code
  loadStockData(randomStock.code)
}

const onWatchlistSelect = (code) => {
  searchSymbol.value = code
  loadStockData(code)
}

// 选择示例股票
const selectExample = (code) => {
  searchSymbol.value = code
  loadStockData(code)
}

// 刷新数据
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

// 改变时间周期
const changePeriod = (period) => {
  selectedPeriod.value = period
  ElMessage.info(`切换为 ${period} 周期数据`)
}

// 清除数据
const clearData = () => {
  ElMessageBox.confirm('确定要清除所有数据吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    currentSymbol.value = ''
    summaryData.value = null
    indicatorsData.value = null
    pipelineStages.value = []
    directions.value = null
    priceLevels.value = null
    forecasts.value = null
    searchSymbol.value = ''
    ElMessage.success('数据已清除')
  }).catch(() => {})
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

// 组件挂载时初始化
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

// 监听当前股票变化
watch(currentSymbol, (newVal) => {
  if (newVal) {
    document.title = `${newVal} - 股票分析系统`
  }
})
</script>
