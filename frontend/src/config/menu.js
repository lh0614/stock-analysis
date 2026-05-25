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
      { index: '/screener', title: '选股器', route: '/screener' }
    ]
  },
  {
    index: 'group-strategy',
    title: '策略配置',
    icon: 'SetUp',
    children: [
      { index: '/workflows', title: '工作流记忆', route: '/workflows' },
      { index: '/strategies', title: '策略工坊', route: '/strategies' }
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
    children: [{ index: '/settings', title: '系统设置', route: '/settings' }]
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
  '/workflows': {
    title: '工作流记忆',
    breadcrumb: [{ title: '策略配置' }, { title: '工作流记忆', path: '/workflows' }]
  },
  '/strategies': {
    title: '策略工坊',
    breadcrumb: [{ title: '策略配置' }, { title: '策略工坊', path: '/strategies' }]
  },
  '/alerts': {
    title: '预警中心',
    breadcrumb: [{ title: '监控预警' }, { title: '预警中心', path: '/alerts' }]
  },
  '/settings': {
    title: '系统设置',
    breadcrumb: [{ title: '系统管理' }, { title: '系统设置', path: '/settings' }]
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
