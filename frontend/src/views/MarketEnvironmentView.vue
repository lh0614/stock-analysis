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
  </div>
</template>

<script setup>
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'

import { onMounted, ref } from 'vue'
import marketApi from '@/api/market'

const regime = ref({})
const indices = ref([])
const breadth = ref({})

async function load() {
  regime.value = await marketApi.regime()
  const idx = await marketApi.indices()
  indices.value = idx.indices || []
  breadth.value = await marketApi.breadth()
}

onMounted(load)
</script>
