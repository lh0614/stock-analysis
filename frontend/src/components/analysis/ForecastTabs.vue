<template>
  <el-card shadow="never" class="rb-card forecast-card">
    <template #header>
      <span>周期预测（参考区间）</span>
    </template>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="短线" name="short" />
      <el-tab-pane label="中线" name="medium" />
      <el-tab-pane label="长线" name="long" />
    </el-tabs>

    <div v-if="loading" class="loading">
      <el-skeleton :rows="2" animated />
    </div>

    <template v-else-if="current">
      <el-descriptions v-if="current.available" :column="3" border size="small">
        <el-descriptions-item label="现价">{{ current.current }}</el-descriptions-item>
        <el-descriptions-item label="区间下沿">{{ current.low }}</el-descriptions-item>
        <el-descriptions-item label="区间上沿">{{ current.high }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="数据不足，无法估算" />
      <p class="note">{{ current.probability_note }}</p>
    </template>

    <p class="disclaimer">预测区间为历史波动估算，不构成投资建议</p>
  </el-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  forecasts: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['request-horizon'])

const activeTab = ref('short')

const current = computed(() => {
  if (!props.forecasts) return null
  return props.forecasts[activeTab.value]
})

watch(
  () => props.forecasts,
  (v) => {
    if (v?.short) activeTab.value = 'short'
  }
)

function onTabChange(name) {
  if (!props.forecasts?.[name]?.available) {
    emit('request-horizon', name)
  }
}
</script>

<style scoped>
.note {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 10px;
}

.disclaimer {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 12px;
}

.loading {
  padding: 8px 0;
}
</style>
