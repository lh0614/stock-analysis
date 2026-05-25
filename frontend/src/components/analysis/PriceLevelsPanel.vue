<template>
  <el-card shadow="never" class="rb-card price-panel">
    <template #header>
      <span>价格结构</span>
    </template>

    <div v-if="loading">
      <el-skeleton :rows="2" animated />
    </div>

    <el-alert v-else-if="error" :title="error" type="warning" show-icon :closable="false" />

    <template v-else-if="data">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="现价">{{ data.latest_price }}</el-descriptions-item>
        <el-descriptions-item label="区间位置">
          <el-progress :percentage="data.position_pct || 0" :stroke-width="10" />
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="data.labels?.length" class="tags">
        <el-tag v-for="t in data.labels" :key="t" size="small">{{ t }}</el-tag>
      </div>

      <el-table :data="data.levels" size="small" stripe class="levels-table">
        <el-table-column prop="label" label="关键位" />
        <el-table-column prop="type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.type === 'resistance' ? 'danger' : row.type === 'support' ? 'success' : 'info'">
              {{ typeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价位" width="100" />
      </el-table>
    </template>

    <el-empty v-else description="暂无价格结构数据" />
  </el-card>
</template>

<script setup>
defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

function typeLabel(t) {
  const m = { resistance: '压力', support: '支撑', ma: '均线' }
  return m[t] || t
}
</script>

<style scoped>
.tags {
  margin: 12px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.levels-table {
  margin-top: 12px;
}
</style>
