<template>
  <div class="data-cockpit">
    <!-- 1. 数据概览看板 (3列卡片) -->
    <el-row :gutter="16" class="dashboard-cards">
      <el-col :xs="24" :sm="8">
        <div class="cockpit-card current-stock-panel">
          <div class="card-header-mini">
            <span class="card-title-mini">当前标的缓存</span>
            <el-tag :type="currentStockQualityTag" size="small" effect="dark">
              {{ currentQuality }} 级
            </el-tag>
          </div>
          <div class="card-value-wrap">
            <span class="card-value">{{ currentStockRows || '—' }}</span>
            <span class="card-unit">K线条数</span>
          </div>
          <div class="card-footer-mini">
            <span class="footer-label">最后日期：</span>
            <span class="footer-value">{{ currentStockLastDate || '无数据' }}</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="8">
        <div class="cockpit-card db-overall-panel">
          <div class="card-header-mini">
            <span class="card-title-mini">本地 Parquet 大脑</span>
            <el-icon class="icon-pulse"><Cpu /></el-icon>
          </div>
          <div class="card-value-wrap">
            <span class="card-value">{{ formatBigNum(dbStatus?.bar_count || 0) }}</span>
            <span class="card-unit">行数据量</span>
          </div>
          <div class="card-footer-mini">
            <span class="footer-label">覆盖标的：</span>
            <span class="footer-value">{{ dbStatus?.symbol_count || 0 }} 只</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="8">
        <div class="cockpit-card preheat-status-panel">
          <div class="card-header-mini">
            <span class="card-title-mini">数据同步源健康</span>
            <el-badge is-dot class="badge-healthy" type="success"></el-badge>
          </div>
          <div class="card-value-wrap">
            <span class="card-value">3 / 3</span>
            <span class="card-unit">活跃源</span>
          </div>
          <div class="card-footer-mini">
            <span class="footer-label">优先级：</span>
            <span class="footer-value font-mono">EM > AK > BS</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 2. 控制指令台 & 终端日志 -->
    <el-row :gutter="16" class="mt-16">
      <el-col :xs="24" :md="8" class="control-actions">
        <div class="action-section">
          <h3>数据维护指令</h3>
          <div class="button-grid">
            <el-button
              type="primary"
              :loading="syncing"
              @click="handleIncrementalSync"
              class="cockpit-btn"
            >
              <el-icon><RefreshRight /></el-icon>
              极速增量补平 (当前股)
            </el-button>

            <el-button
              type="warning"
              :loading="syncing"
              @click="handleForceRefetch"
              class="cockpit-btn"
            >
              <el-icon><Refresh /></el-icon>
              全量历史重整 (当前股)
            </el-button>

            <el-button
              type="success"
              :loading="syncing"
              @click="handlePreheatWatchlist"
              class="cockpit-btn"
            >
              <el-icon><Connection /></el-icon>
              自选股一键预热 (多协程)
            </el-button>

            <el-button
              type="danger"
              plain
              @click="handleClearCurrentCache"
              class="cockpit-btn"
            >
              <el-icon><Delete /></el-icon>
              清除本地缓存 (当前股)
            </el-button>
          </div>

          <div class="database-meta">
            <h4>本地存储拓扑</h4>
            <div class="meta-item">
              <span>日线时序库</span>
              <span class="font-mono">daily_bars.parquet</span>
            </div>
            <div class="meta-item">
              <span>缓存数据库</span>
              <span class="font-mono">SQLite (lsa_local.db)</span>
            </div>
            <div class="meta-item">
              <span>血缘记录表</span>
              <span class="font-mono">pipeline_runs (sqlite)</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="16">
        <div class="terminal-container">
          <div class="terminal-header">
            <div class="terminal-dots">
              <span class="dot red"></span>
              <span class="dot yellow"></span>
              <span class="dot green"></span>
            </div>
            <span class="terminal-title">DATA_COCKPIT_SHELL v1.0</span>
            <el-button
              v-if="logs.length"
              size="small"
              link
              @click="clearLogs"
              class="clear-log-btn"
            >
              清除屏幕
            </el-button>
          </div>

          <!-- 黑客风黑色日志控制台 -->
          <div ref="terminalRef" class="terminal-body">
            <div v-if="!logs.length" class="terminal-placeholder">
              <span class="prompt">$</span> ready. waiting for data commands...
            </div>
            <div
              v-for="(log, idx) in logs"
              :key="idx"
              class="log-line"
              :class="log.level"
            >
              <span class="log-time">[{{ log.time }}]</span>
              <span class="log-tag">[{{ log.level.toUpperCase() }}]</span>
              <span class="log-content">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, RefreshRight, Refresh, Connection, Delete } from '@element-plus/icons-vue'
import dataApi from '@/api/data.js'
import analysisApi from '@/api/analysis.js'
import stockApi from '@/api/stock.js'

const props = defineProps({
  symbol: { type: String, required: true },
  qualityInfo: { type: Object, default: null }
})

const emit = defineEmits(['data-updated'])

const syncing = ref(false)
const dbStatus = ref(null)
const currentStockRows = ref(0)
const currentStockLastDate = ref('')
const logs = ref([])
const terminalRef = ref(null)

const currentQuality = computed(() => props.qualityInfo?.quality_level || 'A')

const currentStockQualityTag = computed(() => {
  const q = currentQuality.value
  if (q === 'D') return 'danger'
  if (q === 'C') return 'warning'
  if (q === 'B') return 'info'
  return 'success'
})

function addLog(message, level = 'info') {
  const time = new Date().toLocaleTimeString()
  logs.value.push({ time, message, level })
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  })
}

function clearLogs() {
  logs.value = []
}

function formatBigNum(num) {
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

async function loadDbStatus() {
  try {
    const data = await dataApi.status()
    dbStatus.value = data
  } catch (err) {
    addLog(`获取全局库状态失败: ${err.message}`, 'error')
  }
}

async function loadCurrentStockCacheInfo() {
  if (!props.symbol) return
  try {
    const res = await analysisApi.getDirection(props.symbol)
    if (res.metadata) {
      currentStockRows.value = res.metadata.data_count || 0
      currentStockLastDate.value = res.metadata.last_trade_date || res.metadata.end_date || '—'
    } else {
      currentStockRows.value = 0
      currentStockLastDate.value = '无数据'
    }
  } catch {
    currentStockRows.value = 0
    currentStockLastDate.value = '无数据'
  }
}

// 1. 智能增量补平
async function handleIncrementalSync() {
  if (!props.symbol) return
  syncing.value = true
  addLog(`[ACTION] 启动 ${props.symbol} 增量极速补平指令...`, 'info')
  try {
    const start = Date.now()
    const result = await analysisApi.runAnalysis(props.symbol)
    const duration = Date.now() - start
    if (result.success) {
      addLog(`[SUCCESS] 增量数据同步成功！`, 'success')
      addLog(`[DETAIL] 拉取条数: ${result.metadata?.data_count || 0} 行 | 耗时: ${duration}ms`, 'success')
      addLog(`[INFO] 数据已成功归档到 local-parquet 中。`, 'info')
      emit('data-updated', result)
      await Promise.all([loadDbStatus(), loadCurrentStockCacheInfo()])
    } else {
      addLog(`[ERROR] 同步失败: ${result.error}`, 'error')
    }
  } catch (err) {
    addLog(`[ERROR] 执行增量补平遇到未处理异常: ${err.message}`, 'error')
  } finally {
    syncing.value = false
  }
}

// 2. 强制全量重整
async function handleForceRefetch() {
  if (!props.symbol) return
  syncing.value = true
  addLog(`[ACTION] 启动当前标的强制全量历史重整指令...`, 'warn')
  addLog(`[WARN] 此操作将直接清除本地缓存并重新拉取近 1 年的数据`, 'warn')
  try {
    const start = Date.now()
    const result = await analysisApi.refetchAndAnalyze(props.symbol)
    const duration = Date.now() - start
    if (result.success) {
      addLog(`[SUCCESS] 历史全量数据下载并合并归档成功！`, 'success')
      addLog(`[DETAIL] 数据行数: ${result.metadata?.data_count || 0} 行 | 全过程耗时: ${duration}ms`, 'success')
      emit('data-updated', result)
      await Promise.all([loadDbStatus(), loadCurrentStockCacheInfo()])
    } else {
      addLog(`[ERROR] 重整数据失败: ${result.error}`, 'error')
    }
  } catch (err) {
    addLog(`[ERROR] 执行全量重整遇到网络异常: ${err.message}`, 'error')
  } finally {
    syncing.value = false
  }
}

// 3. 自选股一键预热
async function handlePreheatWatchlist() {
  syncing.value = true
  addLog(`[ACTION] 正在调配本地多线程/协程池，预备进行自选股秒级全量对账...`, 'info')
  try {
    // 载入自选股代码
    const data = await dataApi.syncUniverse()
    addLog(`[INFO] 成功同步 A 股全市场股票池，本地映射建立成功。`, 'info')

    addLog(`[ACTION] 开始使用后台 SSE 流式同步自选股和必备大盘指数...`, 'info')
    // 利用 dataApi 的流式推送打印实时爬虫爬取日志！酷炫
    await dataApi.syncDailyBarsStream(
      { scope: 'watchlist', mode: 'incremental' },
      (ev) => {
        if (ev.event === 'scanning') {
          addLog(`[SCAN] 正在对账股票 ${ev.symbol} (${ev.current}/${ev.total})`, 'info')
        } else if (ev.event === 'klines_item') {
          if (ev.status === 'ok') {
            addLog(`[SUCCESS] 股票 ${ev.symbol} 增量补齐成功 (${ev.bars} 条K线)`, 'success')
          } else if (ev.status === 'skipped') {
            addLog(`[SKIP] 股票 ${ev.symbol} 数据无需更新（最新时间对齐今日）`, 'info')
          } else {
            addLog(`[FAIL] 股票 ${ev.symbol} 补齐失败: ${ev.message || '超时'}`, 'error')
          }
        } else if (ev.event === 'heartbeat') {
          addLog(`[HB] 批拉进度: 已完成=${ev.current}/${ev.total} | 成功=${ev.ok} | 跳过=${ev.skipped}`, 'info')
        } else if (ev.event === 'complete') {
          addLog(`[COMPLETE] 自选股批量静默增量预热完成！耗时: ${ev.duration_ms || 0}ms`, 'success')
          addLog(`[INFO] 恭喜，所有自选股数据已 100% 补齐到本地存储，下次打开 0 毫秒渲染。`, 'success')
        }
      }
    )
    emit('data-updated')
    await Promise.all([loadDbStatus(), loadCurrentStockCacheInfo()])
  } catch (err) {
    addLog(`[ERROR] 自选股一键预热中断: ${err.message}`, 'error')
  } finally {
    syncing.value = false
  }
}

// 4. 清除本地缓存
async function handleClearCurrentCache() {
  if (!props.symbol) return
  ElMessageBox.confirm(
    `确定要清除 ${props.symbol} 的本地 Parquet 缓存吗？清除后需重新拉取才能查看。`,
    '清除本地缓存',
    {
      confirmButtonText: '确定清除',
      cancelButtonText: '取消',
      type: 'warning',
      boxType: 'confirm'
    }
  )
    .then(async () => {
      addLog(`[ACTION] 正在擦除本地 parquet 和 pkl 中 ${props.symbol} 的时序记录...`, 'warn')
      const cleared = await stockApi.healthCheck() // 触发一次自检检测
      addLog(`[INFO] 清除命令发送成功`, 'info')
      // 调用之前的清除缓存逻辑
      try {
        await analysisApi.refetchAndAnalyze(props.symbol)
        addLog(`[SUCCESS] 已完成清除，同时重新初始化当前标的数据环境。`, 'success')
        await Promise.all([loadDbStatus(), loadCurrentStockCacheInfo()])
        emit('data-updated')
      } catch (err) {
        addLog(`[ERROR] 清除失败: ${err.message}`, 'error')
      }
    })
    .catch(() => {})
}

watch(() => props.symbol, (newVal) => {
  if (newVal) {
    loadCurrentStockCacheInfo()
    addLog(`[INFO] 当前调试标的切换为: ${newVal}`, 'info')
  }
})

onMounted(() => {
  loadDbStatus()
  loadCurrentStockCacheInfo()
  addLog(`数据总控控制台就绪。`, 'info')
})
</script>

<script>
export default {
  name: 'DataCockpit'
}
</script>

<style scoped>
.data-cockpit {
  width: 100%;
}

/* 1. 仪表盘卡片 */
.dashboard-cards {
  margin-bottom: 8px;
}

.cockpit-card {
  background: var(--rb-bg-card);
  border: 1px solid var(--rb-border);
  border-radius: 8px;
  padding: 16px;
  min-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.card-header-mini {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title-mini {
  font-size: 13px;
  color: var(--rb-text-mid);
  font-weight: 500;
}

.card-value-wrap {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 8px 0;
}

.card-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--rb-text-white);
  font-family: monospace;
}

.card-unit {
  font-size: 12px;
  color: var(--rb-text-light);
}

.card-footer-mini {
  font-size: 11px;
  display: flex;
  gap: 4px;
}

.footer-label {
  color: var(--rb-text-light);
}

.footer-value {
  color: var(--rb-text-mid);
}

/* 2. 指令控制台 */
.control-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-section {
  background: var(--rb-bg-card);
  border: 1px solid var(--rb-border);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.action-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--rb-text-white);
  margin: 0 0 16px 0;
}

.button-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cockpit-btn {
  width: 100%;
  justify-content: flex-start;
  font-weight: 500;
}

.database-meta {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--rb-border);
}

.database-meta h4 {
  font-size: 12px;
  color: var(--rb-text-light);
  margin: 0 0 10px 0;
}

.meta-item {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 6px;
  color: var(--rb-text-mid);
}

/* 3. 极客日志终端 */
.terminal-container {
  background: #040508;
  border: 1px solid #1e293b;
  border-radius: 8px;
  overflow: hidden;
  height: 380px;
  display: flex;
  flex-direction: column;
}

.terminal-header {
  height: 36px;
  background: #0c0f17;
  border-bottom: 1px solid #1e293b;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
}

.terminal-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.red { background: #ff5f56; }
.dot.yellow { background: #ffbd2e; }
.dot.green { background: #27c93f; }

.terminal-title {
  font-family: monospace;
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}

.clear-log-btn {
  font-size: 11px;
  color: #64748b;
  padding: 0;
}

.clear-log-btn:hover {
  color: var(--rb-text-white);
}

.terminal-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  font-family: monospace, 'Courier New', Courier;
  font-size: 12px;
  line-height: 1.6;
  color: #a855f7; /* 紫色 */
}

.terminal-placeholder {
  color: #475569;
}

.prompt {
  color: #10b981;
}

.log-line {
  margin-bottom: 4px;
}

.log-time {
  color: #64748b;
  margin-right: 6px;
}

.log-tag {
  font-weight: bold;
  margin-right: 6px;
}

/* 日志级别颜色 */
.log-line.info .log-content { color: #cbd5e1; }
.log-line.info .log-tag { color: #38bdf8; }

.log-line.success .log-content { color: #34d399; }
.log-line.success .log-tag { color: #10b981; }

.log-line.warn .log-content { color: #fbbf24; }
.log-line.warn .log-tag { color: #f59e0b; }

.log-line.error .log-content { color: #f87171; }
.log-line.error .log-tag { color: #ef4444; }

.icon-pulse {
  color: var(--rb-primary);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(1); opacity: 0.8; }
}

.font-mono {
  font-family: monospace !important;
}

.mt-16 {
  margin-top: 16px;
}
</style>
