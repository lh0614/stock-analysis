import { createApiClient } from './http.js'

const api = createApiClient('/backtests', { timeout: 300000 })

export default {
  run(body) {
    return api.post('/run', body).then((r) => r.data)
  },
  runs(limit = 50) {
    return api.get('/runs', { params: { limit } }).then((r) => r.data)
  },
  runDetail(runId) {
    return api.get(`/runs/${runId}`).then((r) => r.data)
  },
  trades(runId) {
    return api.get(`/runs/${runId}/trades`).then((r) => r.data)
  },
  export(runId, fmt = 'json') {
    return api.get(`/runs/${runId}/export`, { params: { fmt } }).then((r) => r.data)
  },
  compare(runIds) {
    return api.post(`/compare`, runIds).then((r) => r.data)
  }
}
