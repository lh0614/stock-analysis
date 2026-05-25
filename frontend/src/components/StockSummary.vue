<template>
  <div v-if="symbol && summaryData" class="summary-section">
    <el-card class="summary-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h3>{{ symbol }} - 股票摘要</h3>
            <span class="stock-name">{{ stockName }}</span>
          </div>
          <div class="header-right">
            <el-button-group>
              <el-button
                v-for="period in periods"
                :key="period.value"
                :type="selectedPeriod === period.value ? 'primary' : ''"
                @click="$emit('change-period', period.value)"
                size="small"
              >
                {{ period.label }}
              </el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <div v-if="loading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在加载股票数据...</span>
      </div>

      <div v-else-if="error" class="error-state">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>

      <div v-else class="summary-content">
        <el-row :gutter="24">
          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">最新价</div>
              <div class="item-value price">
                {{ formatPrice(summaryData.latest_price) }}
              </div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">涨跌额</div>
              <div class="item-value" :class="summaryData.price_change >= 0 ? 'up' : 'down'">
                {{ formatChange(summaryData.price_change) }}
              </div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">涨跌幅</div>
              <div class="item-value" :class="summaryData.price_change_pct >= 0 ? 'up' : 'down'">
                {{ formatChange(summaryData.price_change_pct) }}%
              </div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">数据点数</div>
              <div class="item-value">{{ summaryData.data_points }}</div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="24" class="mt-4">
          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">期间最高</div>
              <div class="item-value">{{ formatPrice(summaryData.high_30d) }}</div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">期间最低</div>
              <div class="item-value">{{ formatPrice(summaryData.low_30d) }}</div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">均成交量</div>
              <div class="item-value">{{ formatNumber(summaryData.avg_volume) }}</div>
            </div>
          </el-col>

          <el-col :span="6">
            <div class="summary-item">
              <div class="item-label">时间范围</div>
              <div class="item-value period">{{ summaryData.period }}</div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { Loading } from '@element-plus/icons-vue'

const periods = [
  { label: '1个月', value: '1m' },
  { label: '3个月', value: '3m' },
  { label: '6个月', value: '6m' },
  { label: '1年', value: '1y' }
]

defineProps({
  symbol: {
    type: String,
    default: ''
  },
  stockName: {
    type: String,
    default: ''
  },
  summaryData: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  selectedPeriod: {
    type: String,
    default: '1m'
  }
})

defineEmits(['change-period'])

const formatPrice = (price) => {
  return price ? price.toFixed(2) : '--'
}

const formatChange = (value) => {
  if (!value) return '--'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const formatNumber = (num) => {
  if (!num) return '--'
  if (num >= 100000000) {
    return (num / 100000000).toFixed(2) + '亿'
  } else if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}
</script>
