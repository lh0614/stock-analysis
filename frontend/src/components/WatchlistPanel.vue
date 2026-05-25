<template>
  <el-card class="rb-card watchlist-card" shadow="never">
    <template #header>
      <div class="wl-header">
        <span>自选股</span>
        <el-button
          v-if="currentSymbol"
          type="primary"
          link
          size="small"
          :disabled="isInWatchlist"
          @click="addCurrent"
        >
          {{ isInWatchlist ? '已在自选' : '加入自选' }}
        </el-button>
      </div>
    </template>

    <el-skeleton v-if="loading" :rows="3" animated />
    <el-empty v-else-if="!items.length" description="暂无自选，分析页可一键添加" />
    <el-scrollbar v-else max-height="220px">
      <div
        v-for="item in items"
        :key="item.symbol"
        class="wl-item"
        :class="{ active: item.symbol === currentSymbol }"
        @click="$emit('select', item.symbol)"
      >
        <span class="wl-symbol">{{ item.symbol }}</span>
        <span class="wl-name">{{ item.name || '—' }}</span>
        <el-button link type="danger" size="small" @click.stop="remove(item.symbol)">
          移除
        </el-button>
      </div>
    </el-scrollbar>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import watchlistApi from '@/api/watchlist.js'

const props = defineProps({
  currentSymbol: { type: String, default: '' }
})

defineEmits(['select'])

const loading = ref(false)
const groups = ref([])

const items = computed(() => groups.value[0]?.items || [])

const isInWatchlist = computed(() =>
  items.value.some((i) => i.symbol === props.currentSymbol)
)

async function load() {
  loading.value = true
  try {
    const data = await watchlistApi.list()
    groups.value = data.groups || []
  } catch (e) {
    console.warn('[watchlist]', e.response?.data?.detail || e.message)
    groups.value = []
  } finally {
    loading.value = false
  }
}

async function addCurrent() {
  if (!props.currentSymbol) return
  try {
    await watchlistApi.add(props.currentSymbol)
    ElMessage.success('已加入自选')
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

async function remove(symbol) {
  await watchlistApi.remove(symbol)
  await load()
}

watch(() => props.currentSymbol, load)

onMounted(load)

defineExpose({ load, addCurrent })
</script>

<style scoped>
.watchlist-card {
  margin-bottom: 16px;
}

.wl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wl-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  border-radius: 4px;
}

.wl-item:hover,
.wl-item.active {
  background: var(--el-fill-color-light);
}

.wl-symbol {
  font-weight: 600;
  min-width: 56px;
}

.wl-name {
  flex: 1;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
