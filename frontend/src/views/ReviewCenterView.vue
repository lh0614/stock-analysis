<template>
  <div class="rb-page">
    <ComplianceDisclaimer />
    <h1 class="rb-page-title">复盘中心</h1>
    <el-row :gutter="12">
      <el-col :xs="24" :md="9">
        <el-card shadow="never">
          <template #header>新建复盘</template>
          <el-form label-width="90px">
            <el-form-item label="计划ID"><el-input v-model="form.plan_id" /></el-form-item>
            <el-form-item label="盈亏"><el-input-number v-model="form.pnl" /></el-form-item>
            <el-form-item label="标签">
              <el-select v-model="form.tags" multiple style="width: 100%">
                <el-option v-for="t in tags" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="总结"><el-input v-model="form.lesson" type="textarea" :rows="3" /></el-form-item>
            <el-form-item><el-button type="primary" @click="createReview">保存</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="15">
        <el-card shadow="never" style="margin-bottom: 12px">
          <div>复盘数：{{ stats.review_count || 0 }}</div>
          <div>累计盈亏：{{ stats.total_pnl || 0 }}</div>
        </el-card>
        <el-card shadow="never">
          <template #header>复盘列表</template>
          <el-table :data="reviews" size="small">
            <el-table-column prop="plan_id" label="计划ID" min-width="160" />
            <el-table-column prop="pnl" label="盈亏" width="90" />
            <el-table-column prop="tags" label="标签" min-width="200">
              <template #default="{ row }">{{ (row.tags || []).join(', ') }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" min-width="160" />
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
import reviewsApi from '@/api/reviews'

const form = ref({ plan_id: '', pnl: 0, tags: [], lesson: '' })
const tags = ref([])
const reviews = ref([])
const stats = ref({})

async function loadData() {
  const list = await reviewsApi.list()
  reviews.value = list.reviews || []
  tags.value = list.tags || []
  stats.value = await reviewsApi.stats()
}

async function createReview() {
  await reviewsApi.create(form.value)
  ElMessage.success('复盘已保存')
  await loadData()
}

onMounted(loadData)
</script>
