import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE || '/api/v1'}/workflows`,
  timeout: 30000
})

export default {
  list() {
    return api.get('').then((r) => r.data)
  },
  getDefault() {
    return api.get('/default').then((r) => r.data)
  },
  get(id) {
    return api.get(`/${id}`).then((r) => r.data)
  },
  create(data) {
    return api.post('', data).then((r) => r.data)
  },
  update(id, data) {
    return api.put(`/${id}`, data).then((r) => r.data)
  },
  remove(id) {
    return api.delete(`/${id}`).then((r) => r.data)
  },
  setDefault(id) {
    return api.post(`/${id}/default`).then((r) => r.data)
  },
  exportAll() {
    return api.get('/export').then((r) => r.data)
  },
  importAll(payload) {
    return api.post('/import', payload).then((r) => r.data)
  }
}
