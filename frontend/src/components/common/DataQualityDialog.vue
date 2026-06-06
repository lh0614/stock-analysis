<template>
  <el-dialog
    v-model="visible"
    title="数据质量问题"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="quality-issue-content">
      <el-alert
        :title="qualityInfo?.ui_hint || '数据质量异常'"
        :type="alertType"
        show-icon
        :closable="false"
      />

      <div class="issue-details">
        <h4>问题详情</h4>
        <ul>
          <li v-for="(issue, i) in issueLabels" :key="i">{{ issue }}</li>
        </ul>

        <el-descriptions :column="2" border size="small" class="mt-12">
          <el-descriptions-item label="股票代码">{{ symbol }}</el-descriptions-item>
          <el-descriptions-item label="质量等级">
            <el-tag :type="levelTagType">{{ qualityInfo?.quality_level }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据条数">
            {{ qualityInfo?.bar_count || 0 }} 条
          </el-descriptions-item>
          <el-descriptions-item label="数据时效">
            {{ qualityInfo?.stale_days || 0 }} 天前
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="qualityInfo?.can_retry" class="retry-hint">
          <el-icon class="hint-icon"><Warning /></el-icon>
          <span>{{ qualityInfo.retry_hint || '建议重新拉取数据' }}</span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button v-if="qualityInfo?.can_retry" type="primary" @click="handleRetry">
        {{ retryButtonText }}
      </el-button>
      <el-button v-else type="warning" @click="handleContinue">
        忽略并继续
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Warning } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  symbol: { type: String, default: '' },
  qualityInfo: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'retry', 'continue', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const alertType = computed(() => {
  const level = props.qualityInfo?.quality_level
  if (level === 'D') return 'error'
  if (level === 'C') return 'warning'
  return 'info'
})

const levelTagType = computed(() => {
  const level = props.qualityInfo?.quality_level
  if (level === 'D') return 'danger'
  if (level === 'C') return 'warning'
  if (level === 'B') return 'info'
  return 'success'
})

const issueLabels = computed(() => {
  const issues = props.qualityInfo?.issues || []
  const labelMap = {
    no_data: '数据缺失：缓存中无此股票数据',
    invalid_ohlc: 'OHLC 数据异常：开高低收不符合逻辑',
    ohlc_invalid: '价格逻辑错误：最高价低于收盘价或最低价高于开盘价',
    negative_volume: '成交量异常：出现负值',
    single_source: '数据来源单一：仅有一个数据源，可靠性降低',
    stale_data: '数据陈旧：超过 3 天未更新',
    data_lag: '数据延迟：1-2 天未更新'
  }
  return issues.map((issue) => {
    if (issue.startsWith('cross_source_diff_')) {
      const pct = issue.replace('cross_source_diff_', '').replace('%', '')
      return `跨源冲突：不同数据源的收盘价偏差 ${pct}%`
    }
    return labelMap[issue] || issue
  })
})

const retryButtonText = computed(() => {
  const action = props.qualityInfo?.retry_action
  if (action === 'auto_fetch') return '自动拉取数据'
  if (action === 'force_refetch') return '强制重新拉取'
  return '重试'
})

function handleRetry() {
  emit('retry', props.qualityInfo?.retry_action)
  visible.value = false
}

function handleContinue() {
  emit('continue')
  visible.value = false
}

function handleCancel() {
  emit('cancel')
  visible.value = false
}
</script>

<style scoped>
.quality-issue-content {
  padding: 12px 0;
}

.issue-details {
  margin-top: 20px;
}

.issue-details h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 12px 0;
}

.issue-details ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.retry-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: var(--el-color-warning-light-9);
  border: 1px solid var(--el-color-warning-light-7);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
}

.hint-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.mt-12 {
  margin-top: 12px;
}
</style>
