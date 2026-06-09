/**
 * 红熊规范 — 左侧菜单（点击展开子菜单）
 */
export const menuTree = [
  {
    index: 'group-analysis',
    title: '分析中心',
    icon: 'TrendCharts',
    children: [
      { index: '/', title: '分析驾驶舱', route: '/' },
      { index: '/screener', title: '选股器', route: '/screener' },
      { index: '/intelligent-screener', title: '智能选股', route: '/intelligent-screener' },
      { index: '/stock-deep-analysis', title: '单股深度分析', route: '/stock-deep-analysis' }
    ]
  },
  {
    index: 'group-strategy',
    title: '策略配置',
    icon: 'SetUp',
    children: [
      { index: '/workflows', title: '工作流记忆', route: '/workflows' },
      { index: '/strategies', title: '策略工坊', route: '/strategies' },
      { index: '/strategy-library', title: '策略库', route: '/strategy-library' },
      { index: '/p2-research', title: 'P2预测风控', route: '/p2-research' }
    ]
  },
  {
    index: 'group-monitor',
    title: '监控预警',
    icon: 'Bell',
    children: [
      { index: '/alerts', title: '预警中心', route: '/alerts' }
    ]
  },
  {
    index: 'group-system',
    title: '系统管理',
    icon: 'Setting',
    children: [
      { index: '/system-status', title: '系统状态', route: '/system-status' },
      { index: '/sync-scheduler', title: '数据同步', route: '/sync-scheduler' },
      { index: '/data-quality', title: '数据质量', route: '/data-quality' },
      { index: '/market', title: '市场环境', route: '/market' },
      { index: '/backtests', title: '回测中心', route: '/backtests' },
      { index: '/trade-plans', title: '交易计划', route: '/trade-plans' },
      { index: '/portfolio-sim', title: '模拟组合', route: '/portfolio-sim' },
      { index: '/reviews', title: '复盘中心', route: '/reviews' },
      { index: '/settings', title: '系统设置', route: '/settings' }
    ]
  }
]

/** 路由 meta.breadcrumb 可省略，由此表生成 */
export const routeMeta = {
  '/': {
    title: '分析驾驶舱',
    breadcrumb: [{ title: '分析中心' }, { title: '分析驾驶舱', path: '/' }]
  },
  '/screener': {
    title: '选股器',
    breadcrumb: [{ title: '分析中心' }, { title: '选股器', path: '/screener' }]
  },
  '/intelligent-screener': {
    title: '智能选股',
    breadcrumb: [{ title: '分析中心' }, { title: '智能选股', path: '/intelligent-screener' }]
  },
  '/stock-deep-analysis': {
    title: '单股深度分析',
    breadcrumb: [{ title: '分析中心' }, { title: '单股深度分析', path: '/stock-deep-analysis' }]
  },
  '/workflows': {
    title: '工作流记忆',
    breadcrumb: [{ title: '策略配置' }, { title: '工作流记忆', path: '/workflows' }]
  },
  '/strategies': {
    title: '策略工坊',
    breadcrumb: [{ title: '策略配置' }, { title: '策略工坊', path: '/strategies' }]
  },
  '/strategy-library': {
    title: '策略库',
    breadcrumb: [{ title: '策略配置' }, { title: '策略库', path: '/strategy-library' }]
  },
  '/p2-research': {
    title: 'P2预测风控',
    breadcrumb: [{ title: '策略配置' }, { title: 'P2预测风控', path: '/p2-research' }]
  },
  '/alerts': {
    title: '预警中心',
    breadcrumb: [{ title: '监控预警' }, { title: '预警中心', path: '/alerts' }]
  },
  '/settings': {
    title: '系统设置',
    breadcrumb: [{ title: '系统管理' }, { title: '系统设置', path: '/settings' }]
  },
  '/sync-scheduler': {
    title: '数据同步',
    breadcrumb: [{ title: '系统管理' }, { title: '数据同步', path: '/sync-scheduler' }]
  },
  '/data-quality': {
    title: '数据质量',
    breadcrumb: [{ title: '系统管理' }, { title: '数据质量', path: '/data-quality' }]
  },
  '/market': {
    title: '市场环境',
    breadcrumb: [{ title: '系统管理' }, { title: '市场环境', path: '/market' }]
  },
  '/backtests': {
    title: '回测中心',
    breadcrumb: [{ title: '系统管理' }, { title: '回测中心', path: '/backtests' }]
  },
  '/trade-plans': {
    title: '交易计划',
    breadcrumb: [{ title: '系统管理' }, { title: '交易计划', path: '/trade-plans' }]
  },
  '/portfolio-sim': {
    title: '模拟组合',
    breadcrumb: [{ title: '系统管理' }, { title: '模拟组合', path: '/portfolio-sim' }]
  },
  '/reviews': {
    title: '复盘中心',
    breadcrumb: [{ title: '系统管理' }, { title: '复盘中心', path: '/reviews' }]
  },
  '/system-status': {
    title: '系统状态',
    breadcrumb: [{ title: '系统管理' }, { title: '系统状态', path: '/system-status' }]
  }
}

export function getOpenMenuKeys(path) {
  for (const group of menuTree) {
    if (group.children?.some((c) => c.route === path)) {
      return [group.index]
    }
  }
  return ['group-analysis']
}

export function getBreadcrumb(path) {
  return routeMeta[path]?.breadcrumb || [{ title: '首页', path: '/' }]
}

export function getPageTitle(path) {
  return routeMeta[path]?.title || '股票分析'
}
