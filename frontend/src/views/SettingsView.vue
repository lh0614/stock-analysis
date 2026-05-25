<template>
  <div class="rb-page settings-page">
    <h1 class="rb-page-title">系统设置</h1>
    <p class="rb-page-desc">数据源、工作流、智能解读与缓存管理</p>
    <el-card shadow="never" class="rb-card" v-loading="loading">
      <template #header>
        <span class="rb-page-header__title">基础配置</span>
      </template>

      <el-form class="rb-form" label-width="140px" style="max-width: 560px">
        <el-form-item label="数据源优先级">
          <el-select
            v-model="priority"
            multiple
            placeholder="按顺序尝试"
            style="width: 100%"
          >
            <el-option
              v-for="s in availableSources"
              :key="s"
              :label="sourceLabel(s)"
              :value="s"
            />
          </el-select>
          <p class="rb-hint">拉取行情时按此顺序自动 failover</p>
          <el-alert
            v-if="priority.length"
            :title="`当前顺序：${priority.join(' → ')}`"
            type="success"
            :closable="false"
            show-icon
            class="order-alert"
          />
        </el-form-item>

        <el-form-item label="默认工作流">
          <el-select v-model="defaultWorkflowId" style="width: 100%">
            <el-option
              v-for="w in workflows"
              :key="w.id"
              :label="w.name"
              :value="w.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="上次分析标的">
          <el-tag v-if="lastSymbol">{{ lastSymbol }}</el-tag>
          <span v-else class="muted">无</span>
        </el-form-item>

        <el-form-item label="智能解读">
          <el-switch
            v-model="aiInterpretation"
            active-text="开启（规则引擎）"
            inactive-text="关闭"
          />
          <p class="hint">开启后流水线完成时生成解读卡片；默认关闭，不调用外部大模型</p>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
        </el-form-item>
      </el-form>

      <el-divider>缓存管理</el-divider>
      <el-descriptions v-if="cacheInfo" :column="2" border size="small">
        <el-descriptions-item label="目录">{{ cacheInfo.cache_dir }}</el-descriptions-item>
        <el-descriptions-item label="文件数">{{ cacheInfo.file_count }}</el-descriptions-item>
        <el-descriptions-item label="占用">{{ cacheInfo.size_mb }} MB</el-descriptions-item>
      </el-descriptions>
      <div class="cache-actions">
        <el-button :loading="cacheLoading" @click="refreshCache">刷新统计</el-button>
        <el-button :loading="cacheLoading" @click="clearPickles">清理行情缓存</el-button>
        <el-button type="warning" :loading="cacheLoading" @click="clearAllCache">
          清理全部缓存（保留数据库）
        </el-button>
      </div>

      <el-alert
        title="本系统仅提供分析功能，不提供实盘交易。"
        type="info"
        show-icon
        :closable="false"
        class="disclaimer-alert"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import settingsApi from '@/api/settings.js'
import { useWorkflowStore } from '@/stores/workflow.js'

const wfStore = useWorkflowStore()
const loading = ref(false)
const saving = ref(false)
const priority = ref([])
const availableSources = ref([])
const defaultWorkflowId = ref('')
const workflows = ref([])
const lastSymbol = ref('')
const aiInterpretation = ref(false)
const cacheInfo = ref(null)
const cacheLoading = ref(false)

const sourceLabel = (s) =>
  ({ eastmoney: '东方财富', akshare: 'AKShare', baostock: 'Baostock' }[s] || s)

async function load() {
  loading.value = true
  try {
    const data = await settingsApi.get()
    priority.value = data.data_source_priority || []
    availableSources.value = data.available_sources || []
    defaultWorkflowId.value = data.default_workflow?.id || ''
    lastSymbol.value = data.last_symbol || ''
    aiInterpretation.value = !!data.ai_interpretation_enabled
    await wfStore.fetchWorkflows()
    workflows.value = wfStore.workflows
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await settingsApi.update({
      data_source_priority: priority.value,
      default_workflow_id: defaultWorkflowId.value,
      ai_interpretation_enabled: aiInterpretation.value
    })
    wfStore.selectWorkflow(defaultWorkflowId.value)
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    saving.value = false
  }
}

async function refreshCache() {
  cacheLoading.value = true
  try {
    const res = await settingsApi.cacheStats()
    cacheInfo.value = res
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    cacheLoading.value = false
  }
}

async function clearPickles() {
  cacheLoading.value = true
  try {
    cacheInfo.value = await settingsApi.clearPickles()
    ElMessage.success('行情 Pickle 缓存已清理')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    cacheLoading.value = false
  }
}

async function clearAllCache() {
  cacheLoading.value = true
  try {
    cacheInfo.value = await settingsApi.clearAllCache()
    ElMessage.success('已清理（SQLite 数据库保留）')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    cacheLoading.value = false
  }
}

onMounted(async () => {
  await load()
  await refreshCache()
})
</script>

<style scoped>

.muted {
  color: var(--el-text-color-placeholder);
}

.order-alert {
  margin-top: 8px;
}

.cache-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 20px;
}

.disclaimer-alert {
  margin-top: 16px;
}
</style>
