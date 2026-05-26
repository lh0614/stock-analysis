<template>
  <div class="header-section">
    <div class="header-content">
      <h1 class="rb-card-header-title app-header__title">
        <el-icon><TrendCharts /></el-icon>
        <span>股票分析系统</span>
      </h1>
      <p class="subtitle">短 / 中 / 长线分析 · 可配置工作流与策略</p>
    </div>
    <el-tag type="info" size="large">v1.2</el-tag>
  </div>
</template>

<script setup>
import { TrendCharts } from '@element-plus/icons-vue'
</script>

<style scoped>
.header-section {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.app-header__title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 8px;
}

.app-header__title .el-icon {
  font-size: 1.35rem;
}

.subtitle {
  margin: 0;
  color: var(--rb-text-mid, var(--el-text-color-secondary));
  font-size: 0.95rem;
}
</style>
