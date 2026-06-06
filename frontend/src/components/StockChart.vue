<!-- frontend/src/components/StockChart.vue -->
<template>
  <div class="stock-chart">
    <div class="chart-header">
      <span class="chart-title">{{ symbol }} · K 线</span>
      <div class="chart-controls">
        <el-select v-model="period" size="small" @change="fetchData">
          <el-option label="1 个月" value="1m" />
          <el-option label="3 个月" value="3m" />
          <el-option label="6 个月" value="6m" />
          <el-option label="1 年" value="1y" />
          <el-option label="全部" value="all" />
        </el-select>
        <el-select v-model="dataSource" size="small" @change="fetchData">
          <el-option label="自动" value="auto" />
          <el-option label="东方财富" value="eastmoney" />
          <el-option label="AKShare" value="akshare" />
          <el-option label="Baostock" value="baostock" />
        </el-select>
        <el-button size="small" :loading="loading" @click="fetchData">刷新</el-button>
      </div>
    </div>

    <div v-show="loading" class="chart-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载行情中…</span>
    </div>

    <div v-show="!loading && error" class="chart-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>

    <!-- 始终挂载 DOM，避免 v-show 隐藏时 init 导致 cartesian2d 报错 -->
    <div
      v-show="!loading && !error"
      class="chart-wrap"
    >
      <div ref="chartRef" class="chart-canvas"></div>
      <div v-if="metadata" class="chart-meta">
        <span class="meta-tag">数据源 {{ metadata.data_source }}</span>
        <span class="meta-tag">{{ metadata.data_count }} 根 K 线</span>
        <span class="meta-tag">
          {{ metadata.start_date }} ~ {{ metadata.end_date }}
          <template v-if="metadata.last_trade_date">
            · 末根 {{ metadata.last_trade_date }}
          </template>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import stockApi from '@/api/stock.js'
import { formatLocalDate } from '@/utils/date.js'
import { Loading } from '@element-plus/icons-vue'

const UP = '#e54545'
const DOWN = '#17b26a'
const MA_COLORS = { 5: '#f59e0b', 10: '#155eef', 20: '#8b5cf6' }

const props = defineProps({
  symbol: { type: String, required: true, default: '000001' },
  chartPeriod: { type: String, default: '1y' }
})

const chartRef = ref(null)
let chartInstance = null
let resizeHandler = null
let resizeObserver = null

const loading = ref(false)
const error = ref('')
const period = ref('1y')
const dataSource = ref('auto')
const metadata = ref(null)
const stockData = ref([])

const PERIOD_MAP = { '1m': '1m', '3m': '3m', '6m': '6m', '1y': '1y', all: 'all' }

function getDateRange() {
  const endDate = new Date()
  const startDate = new Date()
  switch (period.value) {
    case '1m':
      startDate.setMonth(startDate.getMonth() - 1)
      break
    case '3m':
      startDate.setMonth(startDate.getMonth() - 3)
      break
    case '6m':
      startDate.setMonth(startDate.getMonth() - 6)
      break
    case '1y':
      startDate.setFullYear(startDate.getFullYear() - 1)
      break
    case 'all':
      return { startDate: null, endDate: null }
    default:
      startDate.setFullYear(startDate.getFullYear() - 1)
  }
  return {
    startDate: formatLocalDate(startDate),
    endDate: formatLocalDate(endDate)
  }
}

function calculateMA(dayCount, closes) {
  return closes.map((_, i) => {
    if (i < dayCount - 1) return null
    let sum = 0
    for (let j = 0; j < dayCount; j++) sum += closes[i - j]
    return +(sum / dayCount).toFixed(3)
  })
}

function formatVolume(v) {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`
  return String(Math.round(v))
}

function buildChartOption(rows) {
  const dates = rows.map((item, i) => {
    const t = item.timestamps ?? item.date
    return t ? String(t).slice(0, 10) : `#${i + 1}`
  })
  const ohlc = rows.map((item) => [
    Number(item.open),
    Number(item.close),
    Number(item.low),
    Number(item.high)
  ])
  const closes = rows.map((item) => Number(item.close))
  const volumes = rows.map((item) => Number(item.volume ?? 0))

  const zoomStart = rows.length > 60 ? Math.max(0, 100 - Math.round((60 / rows.length) * 100)) : 0

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 4,
      left: 'center',
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: '#94a3b8', fontSize: 12 },
      data: ['K线', 'MA5', 'MA10', 'MA20', '成交量']
    },
    axisPointer: {
      link: [{ xAxisIndex: [0, 1] }],
      label: { backgroundColor: '#11131c' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 19, 28, 0.95)',
      borderWidth: 1,
      borderColor: '#1e293b',
      padding: [10, 14],
      textStyle: { color: '#f8fafc', fontSize: 12 },
      axisPointer: { type: 'cross', crossStyle: { color: '#64748b' } },
      formatter(params) {
        if (!params?.length) return ''
        const idx = params[0].dataIndex
        const row = rows[idx]
        if (!row) return ''
        const chg = row.close - row.open
        const chgPct = row.open ? ((chg / row.open) * 100).toFixed(2) : '0.00'
        const color = chg >= 0 ? UP : DOWN
        const sign = chg >= 0 ? '+' : ''
        let html = `<div style="font-weight:600;margin-bottom:6px;color:#f8fafc">${dates[idx]}</div>`
        html += `<div>开 <b style="color:#f8fafc">${row.open}</b> 高 <b style="color:#f8fafc">${row.high}</b> 低 <b style="color:#f8fafc">${row.low}</b> 收 <b style="color:${color}">${row.close}</b></div>`
        html += `<div style="color:${color}">涨跌 ${sign}${chg.toFixed(2)} (${sign}${chgPct}%)</div>`
        html += `<div>成交量 <b style="color:#f8fafc">${formatVolume(row.volume ?? 0)}</b></div>`
        params.forEach((p) => {
          if (p.seriesName.startsWith('MA') && p.data != null) {
            html += `<div>${p.marker} ${p.seriesName} <b style="color:#f8fafc">${p.data}</b></div>`
          }
        })
        return html
      }
    },
    grid: [
      { left: 56, right: 20, top: 44, height: '58%', containLabel: false },
      { left: 56, right: 20, top: '74%', height: '14%', containLabel: false }
    ],
    xAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#1e293b' } },
        axisTick: { show: false },
        axisLabel: { color: '#94a3b8', fontSize: 11, margin: 8 },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        splitNumber: 4,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: (v) => Number(v).toFixed(2)
        },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.04)', type: 'dashed' } }
      },
      {
        type: 'value',
        gridIndex: 1,
        scale: true,
        splitNumber: 2,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (v) => formatVolume(v)
        },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: zoomStart,
        end: 100
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 6,
        height: 22,
        start: zoomStart,
        end: 100,
        borderColor: '#1e293b',
        fillerColor: 'rgba(99, 102, 241, 0.08)',
        handleStyle: { color: '#6366f1' },
        textStyle: { color: '#64748b', fontSize: 10 },
        brushSelect: false
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ohlc,
        itemStyle: {
          color: UP,
          color0: DOWN,
          borderColor: UP,
          borderColor0: DOWN,
          borderWidth: 1
        }
      },
      {
        name: 'MA5',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: calculateMA(5, closes),
        symbol: 'none',
        lineStyle: { width: 1.2, color: MA_COLORS[5] },
        smooth: false
      },
      {
        name: 'MA10',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: calculateMA(10, closes),
        symbol: 'none',
        lineStyle: { width: 1.2, color: MA_COLORS[10] },
        smooth: false
      },
      {
        name: 'MA20',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: calculateMA(20, closes),
        symbol: 'none',
        lineStyle: { width: 1.2, color: MA_COLORS[20] },
        smooth: false
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        barMaxWidth: 8,
        itemStyle: {
          color: (params) => {
            const row = rows[params.dataIndex]
            if (!row) return '#c5c8ce'
            return row.close >= row.open ? UP : DOWN
          }
        }
      }
    ]
  }
}

async function renderChart() {
  await nextTick()
  if (!chartRef.value || !stockData.value.length) return

  const w = chartRef.value.clientWidth
  const h = chartRef.value.clientHeight
  if (w < 10 || h < 10) {
    requestAnimationFrame(() => renderChart())
    return
  }

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  chartInstance = echarts.init(chartRef.value, undefined, { renderer: 'canvas' })
  chartInstance.setOption(buildChartOption(stockData.value), { notMerge: true })
  chartInstance.resize()
}

async function fetchData() {
  loading.value = true
  error.value = ''

  try {
    const { startDate, endDate } = getDateRange()
    const source = dataSource.value === 'auto' ? null : dataSource.value
    const response = await stockApi.getStockData(
      props.symbol,
      startDate,
      endDate,
      source
    )

    if (response.success && response.data?.length) {
      stockData.value = response.data
      metadata.value = response.metadata
    } else if (response.success) {
      stockData.value = []
      error.value = '暂无 K 线数据'
    } else {
      stockData.value = []
      error.value = response.error || '获取数据失败'
    }
  } catch (err) {
    stockData.value = []
    error.value = err.response?.data?.detail || err.message || '请求失败'
    console.error('获取股票数据失败:', err)
  } finally {
    loading.value = false
  }

  if (stockData.value.length && !error.value) {
    await renderChart()
  }
}

function bindResize() {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = () => chartInstance?.resize()
  window.addEventListener('resize', resizeHandler)

  if (resizeObserver) resizeObserver.disconnect()
  if (chartRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
  }
}

watch(() => props.symbol, () => fetchData())

watch(
  () => props.chartPeriod,
  (val) => {
    const mapped = PERIOD_MAP[val] || val
    if (mapped && mapped !== period.value) {
      period.value = mapped
      fetchData()
    }
  },
  { immediate: true }
)

onMounted(() => {
  bindResize()
  if (!props.chartPeriod) fetchData()
})

onUnmounted(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.stock-chart {
  width: 100%;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0 12px 0;
  border-bottom: 1px solid var(--rb-border);
  margin-bottom: 16px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--rb-text-white);
}

.chart-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.chart-wrap {
  width: 100%;
}

.chart-canvas {
  width: 100%;
  height: 600px;
}

.chart-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  min-height: 400px;
  color: var(--rb-text-mid);
  font-size: 14px;
}

.chart-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--rb-border);
}

.meta-tag {
  font-size: 12px;
  color: var(--rb-text-mid);
  background: rgba(30, 41, 59, 0.3);
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid var(--rb-border);
}
</style>
