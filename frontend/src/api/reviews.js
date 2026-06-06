import { createApiClient } from './http.js'

const api = createApiClient('/reviews')

export default {
  list() {
    return api.get('').then((r) => r.data)
  },
  create(body) {
    return api.post('', body).then((r) => r.data)
  },
  stats() {
    return api.get('/stats').then((r) => r.data)
  }
}
