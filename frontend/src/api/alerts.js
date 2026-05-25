import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE || '/api/v1'}/alerts`,
  timeout: 120000
})

export default {
  rules() {
    return api.get('/rules').then((r) => r.data)
  },
  list(symbol = null) {
    return api.get('', { params: symbol ? { symbol } : {} }).then((r) => r.data)
  },
  create(body) {
    return api.post('', body).then((r) => r.data)
  },
  update(id, body) {
    return api.put(`/${id}`, body).then((r) => r.data)
  },
  remove(id) {
    return api.delete(`/${id}`).then((r) => r.data)
  },
  events(limit = 50) {
    return api.get('/events', { params: { limit } }).then((r) => r.data)
  },
  evaluate() {
    return api.post('/evaluate').then((r) => r.data)
  }
}
