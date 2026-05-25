<template>
  <div v-if="symbol" class="chart-section">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>📊 K线图分析 - {{ symbol }}</span>
            </div>
          </template>

          <div v-if="loading" class="loading-state">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在加载图表数据...</span>
          </div>

          <div v-else-if="error" class="error-state">
            <el-alert :title="error" type="error" show-icon :closable="false" />
          </div>

          <div v-else class="chart-container">
            <slot>
              <div class="placeholder-chart">
                <div class="placeholder-header">
                  <h4>股票K线图（集成中）</h4>
                  <p>这里将显示完整的K线图、成交量和技术指标</p>
                </div>
                <div class="chart-controls">
                  <el-select v-model="chartType" placeholder="选择图表类型" size="small">
                    <el-option label="K线图" value="candle"></el-option>
                    <el-option label="折线图" value="line"></el-option>
                    <el-option label="面积图" value="area"></el-option>
                  </el-select>

                  <el-select v-model="indicatorType" placeholder="选择技术指标" size="small">
                    <el-option label="MACD" value="macd"></el-option>
                    <el-option label="RSI" value="rsi"></el-option>
                    <el-option label="KDJ" value="kdj"></el-option>
                    <el-option label="布林带" value="boll"></el-option>
                  </el-select>
                </div>
                <div class="chart-placeholder">
                  <div class="chart-grid">
                    <div class="price-level" v-for="i in 5" :key="i"></div>
                  </div>
                  <div class="price-line"></div>
                  <div class="volume-bars">
                    <div
                      v-for="i in 20"
                      :key="i"
                      class="volume-bar"
                      :style="{ height: Math.random() * 100 + 'px' }"
                    ></div>
                  </div>
                </div>
              </div>
            </slot>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Loading } from '@element-plus/icons-vue'

defineProps({
  symbol: {
    type: String,
    default: ''
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

const chartType = ref('candle')
const indicatorType = ref('macd')
</script>

<style scoped>
.placeholder-chart {
  padding: 20px;
}

.placeholder-header {
  text-align: center;
  margin-bottom: 20px;
}

.placeholder-header h4 {
  margin: 0 0 8px 0;
  color: #303133;
}

.placeholder-header p {
  margin: 0;
  color: #909399;
  font-size: 0.9rem;
}

.chart-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  justify-content: center;
}

.chart-placeholder {
  position: relative;
  height: 300px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.chart-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.price-level {
  height: 1px;
  background: #e4e7ed;
  margin: 0 20px;
}

.price-line {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #409eff, transparent);
  opacity: 0.3;
}

.volume-bars {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 100px;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  padding: 0 20px;
}

.volume-bar {
  width: 20px;
  background: #67c23a;
  opacity: 0.6;
  border-radius: 2px 2px 0 0;
  transition: height 0.3s ease;
}
</style>
