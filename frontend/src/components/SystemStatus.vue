<template>
  <el-card class="status-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span class="rb-card-header-title">
          <el-icon><Monitor /></el-icon>
          <span>系统状态</span>
        </span>
      </div>
    </template>

    <div class="status-content">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="后端服务状态">
          <el-tag :type="backendStatus === 'healthy' ? 'success' : 'danger'" size="small">
            {{ backendStatus }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="API服务地址">
          <el-tag type="info" size="small">{{ apiUrl }}</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="当前分析股票">
          <el-tag type="primary" size="small">{{ currentSymbol || '--' }}</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="数据更新时间">
          <el-tag type="info" size="small">{{ lastUpdateTime || '--' }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="status-actions">
        <el-button
          @click="$emit('check-status')"
          :loading="checkingStatus"
          size="small"
          :icon="Connection"
        >
          检查后端连接
        </el-button>

        <el-button
          @click="$emit('clear-data')"
          type="warning"
          size="small"
          :icon="Delete"
        >
          清除数据
        </el-button>

        <el-button
          @click="$emit('export-data')"
          type="success"
          size="small"
          :icon="Download"
          :disabled="!currentSymbol"
        >
          导出数据
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { Connection, Delete, Download, Monitor } from '@element-plus/icons-vue'

defineProps({
  backendStatus: {
    type: String,
    default: 'unknown'
  },
  apiUrl: {
    type: String,
    default: 'http://localhost:8000'
  },
  currentSymbol: {
    type: String,
    default: ''
  },
  lastUpdateTime: {
    type: String,
    default: ''
  },
  checkingStatus: {
    type: Boolean,
    default: false
  }
})

defineEmits(['check-status', 'clear-data', 'export-data'])
</script>
