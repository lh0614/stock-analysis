<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">P2 预测与风控</h1>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="单股预测" name="prediction">
        <el-card shadow="never" class="section-card">
          <el-form inline>
            <el-form-item label="股票代码">
              <el-input v-model="predictionForm.symbol" placeholder="600519" style="width: 160px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="predicting" @click="predict">预测</el-button>
              <el-button :loading="training" @click="train">训练基础模型</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            v-if="modelInfo?.status === 'no_model'"
            title="暂无可用模型，请先训练。训练会使用本地历史行情和因子数据。"
            type="warning"
            :closable="false"
            show-icon
          />
          <el-descriptions v-else-if="modelInfo?.status === 'available'" :column="4" size="small" border>
            <el-descriptions-item label="模型">{{ modelInfo.model_type }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ modelInfo.model_version }}</el-descriptions-item>
            <el-descriptions-item label="周期">{{ modelInfo.target_horizon }} 日</el-descriptions-item>
            <el-descriptions-item label="特征数">{{ modelInfo.feature_count }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="modelMetrics?.status === 'success'" class="metrics-panel">
            <div class="metrics-header">
              <span>模型评估</span>
              <el-tag size="small" effect="plain">{{ modelMetrics.target_horizon }}</el-tag>
            </div>
            <div class="metrics-grid">
              <div class="metric-block">
                <div class="metric-title">训练集</div>
                <div class="metric-row">
                  <span>准确率</span>
                  <strong>{{ formatPercent(modelMetrics.training_metrics?.accuracy) }}</strong>
                </div>
                <div class="metric-row">
                  <span>精确率</span>
                  <strong>{{ formatPercent(modelMetrics.training_metrics?.precision) }}</strong>
                </div>
                <div class="metric-row">
                  <span>召回率</span>
                  <strong>{{ formatPercent(modelMetrics.training_metrics?.recall) }}</strong>
                </div>
                <div class="metric-row">
                  <span>AUC</span>
                  <strong>{{ formatDecimal(modelMetrics.training_metrics?.auc) }}</strong>
                </div>
              </div>
              <div class="metric-block">
                <div class="metric-title">测试集</div>
                <div class="metric-row">
                  <span>准确率</span>
                  <strong>{{ formatPercent(modelMetrics.test_metrics?.accuracy) }}</strong>
                </div>
                <div class="metric-row">
                  <span>精确率</span>
                  <strong>{{ formatPercent(modelMetrics.test_metrics?.precision) }}</strong>
                </div>
                <div class="metric-row">
                  <span>召回率</span>
                  <strong>{{ formatPercent(modelMetrics.test_metrics?.recall) }}</strong>
                </div>
                <div class="metric-row">
                  <span>AUC</span>
                  <strong>{{ formatDecimal(modelMetrics.test_metrics?.auc) }}</strong>
                </div>
              </div>
              <div class="metric-block">
                <div class="metric-title">样本分布</div>
                <div class="metric-row">
                  <span>训练样本</span>
                  <strong>{{ modelMetrics.sample_info?.train_samples || 0 }}</strong>
                </div>
                <div class="metric-row">
                  <span>测试样本</span>
                  <strong>{{ modelMetrics.sample_info?.test_samples || 0 }}</strong>
                </div>
                <div class="metric-row">
                  <span>训练正例</span>
                  <strong>{{ formatPercent(modelMetrics.sample_info?.positive_ratio_train) }}</strong>
                </div>
                <div class="metric-row">
                  <span>测试正例</span>
                  <strong>{{ formatPercent(modelMetrics.sample_info?.positive_ratio_test) }}</strong>
                </div>
              </div>
            </div>
            <el-alert
              v-if="modelMetrics.limitations?.length"
              :title="modelMetrics.limitations.join('；')"
              type="info"
              :closable="false"
              show-icon
              class="metrics-note"
            />
          </div>
        </el-card>
        <StockPredictionCard :prediction="predictionResult" show-model-info />
      </el-tab-pane>

      <el-tab-pane label="市场适配" name="environment">
        <el-card shadow="never" class="section-card">
          <el-form inline>
            <el-form-item label="策略ID">
              <el-input v-model="strategyId" placeholder="策略库 ID" style="width: 280px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loadingFit" @click="loadFit">检查适配</el-button>
              <el-button @click="loadMarket">当前市场</el-button>
            </el-form-item>
          </el-form>
          <el-descriptions v-if="marketState" :column="3" size="small" border>
            <el-descriptions-item label="市场状态">{{ marketState.state }}</el-descriptions-item>
            <el-descriptions-item label="趋势">{{ marketState.trend }}</el-descriptions-item>
            <el-descriptions-item label="波动">{{ marketState.volatility_level }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <StrategyEnvironmentCard :environment-data="environmentResult" show-details />
      </el-tab-pane>

      <el-tab-pane label="组合风控" name="portfolio">
        <el-card shadow="never" class="section-card">
          <el-form inline>
            <el-form-item label="策略ID列表">
              <el-input
                v-model="portfolioForm.strategy_ids"
                placeholder="逗号分隔；留空使用全部活跃策略"
                style="width: 360px"
              />
            </el-form-item>
            <el-form-item label="最大持仓">
              <el-input-number v-model="portfolioForm.max_positions" :min="1" :max="50" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loadingPortfolio" @click="loadPortfolioRisk">生成报告</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <PortfolioRiskCard :risk-data="portfolioRisk" show-details />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'
import StockPredictionCard from '@/components/StockPredictionCard.vue'
import StrategyEnvironmentCard from '@/components/StrategyEnvironmentCard.vue'
import PortfolioRiskCard from '@/components/PortfolioRiskCard.vue'
import p2Api from '@/api/p2.js'

const activeTab = ref('prediction')
const predictionForm = ref({ symbol: '000001' })
const predictionResult = ref(null)
const modelInfo = ref(null)
const modelMetrics = ref(null)
const predicting = ref(false)
const training = ref(false)
const strategyId = ref('')
const loadingFit = ref(false)
const marketState = ref(null)
const environmentResult = ref(null)
const portfolioForm = ref({ strategy_ids: '', max_positions: 10 })
const loadingPortfolio = ref(false)
const portfolioRisk = ref(null)

async function loadModelInfo() {
  modelInfo.value = await p2Api.predictionModelInfo()
  if (modelInfo.value?.status === 'available') {
    await loadModelMetrics()
  } else {
    modelMetrics.value = null
  }
}

async function loadModelMetrics() {
  try {
    modelMetrics.value = await p2Api.predictionModelMetrics()
  } catch {
    modelMetrics.value = null
  }
}

async function train() {
  training.value = true
  try {
    const res = await p2Api.trainPrediction({
      model_type: 'logistic',
      target_horizon: 20,
      prediction_threshold: 0.05,
      symbols: predictionForm.value.symbol ? [predictionForm.value.symbol] : null
    })
    ElMessage.success(`模型训练完成：${res.model_version}`)
    await loadModelInfo()
  } finally {
    training.value = false
  }
}

async function predict() {
  predicting.value = true
  try {
    predictionResult.value = await p2Api.predictStock({ symbol: predictionForm.value.symbol })
  } finally {
    predicting.value = false
  }
}

async function loadMarket() {
  marketState.value = await p2Api.marketState()
}

async function loadFit() {
  if (!strategyId.value) {
    ElMessage.warning('请输入策略ID')
    return
  }
  loadingFit.value = true
  try {
    environmentResult.value = await p2Api.strategyFit(strategyId.value)
  } finally {
    loadingFit.value = false
  }
}

async function loadPortfolioRisk() {
  loadingPortfolio.value = true
  try {
    const ids = portfolioForm.value.strategy_ids
      ? portfolioForm.value.strategy_ids.split(',').map((x) => x.trim()).filter(Boolean)
      : null
    portfolioRisk.value = await p2Api.portfolioReport({
      strategy_ids: ids,
      max_positions: portfolioForm.value.max_positions
    })
  } finally {
    loadingPortfolio.value = false
  }
}

onMounted(async () => {
  await Promise.allSettled([loadModelInfo(), loadMarket()])
})

function formatPercent(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function formatDecimal(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(3)
}
</script>

<style scoped>
.section-card {
  margin-bottom: 12px;
}

.metrics-panel {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-blank);
}

.metrics-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-weight: 600;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 10px;
}

.metric-block {
  padding: 10px;
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}

.metric-title {
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
  font-weight: 600;
  font-size: 13px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.metric-row strong {
  color: var(--el-text-color-primary);
}

.metrics-note {
  margin-top: 10px;
}

@media (max-width: 900px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
