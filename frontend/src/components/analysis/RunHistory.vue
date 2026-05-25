<template>
  <el-card shadow="never" class="rb-card run-history">
    <template #header>
      <div class="header-row">
        <span>最近分析记录</span>
        <el-button link type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="runs" size="small" stripe max-height="220">
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column prop="symbol" label="代码" width="80" />
      <el-table-column label="结果" width="70">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'" size="small">
            {{ row.success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="run_id" label="运行 ID" show-overflow-tooltip />
    </el-table>
    <el-empty v-if="!loading && !runs.length" description="暂无记录" />
  </el-card>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import analysisApi from '@/api/analysis.js'

const props = defineProps({
  symbol: { type: String, default: '' }
})

const runs = ref([])
const loading = ref(false)

async function load() {
  if (!props.symbol) {
    runs.value = []
    return
  }
  loading.value = true
  try {
    const data = await analysisApi.listRuns(props.symbol, 10)
    runs.value = data.runs || []
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.symbol, load)
onMounted(load)

defineExpose({ load })
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.run-history {
  margin-top: 12px;
}
</style>
