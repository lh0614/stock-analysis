import axios from 'axios'

const baseUrl = `${import.meta.env.VITE_API_BASE || '/api/v1'}/analysis`

const api = axios.create({
  baseURL: baseUrl,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() || ''
  for (const block of parts) {
    const line = block.split('\n').find((l) => l.startsWith('data: '))
    if (line) {
      try {
        onEvent(JSON.parse(line.slice(6)))
      } catch {
        /* ignore malformed */
      }
    }
  }
  return rest
}

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
    const response = await fetch(`${baseUrl}/run/stream`, {
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
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = parseSseChunk(buffer, (ev) => {
        onEvent(ev)
        if (ev.event === 'complete' || ev.event === 'error') {
          finalResult = ev.result
        }
      })
    }
    if (buffer) {
      parseSseChunk(buffer + '\n\n', (ev) => {
        onEvent(ev)
        if (ev.event === 'complete' || ev.event === 'error') {
          finalResult = ev.result
        }
      })
    }
    return finalResult
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
    const response = await fetch(`${baseUrl}/resume/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ run_id: runId })
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = parseSseChunk(buffer, (ev) => {
        onEvent(ev)
        if (ev.event === 'complete' || ev.event === 'error') {
          finalResult = ev.result
        }
      })
    }
    if (buffer) {
      parseSseChunk(buffer + '\n\n', (ev) => {
        onEvent(ev)
        if (ev.event === 'complete' || ev.event === 'error') {
          finalResult = ev.result
        }
      })
    }
    return finalResult
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
  }
}
