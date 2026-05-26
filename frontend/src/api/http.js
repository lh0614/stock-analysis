import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE || '/api/v1'

export function createApiClient(path, options = {}) {
  return axios.create({
    baseURL: `${API_BASE_URL}${path}`,
    ...options
  })
}
