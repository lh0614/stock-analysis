import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import workflowApi from '@/api/workflow.js'
import { FALLBACK_WORKFLOWS } from '@/constants/fallbackWorkflows.js'

const LS_KEY = 'lsa_workflow_selection'

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref([])
  const selectedWorkflowId = ref(localStorage.getItem(LS_KEY) || '')
  const selectedStrategyId = ref('builtin_momentum')
  const loading = ref(false)
  const loadError = ref('')

  const selectedWorkflow = computed(() =>
    workflows.value.find((w) => w.id === selectedWorkflowId.value)
  )

  function ensureDefaultSelection() {
    if (!workflows.value.length) return
    const exists = workflows.value.some((w) => w.id === selectedWorkflowId.value)
    if (!exists) {
      const def = workflows.value.find((w) => w.is_default) || workflows.value[0]
      if (def) selectWorkflow(def.id)
    } else if (!selectedWorkflowId.value) {
      const def = workflows.value.find((w) => w.is_default)
      if (def) selectWorkflow(def.id)
    }
  }

  function applyFallbackWorkflows() {
    workflows.value = FALLBACK_WORKFLOWS.map((w) => ({ ...w }))
    ensureDefaultSelection()
  }

  async function fetchWorkflows() {
    loading.value = true
    loadError.value = ''
    try {
      const data = await workflowApi.list()
      workflows.value = data.workflows || []
      if (!workflows.value.length) {
        applyFallbackWorkflows()
      } else {
        ensureDefaultSelection()
      }
    } catch (err) {
      console.warn('[workflow] 加载失败，使用本地默认模板', err)
      loadError.value = err?.message || '加载工作流失败'
      applyFallbackWorkflows()
    } finally {
      loading.value = false
    }
  }

  function selectWorkflow(id) {
    selectedWorkflowId.value = id
    localStorage.setItem(LS_KEY, id)
  }

  function selectStrategy(id) {
    selectedStrategyId.value = id
    localStorage.setItem('lsa_strategy_selection', id)
  }

  function initFromStorage() {
    const s = localStorage.getItem('lsa_strategy_selection')
    if (s) selectedStrategyId.value = s
  }

  return {
    workflows,
    selectedWorkflowId,
    selectedStrategyId,
    selectedWorkflow,
    loading,
    loadError,
    fetchWorkflows,
    applyFallbackWorkflows,
    selectWorkflow,
    selectStrategy,
    initFromStorage
  }
})
