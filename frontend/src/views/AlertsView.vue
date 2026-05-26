<template>
  <div class="rb-page alerts-page">
    <h1 class="rb-page-title">预警中心</h1>
    <p class="rb-page-desc">价格与指标规则，支持冷却与后台自动检测</p>
    <el-row :gutter="16">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="rb-card">
          <template #header>
            <div class="rb-page-header">
              <span>新建预警</span>
              <el-button link type="primary" @click="runEvaluate" :loading="evaluating">
                立即检测
              </el-button>
            </div>
          </template>
          <el-form class="rb-form" label-width="100px">
            <el-form-item label="股票代码">
              <el-input v-model="form.symbol" placeholder="如 000001" />
            </el-form-item>
            <el-form-item label="规则类型">
              <el-select v-model="form.rule_type" style="width: 100%">
                <el-option
                  v-for="r in ruleTypes"
                  :key="r.id"
                  :label="r.label"
                  :value="r.id"
                />
              </el-select>
              <p v-if="currentRuleDesc" class="rule-desc">{{ currentRuleDesc }}</p>
            </el-form-item>
            <el-form-item label="阈值">
              <el-input-number v-model="form.threshold" :step="0.1" style="width: 100%" />
              <p v-if="thresholdUnitHint" class="rule-desc">单位：{{ thresholdUnitHint }}</p>
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="form.name" placeholder="可选" />
            </el-form-item>
            <el-form-item label="冷却(分钟)">
              <el-input-number v-model="form.cooldown_minutes" :min="5" :max="1440" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="createAlert">添加预警</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="rb-card" v-loading="loading">
          <template #header>预警规则</template>
          <el-table :data="alerts" border>
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column label="规则" min-width="140">
              <template #default="{ row }">
                {{ row.rule_label }} {{ row.threshold }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.enabled"
                  @change="(v) => toggleEnabled(row, v)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button link type="danger" @click="remove(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!alerts.length" description="暂无预警规则" />
        </el-card>

        <el-card shadow="never" class="rb-card events-card">
          <template #header>触发记录</template>
          <el-timeline v-if="events.length">
            <el-timeline-item
              v-for="ev in events"
              :key="ev.id"
              :timestamp="ev.created_at"
              type="danger"
            >
              {{ ev.message }}
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无触发记录" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import alertsApi from '@/api/alerts.js'

const loading = ref(false)
const evaluating = ref(false)
const alerts = ref([])
const events = ref([])
const ruleTypes = ref([])
const form = ref({
  symbol: '000001',
  rule_type: 'price_above',
  threshold: 10,
  name: '',
  cooldown_minutes: 60
})

const RULE_DESC = {
  price_above: '当收盘价高于设定阈值时触发预警。',
  price_below: '当收盘价低于设定阈值时触发预警。',
  change_pct_above: '当日涨幅（相对昨收）超过设定百分比时触发。',
  change_pct_below: '当日跌幅（相对昨收）超过设定百分比时触发。',
  rsi_above: '当 RSI12 指标高于设定值时触发（常用区间 0–100）。',
  rsi_below: '当 RSI12 指标低于设定值时触发（常用区间 0–100）。'
}

const THRESHOLD_UNITS = {
  price_above: '元',
  price_below: '元',
  change_pct_above: '%',
  change_pct_below: '%',
  rsi_above: 'RSI 指标值（0–100）',
  rsi_below: 'RSI 指标值（0–100）'
}

const currentRuleDesc = computed(() => RULE_DESC[form.value.rule_type] || '')
const thresholdUnitHint = computed(() => THRESHOLD_UNITS[form.value.rule_type] || '')

function isValidSymbol(symbol) {
  return /^\d{6}$/.test(String(symbol || '').trim())
}

async function load() {
  loading.value = true
  try {
    const [a, e, r] = await Promise.all([
      alertsApi.list(),
      alertsApi.events(30),
      alertsApi.rules()
    ])
    alerts.value = a.alerts || []
    events.value = e.events || []
    ruleTypes.value = r.rules || []
  } finally {
    loading.value = false
  }
}

async function createAlert() {
  if (!isValidSymbol(form.value.symbol)) {
    ElMessage.warning('股票代码须为 6 位数字')
    return
  }
  try {
    await alertsApi.create({ ...form.value, symbol: form.value.symbol.trim() })
    ElMessage.success('预警已添加')
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

async function toggleEnabled(row, enabled) {
  await alertsApi.update(row.id, { enabled })
  row.enabled = enabled
}

async function remove(id) {
  await alertsApi.remove(id)
  ElMessage.success('已删除')
  await load()
}

async function runEvaluate() {
  evaluating.value = true
  try {
    const res = await alertsApi.evaluate()
    const n = res.triggered?.length || 0
    ElMessage.success(n ? `触发 ${n} 条预警` : '检测完成，无新触发')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    evaluating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.events-card {
  margin-top: 16px;
}

.rule-desc {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-secondary);
}
</style>
