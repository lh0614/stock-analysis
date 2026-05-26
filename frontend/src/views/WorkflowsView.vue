<template>
  <div class="rb-page workflows-page">
    <h1 class="rb-page-title">工作流记忆</h1>
    <p class="rb-page-desc">配置默认指标、图表周期与分析视界</p>
    <el-card shadow="never" class="rb-card">
      <template #header>
        <div class="rb-page-header">
          <span class="rb-page-header__title">工作流列表</span>
          <div class="rb-page-header__actions">
            <el-button @click="handleExport">导出</el-button>
            <el-button @click="triggerImport">导入</el-button>
            <input
              ref="importInputRef"
              type="file"
              accept=".json,application/json"
              class="hidden-file-input"
              @change="handleImportFile"
            />
            <el-button type="primary" @click="openCreate">新建工作流</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="workflows" border>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="horizon" label="主周期" width="90">
          <template #default="{ row }">
            {{ horizonLabel(row.horizon) }}
          </template>
        </el-table-column>
        <el-table-column prop="indicators" label="指标" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="i in row.indicators" :key="i" size="small" class="tag">{{
              i
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chart_period" label="图表周期" width="100" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.workflow_type === 'builtin' ? 'info' : 'success'" size="small">
              {{ row.workflow_type === 'builtin' ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="setDefault(row)">设为默认</el-button>
            <el-button
              v-if="row.workflow_type !== 'builtin'"
              link
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="row.workflow_type !== 'builtin'"
              link
              type="danger"
              @click="remove(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑工作流' : '新建工作流'"
      width="480px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：我的波段模板" />
        </el-form-item>
        <el-form-item label="主周期">
          <el-select v-model="form.horizon">
            <el-option label="短线" value="short" />
            <el-option label="中线" value="medium" />
            <el-option label="长线" value="long" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标">
          <el-checkbox-group v-model="form.indicators">
            <el-checkbox label="ma">MA</el-checkbox>
            <el-checkbox label="macd">MACD</el-checkbox>
            <el-checkbox label="rsi">RSI</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="图表周期">
          <el-select v-model="form.chart_period">
            <el-option label="1个月" value="1m" />
            <el-option label="3个月" value="3m" />
            <el-option label="1年" value="1y" />
          </el-select>
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import workflowApi from '@/api/workflow.js'
import { useWorkflowStore } from '@/stores/workflow.js'

const wfStore = useWorkflowStore()
const workflows = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const importing = ref(false)
const importInputRef = ref(null)
const form = ref({
  name: '',
  horizon: 'short',
  indicators: ['ma', 'macd', 'rsi'],
  chart_period: '1y',
  is_default: false
})

const horizonLabel = (h) => ({ short: '短线', medium: '中线', long: '长线' }[h] || h)

async function load() {
  loading.value = true
  try {
    const data = await workflowApi.list()
    workflows.value = data.workflows || []
    await wfStore.fetchWorkflows()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function defaultForm() {
  return {
    name: '',
    horizon: 'short',
    indicators: ['ma', 'macd', 'rsi'],
    chart_period: '1y',
    is_default: false
  }
}

function openCreate() {
  editingId.value = null
  form.value = defaultForm()
  dialogVisible.value = true
}

function openEdit(row) {
  if (row.workflow_type === 'builtin') {
    ElMessage.info('内置工作流不可编辑，请新建自定义工作流')
    return
  }
  editingId.value = row.id
  form.value = {
    name: row.name,
    horizon: row.horizon || 'short',
    indicators: [...(row.indicators || ['ma', 'macd', 'rsi'])],
    chart_period: row.chart_period || '1y',
    is_default: !!row.is_default
  }
  dialogVisible.value = true
}

async function saveDialog() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await workflowApi.update(editingId.value, form.value)
      ElMessage.success('已保存')
    } else {
      await workflowApi.create(form.value)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    editingId.value = null
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    saving.value = false
  }
}

function triggerImport() {
  importInputRef.value?.click()
}

function validateImportPayload(data) {
  if (!data || typeof data !== 'object') return 'JSON 根节点须为对象'
  if (!Array.isArray(data.workflows)) return '缺少 workflows 数组'
  return null
}

async function handleImportFile(ev) {
  const input = ev.target
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const name = (file.name || '').toLowerCase()
  const okExt = name.endsWith('.json')
  const okMime =
    !file.type || file.type === 'application/json' || file.type === 'text/json'
  if (!okExt && !okMime) {
    ElMessage.warning('请选择 .json 格式的工作流导出文件')
    return
  }

  importing.value = true
  try {
    const text = await file.text()
    let payload
    try {
      payload = JSON.parse(text)
    } catch {
      ElMessage.error('JSON 解析失败，请检查文件内容')
      return
    }
    const err = validateImportPayload(payload)
    if (err) {
      ElMessage.warning(err)
      return
    }
    const res = await workflowApi.importAll(payload)
    const n = res.imported ?? payload.workflows.length
    ElMessage.success(`已导入 ${n} 条工作流`)
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '导入失败')
  } finally {
    importing.value = false
  }
}

async function setDefault(row) {
  await workflowApi.setDefault(row.id)
  wfStore.selectWorkflow(row.id)
  ElMessage.success(`已将「${row.name}」设为默认`)
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除工作流「${row.name}」？`, '提示', { type: 'warning' })
  await workflowApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

async function handleExport() {
  const data = await workflowApi.exportAll()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `workflows_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<style scoped>

.tag {
  margin-right: 4px;
}

.hidden-file-input {
  display: none;
}
</style>
