<template>
  <div class="rb-page intelligent-screener-page">
    <h1 class="rb-page-title">智能选股</h1>
    <p class="rb-page-desc">根据条件精准筛选候选股票，自动评分排序并展示命中原因</p>

    <el-card shadow="never" class="rb-card strategy-config-card">
      <template #header>
        <div class="rb-page-header">
          <span>策略配置</span>
        </div>
      </template>

      <el-form :model="form" label-width="120px" class="rb-form">
        <el-form-item label="选股要求">
          <div class="intent-input">
            <el-input
              v-model="intentText"
              type="textarea"
              :rows="3"
              placeholder="例如：找最近20日放量突破、回踩MA20不破、不超买、前10只股票"
            />
            <div class="intent-actions">
              <el-button :loading="parsingIntent" @click="parseIntent">
                解析要求
              </el-button>
              <el-button type="primary" plain :loading="generatingStrategies" @click="generateCandidateStrategies">
                生成候选策略
              </el-button>
              <el-button
                v-if="generatedStrategies.length"
                type="success"
                plain
                :loading="batchBacktestLoading"
                @click="batchBacktestCandidates(false)"
              >
                批量回测排行
              </el-button>
              <el-tag v-if="parserLabel" size="small" :type="parserTagType">
                {{ parserLabel }}
              </el-tag>
              <span v-if="parsedWarning" class="intent-warning">{{ parsedWarning }}</span>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="策略名称">
          <el-input v-model="form.name" placeholder="例如：放量突破回踩策略" />
        </el-form-item>

        <el-form-item label="投资周期">
          <el-radio-group v-model="form.horizon">
            <el-radio-button label="short">短线</el-radio-button>
            <el-radio-button label="medium">中线</el-radio-button>
            <el-radio-button label="long">长线</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="股票池">
          <el-checkbox-group v-model="form.boards">
            <el-checkbox label="main">主板</el-checkbox>
            <el-checkbox label="chinext">创业板</el-checkbox>
            <el-checkbox label="star">科创板</el-checkbox>
          </el-checkbox-group>
          <el-checkbox v-model="form.exclude_st" style="margin-left: 20px">排除ST</el-checkbox>
        </el-form-item>

        <el-divider content-position="left">筛选条件</el-divider>

        <div v-for="(cond, index) in form.conditions" :key="index" class="condition-row">
          <el-select v-model="cond.factor" placeholder="选择因子" style="width: 200px">
            <el-option-group label="均线因子">
              <el-option label="MA5" value="ma5" />
              <el-option label="MA10" value="ma10" />
              <el-option label="MA20" value="ma20" />
              <el-option label="MA60" value="ma60" />
              <el-option label="收盘价>MA20" value="close_above_ma20" />
              <el-option label="均线多头排列" value="ma_bullish_alignment" />
            </el-option-group>
            <el-option-group label="技术指标">
              <el-option label="RSI6" value="rsi6" />
              <el-option label="RSI12" value="rsi12" />
              <el-option label="RSI24" value="rsi24" />
              <el-option label="MACD柱" value="macd_hist" />
            </el-option-group>
            <el-option-group label="收益率">
              <el-option label="1日收益率" value="return_1d" />
              <el-option label="5日收益率" value="return_5d" />
              <el-option label="20日收益率" value="return_20d" />
              <el-option label="60日收益率" value="return_60d" />
            </el-option-group>
            <el-option-group label="量价">
              <el-option label="量比(5日/20日)" value="volume_ratio_5_20" />
              <el-option label="20日波动率" value="volatility_20d" />
            </el-option-group>
            <el-option-group label="形态">
              <el-option label="突破20日新高" value="breakout_20d_high" />
              <el-option label="回踩MA20不破" value="pullback_to_ma20" />
              <el-option label="60日价格分位" value="price_position_60d" />
            </el-option-group>
          </el-select>

          <el-select v-model="cond.op" placeholder="操作符" style="width: 100px; margin-left: 10px">
            <el-option label=">" value="gt" />
            <el-option label="<" value="lt" />
            <el-option label="=" value="eq" />
            <el-option label=">=" value="gte" />
            <el-option label="<=" value="lte" />
          </el-select>

          <el-input
            v-model="cond.value"
            placeholder="目标值"
            style="width: 150px; margin-left: 10px"
          />

          <el-input-number
            v-model="cond.weight"
            :min="0"
            :max="2"
            :step="0.1"
            placeholder="权重"
            style="width: 120px; margin-left: 10px"
          />

          <el-button
            type="danger"
            link
            @click="removeCondition(index)"
            style="margin-left: 10px"
          >
            删除
          </el-button>
        </div>

        <el-button type="primary" link @click="addCondition">+ 添加条件</el-button>

        <el-divider content-position="left">排序规则</el-divider>

        <div v-for="(rank, index) in form.ranking" :key="index" class="condition-row">
          <el-select v-model="rank.factor" placeholder="选择因子" style="width: 200px">
            <el-option label="1日收益率" value="return_1d" />
            <el-option label="5日收益率" value="return_5d" />
            <el-option label="20日收益率" value="return_20d" />
            <el-option label="60日收益率" value="return_60d" />
            <el-option label="量比" value="volume_ratio_5_20" />
            <el-option label="RSI12" value="rsi12" />
            <el-option label="波动率" value="volatility_20d" />
            <el-option label="价格分位" value="price_position_60d" />
          </el-select>

          <el-select v-model="rank.direction" style="width: 120px; margin-left: 10px">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>

          <el-input-number
            v-model="rank.weight"
            :min="0"
            :max="2"
            :step="0.1"
            style="width: 120px; margin-left: 10px"
          />

          <el-button type="danger" link @click="removeRanking(index)" style="margin-left: 10px">
            删除
          </el-button>
        </div>

        <el-button type="primary" link @click="addRanking">+ 添加排序</el-button>

        <el-divider />

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runScreener">
            <el-icon><Search /></el-icon>
            开始选股
          </el-button>
          <el-button type="success" :loading="backtestLoading" @click="runAndBacktest">
            <el-icon><Histogram /></el-icon>
            选股并回测
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="generatedStrategies.length" shadow="never" class="rb-card result-card">
      <template #header>
        <div class="rb-page-header">
          <span>P1 候选策略</span>
          <div>
            <el-button
              size="small"
              type="success"
              :loading="batchBacktestLoading"
              @click="batchBacktestCandidates(true)"
            >
              回测并保存推荐
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="clarification?.need_clarification"
        :title="`建议补充：${clarification.questions.join('；')}`"
        type="warning"
        show-icon
        :closable="false"
        class="intent-warning-alert"
      />

      <el-table :data="generatedStrategies" stripe>
        <el-table-column prop="name" label="策略名称" min-width="180" />
        <el-table-column prop="horizon" label="周期" width="80">
          <template #default="{ row }">{{ getHorizonLabel(row.horizon) }}</template>
        </el-table-column>
        <el-table-column label="入场条件" min-width="260">
          <template #default="{ row }">
            <el-tag
              v-for="cond in row.entry_conditions?.slice(0, 4)"
              :key="`${row.name}-${cond.factor}-${cond.op}`"
              size="small"
              class="condition-chip"
            >
              {{ cond.factor }} {{ cond.op }} {{ formatValue(cond.value) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="applyStrategySpec(row)">套用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="batchRanking.length" shadow="never" class="rb-card result-card">
      <template #header>
        <div class="rb-page-header">
          <span>P1 批量回测排行榜</span>
          <div class="result-meta">
            <span>候选 {{ batchBacktestResult?.total || 0 }} 个</span>
            <span>推荐 {{ batchBacktestResult?.recommended?.length || 0 }} 个</span>
          </div>
        </div>
      </template>

      <el-table :data="batchRanking" stripe>
        <el-table-column prop="name" label="策略名称" min-width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getResearchStatusType(row.status)">{{ getResearchStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="研究分" width="90" />
        <el-table-column label="评级" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.rating?.rating" :type="getRatingType(row.rating.rating)">
              {{ row.rating.rating }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="样本外年化" width="120">
          <template #default="{ row }">{{ formatPercent(row.metrics?.out_sample_annual_return) }}</template>
        </el-table-column>
        <el-table-column label="样本外夏普" width="110">
          <template #default="{ row }">{{ row.metrics?.out_sample_sharpe?.toFixed?.(2) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="最大回撤" width="110">
          <template #default="{ row }">{{ formatPercent(row.metrics?.out_sample_max_drawdown) }}</template>
        </el-table-column>
        <el-table-column label="数据质量" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.data_quality?.quality_grade" :type="getQualityType(row.data_quality.quality_grade)">
              {{ row.data_quality.quality_grade }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="筛选原因" min-width="220" />
        <el-table-column label="保存结果" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.saved_strategy_id" type="success" size="small">{{ row.saved_strategy_id }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 选股结果 -->
    <el-card v-if="result" shadow="never" class="rb-card result-card">
      <template #header>
        <div class="rb-page-header">
          <span>选股结果</span>
          <div class="result-meta">
            <span>扫描 {{ result.total_scanned }} 只</span>
            <span>命中 {{ result.total_matched }} 只</span>
            <span>耗时 {{ result.execution_time_ms.toFixed(0) }}ms</span>
          </div>
        </div>
      </template>

      <DataQualityCard
        v-if="result.data_quality_summary"
        :quality-summary="result.data_quality_summary"
        show-details
        class="quality-card-inline"
      />

      <el-table :data="result.candidates" stripe>
        <el-table-column prop="rank" label="排名" width="80" />
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="score" label="得分" width="100">
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.score)">{{ row.score.toFixed(1) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quality_level" label="数据质量" width="100">
          <template #default="{ row }">
            <el-tag :type="getQualityType(row.quality_level)">{{ row.quality_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="命中条件" min-width="200">
          <template #default="{ row }">
            <div class="matched-conditions">
              <el-tag
                v-for="(cond, idx) in row.matched_conditions"
                :key="idx"
                size="small"
                style="margin-right: 5px; margin-bottom: 5px"
              >
                {{ cond.factor }}: {{ formatValue(cond.value) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="analyzeStock(row.symbol)">
              深度分析
            </el-button>
            <el-button size="small" link>回测</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 回测结果和评级 -->
    <el-card v-if="backtestResult && rating" shadow="never" class="rb-card result-card">
      <template #header>
        <div class="rb-page-header">
          <span>回测结果与评级</span>
          <el-tag :type="getRatingType(rating.rating)" size="large">
            评级: {{ rating.rating }}
          </el-tag>
        </div>
      </template>

      <el-alert
        :title="rating.reason"
        :type="getRatingAlertType(rating.rating)"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #default>
          <div>{{ rating.recommendation }}</div>
          <ul style="margin: 10px 0 0 20px; padding: 0">
            <li v-for="(r, idx) in rating.reasons" :key="idx">{{ r }}</li>
          </ul>
        </template>
      </el-alert>

      <el-row :gutter="20" class="quality-row">
        <el-col :xs="24" :md="12">
          <DataQualityCard
            v-if="backtestResult.in_sample?.data_quality_summary"
            :quality-summary="backtestResult.in_sample.data_quality_summary"
            show-details
          />
        </el-col>
        <el-col :xs="24" :md="12">
          <DataQualityCard
            v-if="backtestResult.out_sample?.data_quality_summary"
            :quality-summary="backtestResult.out_sample.data_quality_summary"
            show-details
          />
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="never" header="样本内表现">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="年化收益">
                {{ (backtestResult.in_sample.metrics.annual_return * 100).toFixed(2) }}%
              </el-descriptions-item>
              <el-descriptions-item label="最大回撤">
                {{ (backtestResult.in_sample.metrics.max_drawdown * 100).toFixed(2) }}%
              </el-descriptions-item>
              <el-descriptions-item label="夏普比率">
                {{ backtestResult.in_sample.metrics.sharpe_ratio.toFixed(2) }}
              </el-descriptions-item>
              <el-descriptions-item label="胜率">
                {{ (backtestResult.in_sample.metrics.win_rate * 100).toFixed(1) }}%
              </el-descriptions-item>
              <el-descriptions-item label="盈亏比">
                {{ backtestResult.in_sample.metrics.profit_loss_ratio.toFixed(2) }}
              </el-descriptions-item>
              <el-descriptions-item label="交易次数">
                {{ backtestResult.in_sample.metrics.total_trades }}
              </el-descriptions-item>
              <el-descriptions-item label="跳过交易">
                {{ backtestResult.in_sample.metrics.skipped_trade_count || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="基准收益">
                {{ formatPercent(backtestResult.in_sample.metrics.benchmark_return) }}
              </el-descriptions-item>
              <el-descriptions-item label="滑点">
                {{ formatPercent(backtestResult.in_sample.metrics.costs?.slippage) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="never" header="样本外表现">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="年化收益">
                {{ (backtestResult.out_sample.metrics.annual_return * 100).toFixed(2) }}%
              </el-descriptions-item>
              <el-descriptions-item label="最大回撤">
                {{ (backtestResult.out_sample.metrics.max_drawdown * 100).toFixed(2) }}%
              </el-descriptions-item>
              <el-descriptions-item label="夏普比率">
                {{ backtestResult.out_sample.metrics.sharpe_ratio.toFixed(2) }}
              </el-descriptions-item>
              <el-descriptions-item label="胜率">
                {{ (backtestResult.out_sample.metrics.win_rate * 100).toFixed(1) }}%
              </el-descriptions-item>
              <el-descriptions-item label="盈亏比">
                {{ backtestResult.out_sample.metrics.profit_loss_ratio.toFixed(2) }}
              </el-descriptions-item>
              <el-descriptions-item label="交易次数">
                {{ backtestResult.out_sample.metrics.total_trades }}
              </el-descriptions-item>
              <el-descriptions-item label="跳过交易">
                {{ backtestResult.out_sample.metrics.skipped_trade_count || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="基准收益">
                {{ formatPercent(backtestResult.out_sample.metrics.benchmark_return) }}
              </el-descriptions-item>
              <el-descriptions-item label="滑点">
                {{ formatPercent(backtestResult.out_sample.metrics.costs?.slippage) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <el-alert
        v-if="backtestResult.overfit_flag"
        title="⚠️ 疑似过拟合"
        type="warning"
        :closable="false"
        style="margin-top: 20px"
      >
        {{ backtestResult.overfit_reason }}
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Histogram } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import intelligentScreenerApi from '@/api/intelligentScreener'
import DataQualityCard from '@/components/DataQualityCard.vue'

const router = useRouter()
const loading = ref(false)
const backtestLoading = ref(false)
const parsingIntent = ref(false)
const generatingStrategies = ref(false)
const batchBacktestLoading = ref(false)
const result = ref(null)
const backtestResult = ref(null)
const rating = ref(null)
const generatedStrategies = ref([])
const batchBacktestResult = ref(null)
const batchRanking = ref([])
const clarification = ref(null)
const intentText = ref('')
const parsedWarning = ref('')
const parserLabel = ref('')
const parserTagType = ref('info')

const form = reactive({
  name: '',
  horizon: 'medium',
  boards: ['main', 'chinext', 'star'],
  exclude_st: true,
  conditions: [
    { factor: 'breakout_20d_high', op: 'eq', value: true, weight: 1.0 },
    { factor: 'volume_ratio_5_20', op: 'gt', value: 1.5, weight: 0.8 },
    { factor: 'close_above_ma20', op: 'eq', value: true, weight: 1.0 }
  ],
  ranking: [
    { factor: 'return_20d', direction: 'desc', weight: 0.6 },
    { factor: 'volume_ratio_5_20', direction: 'desc', weight: 0.4 }
  ]
})

function addCondition() {
  form.conditions.push({ factor: '', op: 'gt', value: '', weight: 1.0 })
}

function removeCondition(index) {
  form.conditions.splice(index, 1)
}

function addRanking() {
  form.ranking.push({ factor: '', direction: 'desc', weight: 1.0 })
}

function removeRanking(index) {
  form.ranking.splice(index, 1)
}

function resetForm() {
  form.name = ''
  form.horizon = 'medium'
  form.boards = ['main', 'chinext', 'star']
  form.exclude_st = true
  form.conditions = []
  form.ranking = []
  result.value = null
  backtestResult.value = null
  rating.value = null
  generatedStrategies.value = []
  batchBacktestResult.value = null
  batchRanking.value = []
  clarification.value = null
  parsedWarning.value = ''
  parserLabel.value = ''
}

async function parseIntent() {
  if (!intentText.value.trim()) {
    ElMessage.warning('请输入选股要求')
    return
  }
  parsingIntent.value = true
  parsedWarning.value = ''
  try {
    const data = await intelligentScreenerApi.parseIntent(intentText.value.trim())
    const spec = data.strategy_spec
    form.name = spec.name || form.name
    form.horizon = spec.horizon || 'medium'
    form.boards = spec.universe?.boards || ['main', 'chinext', 'star']
    form.exclude_st = spec.universe?.exclude_st ?? true
    form.conditions = (spec.entry_conditions || []).map((c) => ({ ...c }))
    form.ranking = (spec.ranking || []).map((r) => ({ ...r }))
    parsedWarning.value = data.warnings?.[0] || ''
    parserLabel.value = data.parser === 'deepseek' ? 'DeepSeek 解析' : data.fallback_used ? '规则兜底' : '规则解析'
    parserTagType.value = data.parser === 'deepseek' ? 'success' : data.fallback_used ? 'warning' : 'info'
    applyStrategySpec(spec)
    ElMessage.success('已解析为可执行策略条件，可继续调整后运行')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '解析失败')
  } finally {
    parsingIntent.value = false
  }
}

async function generateCandidateStrategies() {
  if (!intentText.value.trim()) {
    ElMessage.warning('请输入策略目标')
    return
  }
  generatingStrategies.value = true
  batchBacktestResult.value = null
  batchRanking.value = []
  try {
    const data = await intelligentScreenerApi.generateStrategies(intentText.value.trim(), 4)
    generatedStrategies.value = data.strategies || []
    clarification.value = data.clarification || null
    parserLabel.value = data.parser === 'deepseek' ? 'DeepSeek 候选生成' : '规则候选生成'
    parserTagType.value = data.parser === 'deepseek' ? 'success' : 'info'
    if (data.warnings?.length) {
      parsedWarning.value = data.warnings[0]
    }
    if (generatedStrategies.value.length) {
      applyStrategySpec(generatedStrategies.value[0])
    }
    ElMessage.success(`已生成 ${generatedStrategies.value.length} 个可执行候选策略`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '生成候选策略失败')
  } finally {
    generatingStrategies.value = false
  }
}

async function batchBacktestCandidates(saveRecommended = false) {
  if (!generatedStrategies.value.length) {
    ElMessage.warning('请先生成候选策略')
    return
  }
  batchBacktestLoading.value = true
  try {
    const data = await intelligentScreenerApi.batchBacktest(generatedStrategies.value, saveRecommended, 2)
    batchBacktestResult.value = data
    batchRanking.value = data.ranked || []
    const saved = data.saved_strategy_ids?.length || 0
    ElMessage.success(saveRecommended ? `批量回测完成，已保存 ${saved} 个推荐策略` : '批量回测完成')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '批量回测失败')
  } finally {
    batchBacktestLoading.value = false
  }
}

function applyStrategySpec(spec) {
  if (!spec) return
  form.name = spec.name || form.name
  form.horizon = spec.horizon || 'medium'
  form.boards = spec.universe?.boards || ['main', 'chinext', 'star']
  form.exclude_st = spec.universe?.exclude_st ?? true
  form.conditions = (spec.entry_conditions || []).map((c) => ({ ...c }))
  form.ranking = (spec.ranking || []).map((r) => ({ ...r }))
}

async function runAndBacktest() {
  if (!form.name) {
    ElMessage.warning('请输入策略名称')
    return
  }

  if (form.conditions.length === 0) {
    ElMessage.warning('请至少添加一个筛选条件')
    return
  }

  backtestLoading.value = true

  try {
    const strategySpec = {
      name: form.name,
      horizon: form.horizon,
      universe: {
        market: 'A股',
        exclude_st: form.exclude_st,
        boards: form.boards
      },
      entry_conditions: form.conditions.map(c => ({
        factor: c.factor,
        op: c.op,
        value: c.value === 'true' ? true : c.value === 'false' ? false : parseFloat(c.value) || c.value,
        weight: c.weight
      })),
      ranking: form.ranking,
      position: {
        max_positions: 10,
        weighting: 'equal_weight'
      }
    }

    const res = await fetch('/api/v1/intelligent-screener/run-and-backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_spec: strategySpec })
    })

    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.detail || '执行失败')
    }

    result.value = data.screener_result
    backtestResult.value = data.backtest_result
    rating.value = data.rating

    if (data.strategy_id) {
      ElMessage.success(`选股和回测完成！策略已保存 (评级: ${data.rating.rating})`)
    } else {
      ElMessage.success(`选股和回测完成 (评级: ${data.rating.rating})`)
    }
  } catch (error) {
    ElMessage.error(error.message || '执行失败')
  } finally {
    backtestLoading.value = false
  }
}

async function runScreener() {
  if (!form.name) {
    ElMessage.warning('请输入策略名称')
    return
  }

  if (form.conditions.length === 0) {
    ElMessage.warning('请至少添加一个筛选条件')
    return
  }

  loading.value = true

  try {
    const strategySpec = {
      name: form.name,
      horizon: form.horizon,
      universe: {
        market: 'A股',
        exclude_st: form.exclude_st,
        boards: form.boards
      },
      entry_conditions: form.conditions.map(c => ({
        factor: c.factor,
        op: c.op,
        value: c.value === 'true' ? true : c.value === 'false' ? false : parseFloat(c.value) || c.value,
        weight: c.weight
      })),
      ranking: form.ranking,
      position: {
        max_positions: 10,
        weighting: 'equal_weight'
      }
    }

    const res = await intelligentScreenerApi.runScreener(strategySpec)
    result.value = res
    ElMessage.success(`选股完成，共找到 ${res.total_matched} 只候选股`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '选股失败')
  } finally {
    loading.value = false
  }
}

function getScoreType(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return ''
  if (score >= 40) return 'warning'
  return 'danger'
}

function getQualityType(level) {
  if (level === 'A') return 'success'
  if (level === 'B') return ''
  if (level === 'C') return 'warning'
  return 'danger'
}

function formatValue(val) {
  if (typeof val === 'number') {
    return val.toFixed(2)
  }
  return val
}

function analyzeStock(symbol) {
  router.push({ name: 'home', query: { symbol } })
}

function getRatingType(rating) {
  if (rating === 'A') return 'success'
  if (rating === 'B') return ''
  if (rating === 'C') return 'warning'
  return 'danger'
}

function getRatingAlertType(rating) {
  if (rating === 'A') return 'success'
  if (rating === 'B') return 'info'
  if (rating === 'C') return 'warning'
  return 'error'
}

function getHorizonLabel(horizon) {
  const map = { short: '短线', medium: '中线', long: '长线' }
  return map[horizon] || horizon || '-'
}

function getResearchStatusLabel(status) {
  const map = {
    qualified: '入围',
    filtered: '过滤',
    rejected: '拒绝',
    invalid: '无效',
    error: '错误'
  }
  return map[status] || status || '-'
}

function getResearchStatusType(status) {
  const map = {
    qualified: 'success',
    filtered: 'warning',
    rejected: 'info',
    invalid: 'danger',
    error: 'danger'
  }
  return map[status] || 'info'
}

function formatPercent(value) {
  if (value === null || value === undefined) return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}
</script>

<style scoped>
.intelligent-screener-page {
  padding: 20px;
}

.strategy-config-card {
  margin-bottom: 20px;
}

.condition-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.result-meta {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.result-meta span {
  padding: 0 10px;
  border-left: 1px solid var(--el-border-color);
}

.result-meta span:first-child {
  border-left: none;
}

.quality-card-inline,
.quality-row {
  margin-bottom: 16px;
}

.intent-warning-alert {
  margin-bottom: 12px;
}

.condition-chip {
  margin-right: 6px;
  margin-bottom: 4px;
}

.matched-conditions {
  display: flex;
  flex-wrap: wrap;
}

.intent-input {
  width: 100%;
}

.intent-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.intent-warning {
  color: var(--el-color-warning);
  font-size: 13px;
}
</style>
