<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">回测中心</h1>
    <el-card shadow="never" style="margin-bottom: 12px">
      <el-form inline>
        <el-form-item label="股票代码">
          <el-input v-model="symbolsText" placeholder="600519,000001" style="width: 260px" />
        </el-form-item>
        <el-form-item label="策略">
          <el-select v-model="strategy" style="width: 180px">
            <el-option label="组合等权" value="portfolio_equal_weight" />
            <el-option label="MA 交叉" value="ma_cross" />
          </el-select>
        </el-form-item>
        <el-form-item label="调仓">
          <el-select v-model="rebalance" style="width: 120px">
            <el-option label="日" value="daily" />
            <el-option label="周" value="weekly" />
            <el-option label="月" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item><el-switch v-model="marketFilter" active-text="市场过滤" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="running" @click="runBacktest">运行回测</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :xs="24" :md="8"><el-card shadow="never">总收益：{{ selectedMetrics.total_return ?? '—' }}</el-card></el-col>
      <el-col :xs="24" :md="8"><el-card shadow="never">最大回撤：{{ selectedMetrics.max_drawdown ?? '—' }}</el-card></el-col>
      <el-col :xs="24" :md="8"><el-card shadow="never">夏普：{{ selectedMetrics.sharpe ?? '—' }}</el-card></el-col>
    </el-row>

    <el-card shadow="never" style="margin-bottom:12px">
      <template #header>权益曲线（简表）</template>
      <el-table :data="equityPreview" size="small" height="220">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="equity" label="权益" />
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-bottom:12px">
      <template #header>交易明细</template>
      <el-table :data="trades" size="small" height="260">
        <el-table-column prop="symbol" label="代码" width="90" />
        <el-table-column prop="side" label="方向" width="90" />
        <el-table-column prop="price" label="价格" width="90" />
        <el-table-column prop="date" label="日期" width="120" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>运行记录</template>
      <el-table :data="runs" size="small" @row-click="selectRun">
        <el-table-column prop="run_id" label="Run ID" min-width="220" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="总收益" width="100"><template #default="{ row }">{{ row.metrics?.total_return }}</template></el-table-column>
        <el-table-column label="最大回撤" width="100"><template #default="{ row }">{{ row.metrics?.max_drawdown }}</template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import backtestsApi from '@/api/backtests'
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'

const symbolsText = ref('600519,000001,300750')
const strategy = ref('portfolio_equal_weight')
const rebalance = ref('monthly')
const marketFilter = ref(false)
const runs = ref([])
const running = ref(false)
const selectedRun = ref(null)
const trades = ref([])
const equityPreview = ref([])

const selectedMetrics = computed(() => selectedRun.value?.detail?.metrics || selectedRun.value?.metrics || {})

async function loadRuns() {
  const data = await backtestsApi.runs()
  runs.value = data.runs || []
}

async function selectRun(row) {
  const detail = await backtestsApi.runDetail(row.run_id)
  selectedRun.value = detail
  const d = detail.detail || {}
  trades.value = d.trades || []
  equityPreview.value = (d.equity_curve || []).slice(-120)
}

async function runBacktest() {
  const symbols = symbolsText.value.split(/[\,\n\s]+/).map((x) => x.trim()).filter(Boolean)
  if (!symbols.length) { ElMessage.warning('请填写股票代码'); return }
  running.value = true
  try {
    const created = await backtestsApi.run({ symbols, strategy: strategy.value, rebalance: rebalance.value, market_filter: marketFilter.value })
    ElMessage.success('回测已运行')
    await loadRuns()
    if (created?.run_id) await selectRun({ run_id: created.run_id })
  } finally {
    running.value = false
  }
}

onMounted(loadRuns)
</script>
