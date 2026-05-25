<template>
  <el-card v-if="output" shadow="never" class="rb-card strategy-output">
    <template #header>
      <span>策略输出</span>
      <el-tag v-if="strategyName" size="small" type="info">{{ strategyName }}</el-tag>
    </template>
    <el-descriptions v-if="typeof output === 'object'" :column="1" border size="small">
      <el-descriptions-item v-if="output.score !== undefined" label="评分">
        {{ output.score }}
      </el-descriptions-item>
      <el-descriptions-item v-if="output.notes?.length" label="说明">
        <ul class="notes">
          <li v-for="(n, i) in output.notes" :key="i">{{ n }}</li>
        </ul>
      </el-descriptions-item>
    </el-descriptions>
    <pre v-else class="raw">{{ output }}</pre>
  </el-card>
</template>

<script setup>
defineProps({
  output: { type: [Object, String, Number], default: null },
  strategyName: { type: String, default: '' }
})
</script>

<style scoped>
.strategy-output {
  margin-bottom: 20px;
}

.strategy-output :deep(.el-card__header) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notes {
  margin: 0;
  padding-left: 18px;
}

.raw {
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 8px;
  border-radius: 4px;
}
</style>
