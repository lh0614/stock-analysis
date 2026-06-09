<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">市场环境</h1>
    <el-card shadow="never" style="margin-bottom: 12px">
      <div>市场状态：<strong>{{ regime.market_regime || '—' }}</strong></div>
      <div>评分：{{ regime.score ?? '—' }}</div>
      <div>{{ regime.summary }}</div>
    </el-card>
    <el-row :gutter="12">
      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>指数趋势</template>
          <el-table :data="indices" size="small">
            <el-table-column prop="name" label="指数" min-width="120" />
            <el-table-column prop="trend" label="趋势" width="100" />
            <el-table-column prop="change_pct" label="涨跌%" width="90" />
            <el-table-column prop="signal" label="信号" min-width="140" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>市场宽度</template>
          <div>上涨家数：{{ breadth.up_count || 0 }}</div>
          <div>下跌家数：{{ breadth.down_count || 0 }}</div>
          <div>下跌占比：{{ breadth.down_ratio || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never" style="margin-top: 12px">
      <template #header>板块强弱</template>
      <el-table :data="sectors" size="small">
        <el-table-column prop="name" label="分组" min-width="120" />
        <el-table-column prop="return_5d" label="5日收益" width="110">
          <template #default="{ row }">{{ formatPercent(row.return_5d) }}</template>
        </el-table-column>
        <el-table-column prop="return_20d" label="20日收益" width="110">
          <template #default="{ row }">{{ formatPercent(row.return_20d) }}</template>
        </el-table-column>
        <el-table-column prop="ma20_bull_ratio" label="MA20强势占比" width="130">
          <template #default="{ row }">{{ formatPercent(row.ma20_bull_ratio) }}</template>
        </el-table-column>
        <el-table-column prop="sample_size" label="样本" width="80" />
        <el-table-column prop="strength" label="强弱" width="100" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'

import { onMounted, ref } from 'vue'
import marketApi from '@/api/market'

const regime = ref({})
const indices = ref([])
const breadth = ref({})
const sectors = ref([])

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}

async function load() {
  regime.value = await marketApi.regime()
  const idx = await marketApi.indices()
  indices.value = idx.indices || []
  breadth.value = await marketApi.breadth()
  const sectorData = await marketApi.sectors()
  sectors.value = sectorData.sectors || []
}

onMounted(load)
</script>
