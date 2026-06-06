<template>
  <div class="stock-deep-analysis">
    <el-card class="header-card">
      <div class="page-header">
        <h2>单股深度分析</h2>
        <p class="subtitle">多维度精准分析与预测</p>
      </div>
    </el-card>

    <!-- 输入区 -->
    <el-card class="input-card">
      <el-form :inline="true" @submit.prevent="runAnalysis">
        <el-form-item label="股票代码">
          <el-input
            v-model="inputSymbol"
            placeholder="输入股票代码，如 600519"
            style="width: 300px"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runAnalysis" :loading="loading">
            <el-icon><Search /></el-icon>
            深度分析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 结果展示 -->
    <div v-if="result" class="result-section">
      <!-- 核心结论卡片 -->
      <el-card class="verdict-card">
        <div class="verdict-header">
          <div class="stock-title">
            <h3>{{ result.name || result.symbol }}</h3>
            <el-tag size="large">{{ result.symbol }}</el-tag>
          </div>
          <div class="verdict-badge">
            <el-tag :type="getVerdictType(result.verdict)" size="large" effect="dark">
              {{ getVerdictText(result.verdict) }}
            </el-tag>
          </div>
        </div>

        <el-row :gutter="20" class="verdict-metrics">
          <el-col :span="6">
            <div class="metric-item">
              <div class="metric-label">周期</div>
              <div class="metric-value">{{ getHorizonText(result.horizon) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="metric-item">
              <div class="metric-label">置信度</div>
              <div class="metric-value">{{ (result.confidence * 100).toFixed(1) }}%</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="metric-item">
              <div class="metric-label">胜率估计</div>
              <div class="metric-value">
                {{ result.win_rate_estimate ? (result.win_rate_estimate * 100).toFixed(1) + '%' : 'N/A' }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="metric-item">
              <div class="metric-label">风险收益比</div>
              <div class="metric-value">
                {{ result.risk_reward_ratio ? result.risk_reward_ratio.toFixed(2) : 'N/A' }}
              </div>
            </div>
          </el-col>
        </el-row>

        <div v-if="result.expected_return_range && Object.keys(result.expected_return_range).length" class="return-range">
          <h4>预期收益区间</h4>
          <el-row :gutter="16">
            <el-col :span="8">
              <div class="range-item conservative">
                <div class="range-label">保守</div>
                <div class="range-value">{{ (result.expected_return_range.low * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="range-item base">
                <div class="range-label">基准</div>
                <div class="range-value">{{ (result.expected_return_range.base * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="range-item aggressive">
                <div class="range-label">进取</div>
                <div class="range-value">{{ (result.expected_return_range.high * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
          </el-row>
        </div>
      </el-card>

      <!-- 风险提示 -->
      <el-card v-if="result.risks && result.risks.length" class="risks-card">
        <template #header>
          <div class="card-header">
            <el-icon><WarningFilled /></el-icon>
            <span>风险提示</span>
          </div>
        </template>
        <div class="risk-list">
          <el-alert
            v-for="(risk, idx) in result.risks"
            :key="idx"
            :type="getRiskAlertType(risk.level)"
            :closable="false"
            show-icon
          >
            <template #title>
              <strong>{{ risk.type }}</strong> - {{ risk.message }}
            </template>
          </el-alert>
        </div>
      </el-card>

      <!-- 触发条件 -->
      <el-card class="conditions-card">
        <template #header>
          <div class="card-header">
            <el-icon><Flag /></el-icon>
            <span>触发条件</span>
          </div>
        </template>
        <el-table :data="result.trigger_conditions" style="width: 100%">
          <el-table-column prop="condition" label="条件" />
          <el-table-column prop="current_status" label="当前状态" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.is_met ? 'success' : 'info'" size="small">
                {{ scope.row.is_met ? '已满足' : '待确认' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 失效条件 -->
      <el-card class="conditions-card">
        <template #header>
          <div class="card-header">
            <el-icon><Close /></el-icon>
            <span>失效条件</span>
          </div>
        </template>
        <el-table :data="result.invalid_conditions" style="width: 100%">
          <el-table-column prop="condition" label="条件" />
          <el-table-column prop="threshold" label="阈值" />
        </el-table>
      </el-card>

      <!-- 目标区间 -->
      <el-card v-if="result.target_zones && result.target_zones.length" class="targets-card">
        <template #header>
          <div class="card-header">
            <el-icon><TrendCharts /></el-icon>
            <span>目标区间</span>
          </div>
        </template>
        <el-table :data="result.target_zones" style="width: 100%">
          <el-table-column label="级别" width="120">
            <template #default="scope">
              <el-tag :type="getTargetLevelType(scope.row.level)">
                {{ getTargetLevelText(scope.row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="目标价" />
          <el-table-column label="收益率">
            <template #default="scope">
              {{ (scope.row.return_pct * 100).toFixed(2) }}%
            </template>
          </el-table-column>
          <el-table-column label="概率">
            <template #default="scope">
              {{ (scope.row.probability * 100).toFixed(1) }}%
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 证据链 -->
      <el-card class="evidence-card">
        <template #header>
          <div class="card-header">
            <el-icon><Document /></el-icon>
            <span>证据链</span>
          </div>
        </template>
        <el-collapse>
          <el-collapse-item
            v-for="dimension in groupedEvidence"
            :key="dimension.name"
            :title="`${dimension.name} (${dimension.items.length})`"
          >
            <div class="evidence-list">
              <div
                v-for="(item, idx) in dimension.items"
                :key="idx"
                class="evidence-item"
                :class="{ positive: item.weight > 0, negative: item.weight < 0 }"
              >
                <div class="evidence-header">
                  <span class="evidence-factor">{{ item.factor }}</span>
                  <el-tag size="small" :type="item.weight > 0 ? 'success' : 'danger'">
                    权重: {{ item.weight.toFixed(1) }}
                  </el-tag>
                </div>
                <div class="evidence-value">值: {{ formatValue(item.value) }}</div>
                <div class="evidence-interpretation">{{ item.interpretation }}</div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 矛盾点 -->
      <el-card v-if="result.contradictions && result.contradictions.length" class="contradictions-card">
        <template #header>
          <div class="card-header">
            <el-icon><Warning /></el-icon>
            <span>矛盾点</span>
          </div>
        </template>
        <ul class="contradiction-list">
          <li v-for="(item, idx) in result.contradictions" :key="idx">{{ item }}</li>
        </ul>
      </el-card>

      <!-- 数据质量 -->
      <el-card class="quality-card">
        <template #header>
          <div class="card-header">
            <el-icon><DataAnalysis /></el-icon>
            <span>数据质量</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="质量等级">
            <el-tag :type="getQualityType(result.data_quality.quality_level)">
              {{ result.data_quality.quality_level }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据完整性">
            {{ result.data_quality.completeness_score?.toFixed(2) || 'N/A' }}
          </el-descriptions-item>
          <el-descriptions-item label="最后更新">
            {{ result.data_quality.last_update || 'N/A' }}
          </el-descriptions-item>
          <el-descriptions-item label="分析日期">
            {{ result.analysis_date }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="输入股票代码开始分析" :image-size="200" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, WarningFilled, Flag, Close, TrendCharts, Document, Warning, DataAnalysis } from '@element-plus/icons-vue'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const inputSymbol = ref('')
const loading = ref(false)
const result = ref<any>(null)

const runAnalysis = async () => {
  if (!inputSymbol.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }

  loading.value = true
  result.value = null

  try {
    const response = await axios.post(`${API_BASE}/stock-analysis/deep-run`, {
      symbol: inputSymbol.value.trim()
    })
    result.value = response.data.result
    ElMessage.success('分析完成')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '分析失败')
  } finally {
    loading.value = false
  }
}

const groupedEvidence = computed(() => {
  if (!result.value?.evidence) return []
  const groups = new Map<string, any[]>()

  result.value.evidence.forEach((item: any) => {
    if (!groups.has(item.dimension)) {
      groups.set(item.dimension, [])
    }
    groups.get(item.dimension)!.push(item)
  })

  return Array.from(groups.entries()).map(([name, items]) => ({
    name,
    items
  }))
})

const getVerdictType = (verdict: string) => {
  const map: Record<string, any> = {
    actionable: 'success',
    watch: 'warning',
    avoid: 'danger',
    insufficient_data: 'info'
  }
  return map[verdict] || 'info'
}

const getVerdictText = (verdict: string) => {
  const map: Record<string, string> = {
    actionable: '可关注',
    watch: '观察',
    avoid: '回避',
    insufficient_data: '数据不足'
  }
  return map[verdict] || verdict
}

const getHorizonText = (horizon: string) => {
  const map: Record<string, string> = {
    short: '短线 (1-2周)',
    medium: '中线 (1-2月)',
    long: '长线 (3月+)',
    unknown: '未知'
  }
  return map[horizon] || horizon
}

const getRiskAlertType = (level: string) => {
  const map: Record<string, any> = {
    high: 'error',
    medium: 'warning',
    low: 'info'
  }
  return map[level] || 'info'
}

const getTargetLevelType = (level: string) => {
  const map: Record<string, any> = {
    conservative: 'info',
    base: 'primary',
    aggressive: 'warning'
  }
  return map[level] || 'info'
}

const getTargetLevelText = (level: string) => {
  const map: Record<string, string> = {
    conservative: '保守',
    base: '基准',
    aggressive: '进取'
  }
  return map[level] || level
}

const getQualityType = (level: string) => {
  const map: Record<string, any> = {
    A: 'success',
    B: 'primary',
    C: 'warning',
    D: 'danger'
  }
  return map[level] || 'info'
}

const formatValue = (value: any) => {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return value.toFixed(4)
  return String(value)
}
</script>

<style scoped>
.stock-deep-analysis {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.input-card {
  margin-bottom: 20px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.verdict-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.verdict-card :deep(.el-card__body) {
  padding: 24px;
}

.verdict-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.stock-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stock-title h3 {
  margin: 0;
  font-size: 24px;
  color: white;
}

.verdict-badge :deep(.el-tag) {
  font-size: 16px;
  padding: 8px 16px;
}

.verdict-metrics {
  margin-bottom: 24px;
}

.metric-item {
  text-align: center;
  padding: 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.metric-label {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
}

.return-range h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  opacity: 0.9;
}

.range-item {
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
}

.range-label {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 8px;
}

.range-value {
  font-size: 20px;
  font-weight: bold;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evidence-item {
  padding: 16px;
  border-radius: 8px;
  background: #f5f7fa;
  border-left: 4px solid #dcdfe6;
}

.evidence-item.positive {
  background: #f0f9ff;
  border-left-color: #67c23a;
}

.evidence-item.negative {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.evidence-factor {
  font-weight: 600;
  color: #303133;
}

.evidence-value {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.evidence-interpretation {
  color: #606266;
  line-height: 1.6;
}

.contradiction-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.contradiction-list li {
  padding: 12px;
  margin-bottom: 8px;
  background: #fff7e6;
  border-left: 4px solid #e6a23c;
  border-radius: 4px;
}

.contradiction-list li:last-child {
  margin-bottom: 0;
}
</style>
