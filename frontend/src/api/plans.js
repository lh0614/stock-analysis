import { createApiClient } from './http.js'

const api = createApiClient('/plans')

export default {
  list(status) {
    return api.get('', { params: { status } }).then((r) => r.data)
  },
  create(body) {
    return api.post('', body).then((r) => r.data)
  },
  detail(planId) {
    return api.get(`/${planId}`).then((r) => r.data)
  },
  patch(planId, body) {
    return api.patch(`/${planId}`, body).then((r) => r.data)
  },
  bindAlerts(planId) {
    return api.post(`/${planId}/alerts`).then((r) => r.data)
  }
}
