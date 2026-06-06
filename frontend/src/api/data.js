import { API_BASE_URL, createApiClient } from './http.js'
import { readSseStream } from './sse.js'

const api = createApiClient('/data', { timeout: 300000 })

export default {
  status() {
    return api.get('/status').then((r) => r.data)
  },
  coverage() {
    return api.get('/coverage').then((r) => r.data)
  },
  syncUniverse() {
    return api.post('/sync/universe').then((r) => r.data)
  },
  syncDailyBars(body) {
    return api.post('/sync/daily-bars', body).then((r) => r.data)
  },
  job(jobId) {
    return api.get(`/jobs/${jobId}`).then((r) => r.data)
  },
  async syncDailyBarsStream(body, onEvent) {
    const response = await fetch(`${API_BASE_URL}/data/sync/daily-bars/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body || {})
    })
    if (!response.ok) throw new Error(await response.text())
    return readSseStream(response, {
      onEvent,
      isFinalEvent: (ev) => ev.event === 'complete'
    })
  }
}
