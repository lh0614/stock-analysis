<template>
  <div class="rb-page strategies-page">
    <h1 class="rb-page-title">策略工坊</h1>
    <p class="rb-page-desc">上传、版本管理与参数修正（内置策略可调参）</p>
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" class="rb-card">
          <template #header>
            <div class="rb-page-header">
              <span class="rb-page-header__title">策略列表</span>
              <div class="rb-page-header__actions">
                <el-upload
                :show-file-list="false"
                :http-request="handleUpload"
                accept=".py,.zip"
              >
                <el-button type="primary">上传策略 (.py / .zip)</el-button>
              </el-upload>
              </div>
            </div>
          </template>

          <el-table
            v-loading="loading"
            :data="strategies"
            highlight-current-row
            @current-change="onSelect"
          >
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="version" label="版本" width="90" />
            <el-table-column label="周期" width="120">
              <template #default="{ row }">
                <el-tag v-for="h in row.horizons" :key="h" size="small">{{ h }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                {{ row.is_builtin ? '内置' : '自定义' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  v-if="!row.is_builtin"
                  link
                  type="danger"
                  @click.stop="remove(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card v-if="current" shadow="never" class="rb-card">
          <template #header>策略详情 · {{ current.name }}</template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ current.version }}</el-descriptions-item>
          </el-descriptions>

          <el-divider>修正参数</el-divider>
          <el-form label-width="80px">
            <el-form-item label="RSI超买">
              <el-slider v-model="reviseParams.rsi_high" :min="60" :max="90" show-input />
            </el-form-item>
            <el-form-item label="RSI超卖">
              <el-slider v-model="reviseParams.rsi_low" :min="10" :max="40" show-input />
            </el-form-item>
            <el-form-item label="MACD权重">
              <el-input-number v-model="reviseParams.macd_weight" :step="0.1" :min="0" :max="1" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="reviseNote" type="textarea" rows="2" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitRevise">
                {{ current.is_builtin ? '保存参数' : '保存修正（新版本）' }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider>修订历史</el-divider>
          <el-timeline v-if="revisions.length">
            <el-timeline-item
              v-for="r in revisions"
              :key="r.id"
              :timestamp="r.created_at"
            >
              v{{ r.version }} — {{ r.note }}
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无修订记录" />
        </el-card>
        <el-empty v-else description="选择左侧策略查看详情" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import strategyApi from '@/api/strategy.js'
import { useWorkflowStore } from '@/stores/workflow.js'

const wfStore = useWorkflowStore()
const strategies = ref([])
const loading = ref(false)
const current = ref(null)
const revisions = ref([])
const reviseParams = ref({ rsi_high: 70, rsi_low: 30, macd_weight: 0.4 })
const reviseNote = ref('')

async function load() {
  loading.value = true
  try {
    const data = await strategyApi.list()
    strategies.value = data.strategies || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function onSelect(row) {
  current.value = row
  if (!row) return
  try {
    const data = await strategyApi.versions(row.id)
    revisions.value = data.revisions || []
    const latest = revisions.value[0]
    if (latest?.params) {
      reviseParams.value = { ...reviseParams.value, ...latest.params }
    }
  } catch {
    revisions.value = []
  }
}

async function handleUpload({ file }) {
  try {
    const s = await strategyApi.upload(file)
    ElMessage.success(`上传成功：${s.name}`)
    wfStore.selectStrategy(s.id)
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

async function submitRevise() {
  if (!current.value) return
  try {
    await strategyApi.revise(current.value.id, reviseParams.value, reviseNote.value)
    ElMessage.success('已保存新版本')
    reviseNote.value = ''
    await load()
    const updated = strategies.value.find((s) => s.id === current.value.id)
    if (updated) onSelect(updated)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`删除策略「${row.name}」？`, '提示', { type: 'warning' })
  await strategyApi.remove(row.id)
  ElMessage.success('已删除')
  current.value = null
  await load()
}

onMounted(load)
</script>

<style scoped>
</style>
