/** 后端不可用时的内置工作流占位（与 SQLite 种子一致） */
export const FALLBACK_WORKFLOWS = [
  {
    id: 'builtin_short',
    name: '短线攻坚',
    workflow_type: 'builtin',
    horizon: 'short',
    indicators: ['ma', 'macd', 'rsi'],
    chart_period: '3m',
    is_default: true,
    config: {}
  },
  {
    id: 'builtin_medium',
    name: '中线波段',
    workflow_type: 'builtin',
    horizon: 'medium',
    indicators: ['ma', 'macd', 'rsi'],
    chart_period: '1y',
    is_default: false,
    config: {}
  },
  {
    id: 'builtin_long',
    name: '长线价值',
    workflow_type: 'builtin',
    horizon: 'long',
    indicators: ['ma', 'rsi'],
    chart_period: '1y',
    is_default: false,
    config: {}
  }
]
