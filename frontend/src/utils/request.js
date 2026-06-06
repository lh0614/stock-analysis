import axios from 'axios'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 60000 // 请求超时时间
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 可以在这里添加token等
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data
    return res
  },
  error => {
    console.error('Response error:', error)

    // 处理错误响应
    const message = error.response?.data?.detail || error.message || '请求失败'

    return Promise.reject(new Error(message))
  }
)

export default service
