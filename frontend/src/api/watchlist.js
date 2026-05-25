import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE || '/api/v1'}/watchlist`,
  timeout: 30000
})

export default {
  list() {
    return api.get('').then((r) => r.data)
  },
  add(symbol, groupId = 'default', name = '', note = '') {
    return api.post('/items', { symbol, group_id: groupId, name, note }).then((r) => r.data)
  },
  remove(symbol, groupId = 'default') {
    return api.delete(`/items/${symbol}`, { params: { group_id: groupId } }).then((r) => r.data)
  },
  createGroup(name) {
    return api.post('/groups', { name }).then((r) => r.data)
  }
}
