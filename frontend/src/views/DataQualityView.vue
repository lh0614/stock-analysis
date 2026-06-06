<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">数据质量</h1>
    <p class="rb-page-desc">质量等级分布、跨源冲突与缺失明细</p>

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>等级分布</template>
          <div v-for="(v, k) in summary.counts || {}" :key="k" class="count-row">
            <el-tag :type="tagType(k)">{{ k }}</el-tag>
            <span>{{ v }}</span>
          </div>
          <p class="muted">总标的：{{ summary.total || 0 }} · 冲突：{{ summary.conflicts || 0 }} · D级：{{ summary.blocked || 0 }}</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>单标的查询</template>
          <el-input v-model="querySymbol" placeholder="600519" style="width: 160px; margin-right: 8px" />
          <el-button type="primary" @click="loadSymbol">查询</el-button>
          <div v-if="symbolDetail.symbol" class="symbol-detail">
            <QualityBanner :level="symbolDetail.quality_level" :hint="symbolDetail.ui_hint" />
            <p>最新交易日：{{ symbolDetail.latest_trade_date || '—' }}</p>
            <p>问题：{{ (symbolDetail.issues || []).join('、') || '无' }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs>
      <el-tab-pane label="冲突/异常">
        <el-table :data="conflicts" size="small" height="360">
          <el-table-column prop="symbol" label="代码" width="90" />
          <el-table-column prop="trade_date" label="日期" width="110" />
          <el-table-column prop="quality_level" label="等级" width="70" />
          <el-table-column prop="diff_pct" label="价差%" width="80" />
          <el-table-column prop="issues" label="问题" min-width="200">
            <template #default="{ row }">
              {{ formatIssues(row.issues) }}
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="缺失/阻断">
        <el-table :data="missing" size="small" height="360">
          <el-table-column prop="symbol" label="代码" width="90" />
          <el-table-column prop="bar_count" label="K线条数" width="90" />
          <el-table-column prop="quality_level" label="等级" width="70" />
          <el-table-column prop="issues" label="问题" min-width="220">
            <template #default="{ row }">{{ formatIssues(row.issues) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import qualityApi from '@/api/quality'
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'
import QualityBanner from '@/components/common/QualityBanner.vue'

const summary = ref({ counts: {} })
const conflicts = ref([])
const missing = ref([])
const querySymbol = ref('')
const symbolDetail = ref({})

function tagType(level) {
  if (level === 'D') return 'danger'
  if (level === 'C') return 'warning'
  if (level === 'B') return 'info'
  return 'success'
}

function formatIssues(v) {
  if (Array.isArray(v)) return v.join('、')
  if (typeof v === 'string') return v
  return ''
}

async function load() {
  summary.value = await qualityApi.summary()
  conflicts.value = (await qualityApi.conflicts(200)).items || []
  missing.value = (await qualityApi.missingBars(200)).items || []
}

async function loadSymbol() {
  if (!querySymbol.value.trim()) return
  symbolDetail.value = await qualityApi.symbol(querySymbol.value.trim())
}

onMounted(load)
</script>

<style scoped>
.count-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.symbol-detail {
  margin-top: 12px;
}
</style>
