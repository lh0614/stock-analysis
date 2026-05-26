<template>
  <el-card class="indicators-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span class="rb-card-header-title">
          <el-icon><TrendCharts /></el-icon>
          <span>技术指标</span>
        </span>
      </div>
    </template>

    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在计算技术指标...</span>
    </div>

    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="warning" show-icon :closable="false" />
    </div>

    <div v-else-if="indicatorsData" class="indicators-content">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item
          v-for="(values, key) in indicatorsData.data"
          :key="key"
          :label="key.toUpperCase()"
        >
          <div class="indicator-values">
            <div v-for="(value, subKey) in values" :key="subKey" class="indicator-value">
              <span class="indicator-key">{{ subKey }}:</span>
              <span class="indicator-value-number" :class="getIndicatorClass(key, subKey, value)">
                {{ value }}
              </span>
            </div>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-else class="no-data">
      <el-empty description="暂无技术指标数据" />
    </div>
  </el-card>
</template>

<script setup>
import { Loading, TrendCharts } from '@element-plus/icons-vue'

defineProps({
  indicatorsData: {
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
  }
})

const getIndicatorClass = (indicator, subKey, value) => {
  if (indicator === 'rsi') {
    if (value > 70) return 'overbought'
    if (value < 30) return 'oversold'
  }
  if (indicator === 'macd' && subKey === 'macd') {
    if (value > 0) return 'positive'
    if (value < 0) return 'negative'
  }
  return ''
}
</script>
