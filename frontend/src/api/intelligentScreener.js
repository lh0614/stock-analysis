// frontend/src/api/intelligentScreener.js
import request from '@/utils/request'

/**
 * 智能选股 API
 */
const intelligentScreenerApi = {
  /**
   * 解析自然语言选股要求
   * @param {string} text - 用户选股要求
   */
  parseIntent(text, overrides = null, useLlm = true) {
    return request({
      url: '/api/v1/intents/parse',
      method: 'post',
      data: { text, overrides, use_llm: useLlm }
    })
  },

  clarifyIntent(text) {
    return request({
      url: '/api/v1/intents/clarify',
      method: 'post',
      data: { text }
    })
  },

  generateStrategies(text, count = 4, useLlm = true) {
    return request({
      url: '/api/v1/intents/generate-strategies',
      method: 'post',
      data: { text, count, use_llm: useLlm }
    })
  },

  validateSpec(strategySpec) {
    return request({
      url: '/api/v1/intents/validate-spec',
      method: 'post',
      data: { strategy_spec: strategySpec }
    })
  },

  batchBacktest(strategySpecs, saveRecommended = false, topN = 2) {
    return request({
      url: '/api/v1/strategy-optimizer/batch-backtest',
      method: 'post',
      data: {
        strategy_specs: strategySpecs,
        save_recommended: saveRecommended,
        top_n: topN
      }
    })
  },

  /**
   * 执行智能选股
   * @param {Object} strategySpec - 策略规格
   */
  runScreener(strategySpec) {
    return request({
      url: '/api/v1/intelligent-screener/run',
      method: 'post',
      data: { strategy_spec: strategySpec }
    })
  },

  /**
   * 获取选股运行结果
   * @param {string} runId - 运行ID
   */
  getScreenerRun(runId) {
    return request({
      url: `/api/v1/intelligent-screener/runs/${runId}`,
      method: 'get'
    })
  },

  /**
   * 保存选股结果为策略
   * @param {string} runId - 运行ID
   */
  saveAsStrategy(runId) {
    return request({
      url: `/api/v1/intelligent-screener/runs/${runId}/save-strategy`,
      method: 'post'
    })
  }
}

export default intelligentScreenerApi
