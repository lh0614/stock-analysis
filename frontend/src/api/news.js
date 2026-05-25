import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE || '/api/v1'}/news`,
  timeout: 60000
})

export default {
  timeline(symbol, limit = 30) {
    return api.get(`/${symbol}/timeline`, { params: { limit } }).then((r) => r.data)
  }
}
