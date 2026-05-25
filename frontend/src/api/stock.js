// frontend/src/api/stock.js
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE || '/api/v1'

const stockApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export default {
  // 获取股票数据
  async getStockData(symbol, startDate = null, endDate = null, dataSource = null) {
    const params = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    if (dataSource) params.data_source = dataSource

    const response = await stockApi.get(`/stocks/${symbol}`, { params })
    return response.data
  },

  // 获取技术指标
  async getTechnicalIndicators(symbol, indicators = 'ma,macd,rsi') {
    const response = await stockApi.get(`/stocks/${symbol}/indicators`, {
      params: { indicators }
    })
    return response.data
  },

  // 获取股票摘要
  async getStockSummary(symbol) {
    const response = await stockApi.get(`/stocks/${symbol}/summary`)
    return response.data
  },

  exportDownloadUrl(symbol, format = 'csv', includeIndicators = true) {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const params = new URLSearchParams({
      format,
      include_indicators: includeIndicators
    })
    return `${base}/stocks/${symbol}/export?${params}`
  },

  // 健康检查
  async healthCheck() {
    try {
      const response = await stockApi.get('/health')
      return response.data
    } catch (error) {
      return { status: 'unhealthy', error: error.message }
    }
  }
}
