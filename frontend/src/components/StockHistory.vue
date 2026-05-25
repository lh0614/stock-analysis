<template>
  <div v-if="symbol" class="history-section">
    <el-card class="history-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>📋 历史数据详情</span>
          <div class="header-actions">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @change="fetchHistoryData"
            />
            <el-button
              type="primary"
              size="small"
              @click="fetchHistoryData"
              :loading="loading"
              :icon="Refresh"
            >
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="loading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在加载历史数据...</span>
      </div>

      <div v-else-if="error" class="error-state">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>

      <div v-else-if="historyData.length > 0" class="history-content">
        <!-- 数据统计 -->
        <div class="data-stats">
          <el-tag type="info">共 {{ historyData.length }} 条数据</el-tag>
          <el-tag type="success">时间范围: {{ formatDate(historyData[0]?.timestamps) }} 至 {{ formatDate(historyData[historyData.length - 1]?.timestamps) }}</el-tag>
          <el-tag v-if="metadata" type="warning">数据源: {{ metadata.data_source }}</el-tag>
        </div>

        <!-- 数据表格 -->
        <el-table
          :data="paginatedData"
          stripe
          border
          size="small"
          max-height="400"
          @sort-change="handleSortChange"
        >
          <el-table-column
            prop="timestamps"
            label="交易日期"
            width="120"
            sortable
            fixed
            :formatter="formatDateCol"
          />
          <el-table-column
            prop="open"
            label="开盘价"
            width="100"
            sortable
            :formatter="formatPriceCol"
          />
          <el-table-column
            prop="high"
            label="最高价"
            width="100"
            sortable
            :formatter="formatPriceCol"
          />
          <el-table-column
            prop="low"
            label="最低价"
            width="100"
            sortable
            :formatter="formatPriceCol"
          />
          <el-table-column
            prop="close"
            label="收盘价"
            width="100"
            sortable
            :formatter="formatPriceCol"
          />
          <el-table-column
            label="涨跌幅"
            width="100"
            :formatter="formatChangeCol"
          />
          <el-table-column
            prop="volume"
            label="成交量"
            width="120"
            sortable
            :formatter="formatVolumeCol"
          />
          <el-table-column
            prop="amount"
            label="成交额"
            width="120"
            sortable
            :formatter="formatAmountCol"
          />
          <el-table-column
            label="换手率"
            width="100"
            :formatter="formatTurnoverCol"
          />
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="historyData.length"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <div v-else class="no-data">
        <el-empty description="暂无历史数据" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Loading, Refresh } from '@element-plus/icons-vue'
import stockApi from '@/api/stock.js'
import { formatLocalDate } from '@/utils/date.js'

const props = defineProps({
  symbol: {
    type: String,
    default: ''
  }
})

// 数据状态
const historyData = ref([])
const metadata = ref(null)
const loading = ref(false)
const error = ref('')

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)

// 日期范围
const dateRange = ref(null)

// 排序状态
const sortProp = ref('')
const sortOrder = ref('')

// 计算分页数据
const paginatedData = computed(() => {
  let data = [...historyData.value]

  // 排序
  if (sortProp.value && sortOrder.value) {
    data.sort((a, b) => {
      const aVal = a[sortProp.value] || 0
      const bVal = b[sortProp.value] || 0
      if (sortOrder.value === 'ascending') {
        return aVal - bVal
      }
      return bVal - aVal
    })
  }

  // 分页
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return data.slice(start, end)
})

// 获取历史数据
const fetchHistoryData = async () => {
  if (!props.symbol) return

  loading.value = true
  error.value = ''

  try {
    let startDate = null
    let endDate = null

    if (dateRange.value && dateRange.value.length === 2) {
      startDate = dateRange.value[0]
      endDate = dateRange.value[1]
    } else {
      // 默认获取最近3个月数据
      const end = new Date()
      const start = new Date()
      start.setMonth(start.getMonth() - 3)
      startDate = formatLocalDate(start)
      endDate = formatLocalDate(end)
    }

    const result = await stockApi.getStockData(props.symbol, startDate, endDate)

    if (result.success) {
      historyData.value = result.data || []
      metadata.value = result.metadata
      currentPage.value = 1
    } else {
      error.value = result.error || '获取数据失败'
    }
  } catch (err) {
    error.value = err.message || '请求失败'
  } finally {
    loading.value = false
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '--'
  return String(dateStr).substring(0, 10)
}

const formatDateCol = (row) => {
  if (!row || !row.timestamps) return '--'
  return String(row.timestamps).substring(0, 10)
}

const formatPriceCol = (row, _col, value) => {
  return value != null ? Number(value).toFixed(2) : '--'
}

const formatChangeCol = (row) => {
  if (!row || row.close == null || row.open == null || row.open === 0) return '--'
  const change = ((row.close - row.open) / row.open) * 100
  const prefix = change >= 0 ? '+' : ''
  return prefix + change.toFixed(2) + '%'
}

const formatVolumeCol = (row, _col, value) => {
  if (!value) return '--'
  if (value >= 100000000) return (value / 100000000).toFixed(2) + '亿'
  if (value >= 10000) return (value / 10000).toFixed(2) + '万'
  return value.toLocaleString()
}

const formatAmountCol = (row, _col, value) => {
  if (!value) return '--'
  if (value >= 100000000) return (value / 100000000).toFixed(2) + '亿'
  if (value >= 10000) return (value / 10000).toFixed(2) + '万'
  return value.toLocaleString()
}

const formatTurnoverCol = (row) => {
  if (!row || row.turnover == null) return '--'
  return row.turnover.toFixed(2) + '%'
}

// 格式化日期
const formatPrice = (price) => {
  return price != null ? Number(price).toFixed(2) : '--'
}

// 格式化成交量
const formatVolume = (volume) => {
  if (!volume) return '--'
  if (volume >= 100000000) {
    return (volume / 100000000).toFixed(2) + '亿'
  } else if (volume >= 10000) {
    return (volume / 10000).toFixed(2) + '万'
  }
  return volume.toLocaleString()
}

// 格式化成交额
const formatAmount = (amount) => {
  if (!amount) return '--'
  if (amount >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (amount >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toLocaleString()
}

// 格式化涨跌幅
const formatChange = (close, open) => {
  if (close == null || open == null || open === 0) return '--'
  const change = ((close - open) / open) * 100
  const prefix = change >= 0 ? '+' : ''
  return prefix + change.toFixed(2) + '%'
}

const getChangeClass = (close, open) => {
  if (close == null || open == null || open === 0) return ''
  return close >= open ? 'change-up' : 'change-down'
}

// 处理排序变化
const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop
  sortOrder.value = order
}

// 处理分页变化
const handlePageChange = (page) => {
  currentPage.value = page
}

// 处理每页条数变化
const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

// 监听股票代码变化
watch(() => props.symbol, () => {
  if (props.symbol) {
    fetchHistoryData()
  }
}, { immediate: true })

// 组件挂载时获取数据
onMounted(() => {
  if (props.symbol) {
    fetchHistoryData()
  }
})
</script>

<style scoped>
.history-section {
  margin-bottom: 30px;
}

.history-card {
  border-radius: 12px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

.loading-state .el-icon {
  font-size: 2rem;
  margin-bottom: 10px;
}

.data-stats {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.history-content {
  padding: 10px 0;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 价格样式 */
.price-up {
  color: #f56c6c;
}

.price-down {
  color: #67c23a;
}

.price-high {
  color: #f56c6c;
  font-weight: 600;
}

.price-low {
  color: #67c23a;
  font-weight: 600;
}

.change-up {
  color: #f56c6c;
  font-weight: 600;
}

.change-down {
  color: #67c23a;
  font-weight: 600;
}

.no-data {
  padding: 40px;
}
</style>
