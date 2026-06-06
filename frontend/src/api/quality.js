import { createApiClient } from './http.js'

const api = createApiClient('/quality')

export default {
  summary() {
    return api.get('/summary').then((r) => r.data)
  },
  symbol(symbol) {
    return api.get(`/symbol/${symbol}`).then((r) => r.data)
  },
  conflicts(limit = 100) {
    return api.get('/conflicts', { params: { limit } }).then((r) => r.data)
  },
  missingBars(limit = 100) {
    return api.get('/missing-bars', { params: { limit } }).then((r) => r.data)
  }
}
