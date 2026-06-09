import { createApiClient } from './http.js'

const prediction = createApiClient('/prediction', { timeout: 300000 })
const environment = createApiClient('/strategy-environment')
const portfolioRisk = createApiClient('/portfolio-risk')

export default {
  trainPrediction(body) {
    return prediction.post('/train', body).then((r) => r.data)
  },
  predictStock(body) {
    return prediction.post('/predict', body).then((r) => r.data)
  },
  predictionModelInfo() {
    return prediction.get('/model-info').then((r) => r.data)
  },
  predictionModelMetrics() {
    return prediction.get('/model-metrics').then((r) => r.data)
  },
  classifyEnvironment(spec) {
    return environment.post('/classify', { spec }).then((r) => r.data)
  },
  strategyFit(strategyId) {
    return environment.get(`/strategy-fit/${strategyId}`).then((r) => r.data)
  },
  marketState() {
    return environment.get('/market-state').then((r) => r.data)
  },
  portfolioReport(body) {
    return portfolioRisk.post('/generate-report', body).then((r) => r.data)
  }
}
