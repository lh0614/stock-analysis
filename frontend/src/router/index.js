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
          path: 'alerts',
          name: 'alerts',
          component: () => import('../views/AlertsView.vue')
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('../views/SettingsView.vue')
        }
      ]
    }
  ]
})

export default router
