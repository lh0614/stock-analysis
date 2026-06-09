import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('../views/HomeView.vue')
        },
        {
          path: 'workflows',
          name: 'workflows',
          component: () => import('../views/WorkflowsView.vue')
        },
        {
          path: 'strategies',
          name: 'strategies',
          component: () => import('../views/StrategiesView.vue')
        },
        {
          path: 'screener',
          name: 'screener',
          component: () => import('../views/ScreenerView.vue')
        },
        {
          path: 'intelligent-screener',
          name: 'intelligent-screener',
          component: () => import('../views/IntelligentScreenerView.vue')
        },
        {
          path: 'strategy-library',
          name: 'strategy-library',
          component: () => import('../views/StrategyLibraryView.vue')
        },
        {
          path: 'stock-deep-analysis',
          name: 'stock-deep-analysis',
          component: () => import('../views/StockDeepAnalysisView.vue')
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: () => import('../views/AlertsView.vue')
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('../views/SettingsView.vue')
        },
        {
          path: 'sync-scheduler',
          name: 'sync-scheduler',
          component: () => import('../views/SyncSchedulerView.vue')
        },
        {
          path: 'data-quality',
          name: 'data-quality',
          component: () => import('../views/DataQualityView.vue')
        },
        {
          path: 'backtests',
          name: 'backtests',
          component: () => import('../views/BacktestView.vue')
        },
        {
          path: 'trade-plans',
          name: 'trade-plans',
          component: () => import('../views/TradePlansView.vue')
        },
        {
          path: 'portfolio-sim',
          name: 'portfolio-sim',
          component: () => import('../views/PortfolioSimView.vue')
        },
        {
          path: 'reviews',
          name: 'reviews',
          component: () => import('../views/ReviewCenterView.vue')
        },
        {
          path: 'market',
          name: 'market',
          component: () => import('../views/MarketEnvironmentView.vue')
        },
        {
          path: 'p2-research',
          name: 'p2-research',
          component: () => import('../views/P2ResearchView.vue')
        },
        {
          path: 'system-status',
          name: 'system-status',
          component: () => import('../views/SystemStatusView.vue')
        }
      ]
    }
  ]
})

export default router
