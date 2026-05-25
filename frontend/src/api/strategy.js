import axios from 'axios'

const base = import.meta.env.VITE_API_BASE || '/api/v1'
const api = axios.create({ baseURL: `${base}/strategies`, timeout: 60000 })

export default {
  list() {
    return api.get('').then((r) => r.data)
  },
  get(id) {
    return api.get(`/${id}`).then((r) => r.data)
  },
  upload(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then((r) => r.data)
  },
  revise(id, params, note = '') {
    return api.post(`/${id}/revise`, { params, note }).then((r) => r.data)
  },
  versions(id) {
    return api.get(`/${id}/versions`).then((r) => r.data)
  },
  run(id, symbol) {
    return api.post(`/${id}/run`, null, { params: { symbol } }).then((r) => r.data)
  },
  remove(id) {
    return api.delete(`/${id}`).then((r) => r.data)
  }
}
