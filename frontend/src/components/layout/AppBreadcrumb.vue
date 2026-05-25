<template>
  <header class="rb-breadcrumb-bar">
    <el-breadcrumb separator="/">
      <el-breadcrumb-item
        v-for="(item, idx) in items"
        :key="idx"
        :to="item.path && idx < items.length - 1 ? { path: item.path } : undefined"
      >
        {{ item.title }}
      </el-breadcrumb-item>
    </el-breadcrumb>

    <div class="rb-breadcrumb-bar__extra">
      <slot name="extra" />
      <el-tag
        :type="backendStatus === 'healthy' ? 'success' : 'danger'"
        size="small"
        effect="plain"
      >
        {{ backendStatus === 'healthy' ? '服务正常' : '服务异常' }}
      </el-tag>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { getBreadcrumb } from '@/config/menu.js'

defineProps({
  backendStatus: { type: String, default: 'unknown' }
})

const route = useRoute()
const items = computed(() => getBreadcrumb(route.path))
</script>

<style scoped>
.rb-breadcrumb-bar {
  height: var(--rb-breadcrumb-height);
  min-height: var(--rb-breadcrumb-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--rb-border);
}

.rb-breadcrumb-bar :deep(.el-breadcrumb__inner),
.rb-breadcrumb-bar :deep(.el-breadcrumb__item) {
  font-size: 14px;
  color: var(--rb-text-mid);
}

.rb-breadcrumb-bar :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--rb-text-dark);
  font-weight: 600;
}

.rb-breadcrumb-bar__extra {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
