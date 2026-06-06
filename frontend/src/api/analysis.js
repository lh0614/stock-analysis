import { API_BASE_URL, createApiClient } from './http.js'
import { readSseStream } from './sse.js'

const api = createApiClient('/analysis', {
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

const isFinalEvent = (ev) => ev.event === 'complete' || ev.event === 'error'

export default {
  async runAnalysis(symbol, workflowId = null, strategyId = null) {
    const { data } = await api.post('/run', {
      symbol,
      workflow_id: workflowId,
      strategy_id: strategyId,
      auto: true
    })
    return data
  },

  /**
   * SSE 流式分析；onEvent({ event, stages, result, ... })
   * @returns {Promise<object>} 最终 complete/error 的 result
   */
  async runAnalysisStream(symbol, workflowId = null, strategyId = null, onEvent = () => {}) {
    const response = await fetch(`${API_BASE_URL}/analysis/run/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        symbol,
        workflow_id: workflowId,
        strategy_id: strategyId,
        auto: true
      })
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `HTTP ${response.status}`)
    }
    return readSseStream(response, { onEvent, isFinalEvent, flushRemainder: true })
  },

  listRuns(symbol = null, limit = 20) {
    return api.get('/runs', { params: { symbol, limit } }).then((r) => r.data)
  },

  async getRun(runId) {
    const { data } = await api.get(`/runs/${runId}`)
    return data
  },

  async getCheckpoint(symbol) {
    const { data } = await api.get('/checkpoint', { params: { symbol } })
    return data
  },

  async resumeAnalysisStream(runId, onEvent = () => {}) {
    const response = await fetch(`${API_BASE_URL}/analysis/resume/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ run_id: runId })
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `HTTP ${response.status}`)
    }
    return readSseStream(response, { onEvent, isFinalEvent, flushRemainder: true })
  },

  async getDirection(symbol) {
    const { data } = await api.get(`/${symbol}/direction`)
    return data
  },

  async getPriceLevels(symbol) {
    const { data } = await api.get(`/${symbol}/price-levels`)
    return data
  },

  async getForecast(symbol, horizon = 'short') {
    const { data } = await api.get(`/${symbol}/forecast`, { params: { horizon } })
    return data
  },

  async refetchAndAnalyze(symbol, workflowId = null, strategyId = null) {
    const { data } = await api.post('/refetch', {
      symbol,
      workflow_id: workflowId,
      strategy_id: strategyId,
      auto: true
    })
    return data
  }
}
