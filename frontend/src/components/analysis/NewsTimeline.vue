<template>
  <el-card class="rb-card news-card" shadow="never" v-loading="loading">
    <template #header>
      <span>资讯与公告</span>
      <el-button link type="primary" size="small" @click="load">刷新</el-button>
    </template>

    <el-empty v-if="!loading && !events.length" description="暂无资讯（需网络拉取）" />
    <el-timeline v-else>
      <el-timeline-item
        v-for="(ev, idx) in events"
        :key="idx"
        :timestamp="ev.published_at"
        :type="ev.type === 'announcement' ? 'warning' : 'primary'"
      >
        <el-tag size="small" class="ev-tag">{{ ev.type === 'announcement' ? '公告' : '新闻' }}</el-tag>
        <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener" class="ev-title">{{ ev.title }}</a>
        <span v-else class="ev-title">{{ ev.title }}</span>
        <div v-if="ev.source" class="ev-source">{{ ev.source }}</div>
      </el-timeline-item>
    </el-timeline>
    <p v-if="disclaimer" class="disclaimer">{{ disclaimer }}</p>
  </el-card>
</template>

<script setup>
import { ref, watch } from 'vue'
import newsApi from '@/api/news.js'

const props = defineProps({
  symbol: { type: String, required: true }
})

const loading = ref(false)
const events = ref([])
const disclaimer = ref('')

async function load() {
  if (!props.symbol) return
  loading.value = true
  try {
    const data = await newsApi.timeline(props.symbol)
    events.value = data.events || []
    disclaimer.value = data.disclaimer || ''
  } catch {
    events.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.symbol, load, { immediate: true })
</script>

<style scoped>
.news-card {
  margin-bottom: 20px;
}

.ev-tag {
  margin-right: 8px;
}

.ev-title {
  font-size: 14px;
  color: var(--el-color-primary);
  text-decoration: none;
}

.ev-source {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.disclaimer {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 12px;
}
</style>
