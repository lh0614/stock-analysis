<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">交易计划</h1>
    <el-row :gutter="12">
      <el-col :xs="24" :md="10">
        <el-card shadow="never">
          <template #header>新建计划</template>
          <el-form label-width="90px">
            <el-form-item label="股票代码"><el-input v-model="form.symbol" /></el-form-item>
            <el-form-item label="触发价"><el-input-number v-model="form.trigger_price" :min="0" /></el-form-item>
            <el-form-item label="失效价"><el-input-number v-model="form.invalid_price" :min="0" /></el-form-item>
            <el-form-item><el-button type="primary" @click="createPlan">保存</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="14">
        <el-card shadow="never">
          <template #header>计划列表</template>
          <el-table :data="plans" size="small">
            <el-table-column prop="id" label="ID" min-width="180" />
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button link type="primary" @click="bindAlerts(row.id)">绑定预警</el-button>
              </template>
            </el-table-column>
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
import plansApi from '@/api/plans'

const plans = ref([])
const form = ref({ symbol: '', trigger_price: null, invalid_price: null })

async function loadPlans() {
  const data = await plansApi.list()
  plans.value = data.plans || []
}

async function createPlan() {
  await plansApi.create(form.value)
  ElMessage.success('计划已保存')
  form.value = { symbol: '', trigger_price: null, invalid_price: null }
  await loadPlans()
}

async function bindAlerts(planId) {
  await plansApi.bindAlerts(planId)
  ElMessage.success('已绑定预警')
}

onMounted(loadPlans)
</script>
