<template>
  <div class="backend-state" :class="`backend-state--${resolvedType}`">
    <el-icon class="backend-state__icon" :size="28">
      <component :is="iconComponent" />
    </el-icon>
    <div class="backend-state__body">
      <p class="backend-state__title">{{ title }}</p>
      <p v-if="description" class="backend-state__desc">{{ description }}</p>
      <el-button
        v-if="showRetry"
        type="primary"
        size="small"
        :loading="retrying"
        @click="emit('retry')"
      >
        重试
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Connection, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  type: {
    type: String,
    default: 'offline',
    validator: (v) => ['offline', 'error'].includes(v)
  },
  status: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  showRetry: {
    type: Boolean,
    default: true
  },
  retrying: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['retry'])

const resolvedType = computed(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'offline') return 'offline'
  return props.type
})

const iconComponent = computed(() =>
  resolvedType.value === 'error' ? WarningFilled : Connection
)
</script>

<style scoped>
.backend-state {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}

.backend-state--offline {
  border-color: var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
}

.backend-state--offline .backend-state__icon {
  color: var(--el-color-warning);
}

.backend-state--error {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
}

.backend-state--error .backend-state__icon {
  color: var(--el-color-danger);
}

.backend-state__body {
  flex: 1;
  min-width: 0;
}

.backend-state__title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--rb-text-dark, var(--el-text-color-primary));
}

.backend-state__desc {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--rb-text-mid, var(--el-text-color-regular));
}

.backend-state__body .el-button {
  margin-top: 2px;
}
</style>
