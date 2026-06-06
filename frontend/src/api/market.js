import { createApiClient } from './http.js'

const api = createApiClient('/market')

export default {
  regime() {
    return api.get('/regime').then((r) => r.data)
  },
  indices() {
    return api.get('/indices').then((r) => r.data)
  },
  breadth() {
    return api.get('/breadth').then((r) => r.data)
  },
  sectors() {
    return api.get('/sectors').then((r) => r.data)
  }
}
