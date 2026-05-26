import { createApiClient } from './http.js'

const api = createApiClient('/sync-scheduler', { timeout: 120000 })

export default {
  status() {
    return api.get('/status').then((r) => r.data)
  },
  saveConfig(body) {
    return api.put('/config', body).then((r) => r.data)
  },
  runNow() {
    return api.post('/run').then((r) => r.data)
  }
}
