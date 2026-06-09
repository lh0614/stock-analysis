import { createApiClient } from './http.js'

const api = createApiClient('/portfolio')

export default {
  simulated() {
    return api.get('/simulated').then((r) => r.data)
  },
  addTrade(body) {
    return api.post('/simulated-trades', body).then((r) => r.data)
  },
  importCsv(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/simulated-trades/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then((r) => r.data)
  }
}
