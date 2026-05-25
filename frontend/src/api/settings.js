import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE || '/api/v1'}/settings`,
  timeout: 15000
})

export default {
  get() {
    return api.get('').then((r) => r.data)
  },
  update(data) {
    return api.put('', data).then((r) => r.data)
  },
  cacheStats() {
    return api.get('/cache').then((r) => r.data)
  },
  clearPickles() {
    return api.post('/cache/clear-pickles').then((r) => r.data)
  },
  clearAllCache() {
    return api.post('/cache/clear-all').then((r) => r.data)
  }
}
