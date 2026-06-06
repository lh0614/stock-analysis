<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">模拟组合</h1>
    <el-card shadow="never" style="margin-bottom: 12px">
      <el-form inline>
        <el-form-item label="代码"><el-input v-model="form.symbol" style="width: 120px" /></el-form-item>
        <el-form-item label="方向">
          <el-select v-model="form.side" style="width: 100px">
            <el-option value="buy" label="买入" />
            <el-option value="sell" label="卖出" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格"><el-input-number v-model="form.price" :min="0" /></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" /></el-form-item>
        <el-form-item><el-button type="primary" @click="submitTrade">记录</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-row :gutter="12">
      <el-col :xs="24" :md="10">
        <el-card shadow="never">
          <template #header>持仓</template>
          <el-table :data="summary.holdings || []" size="small">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column prop="avg_cost" label="成本" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="14">
        <el-card shadow="never">
          <template #header>成交记录</template>
          <el-table :data="trades" size="small">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="side" label="方向" width="90" />
            <el-table-column prop="price" label="价格" width="90" />
            <el-table-column prop="quantity" label="数量" width="90" />
            <el-table-column prop="traded_at" label="时间" min-width="160" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import ComplianceDisclaimer from '@/components/common/ComplianceDisclaimer.vue'

import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import portfolioApi from '@/api/portfolio'

const form = ref({ symbol: '', side: 'buy', price: null, quantity: 100 })
const trades = ref([])
const summary = ref({})

async function loadData() {
  const data = await portfolioApi.simulated()
  trades.value = data.trades || []
  summary.value = data
}

async function submitTrade() {
  await portfolioApi.addTrade(form.value)
  ElMessage.success('模拟成交已记录')
  await loadData()
}

onMounted(loadData)
</script>
