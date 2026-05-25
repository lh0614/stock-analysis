<template>
  <div class="rb-layout-shell">
    <AppSidebar />
    <div class="rb-layout-main">
      <AppBreadcrumb :backend-status="backendStatus">
        <template v-if="pageTitle" #extra>
          <span class="rb-breadcrumb-page-title">{{ pageTitle }}</span>
        </template>
      </AppBreadcrumb>
      <main class="rb-layout-content">
        <router-view v-slot="{ Component }">
          <transition name="rb-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppBreadcrumb from '@/components/layout/AppBreadcrumb.vue'
import { getPageTitle } from '@/config/menu.js'
import stockApi from '@/api/stock.js'

const route = useRoute()
const backendStatus = ref('unknown')

const pageTitle = computed(() => getPageTitle(route.path))

/** 仅进入应用时检查一次，不轮询 */
onMounted(async () => {
  try {
    const data = await stockApi.healthCheck()
    backendStatus.value = data.status
  } catch {
    backendStatus.value = 'error'
  }
})
</script>

<style scoped>
.rb-layout-shell {
  display: flex;
  min-height: 100vh;
  background: var(--rb-bg-page);
}

.rb-layout-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.rb-layout-content {
  flex: 1;
  padding: 16px 20px 24px;
  overflow-x: auto;
}

.rb-breadcrumb-page-title {
  font-size: 14px;
  color: var(--rb-text-light);
  margin-right: 4px;
}

.rb-fade-enter-active,
.rb-fade-leave-active {
  transition: opacity 0.15s ease;
}

.rb-fade-enter-from,
.rb-fade-leave-to {
  opacity: 0;
}
</style>
