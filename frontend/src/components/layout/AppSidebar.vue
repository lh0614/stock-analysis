<template>
  <aside class="rb-sidebar">
    <div class="rb-sidebar__brand" @click="router.push('/')">
      <span class="rb-sidebar__logo">熊</span>
      <div class="rb-sidebar__brand-text">
        <span class="name">红熊分析</span>
        <span class="sub">Local Stock</span>
      </div>
    </div>

    <el-menu
      :default-active="activeMenu"
      :default-openeds="openedMenus"
      class="rb-menu"
      background-color="#ffffff"
      text-color="#5B6167"
      active-text-color="#155EEF"
      @select="onSelect"
    >
      <el-sub-menu
        v-for="group in menuTree"
        :key="group.index"
        :index="group.index"
      >
        <template #title>
          <el-icon v-if="group.icon">
            <component :is="icons[group.icon]" />
          </el-icon>
          <span>{{ group.title }}</span>
        </template>
        <el-menu-item
          v-for="item in group.children"
          :key="item.index"
          :index="item.index"
        >
          {{ item.title }}
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </aside>
</template>

<script setup>
import { computed, watch, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  TrendCharts,
  SetUp,
  Bell,
  Setting
} from '@element-plus/icons-vue'
import { menuTree, getOpenMenuKeys } from '@/config/menu.js'

const icons = { TrendCharts, SetUp, Bell, Setting }
const route = useRoute()
const router = useRouter()
const openedMenus = ref(getOpenMenuKeys(route.path))

const activeMenu = computed(() => {
  const p = route.path
  if (p === '/') return '/'
  return p
})

watch(
  () => route.path,
  (p) => {
    openedMenus.value = getOpenMenuKeys(p)
  }
)

function onSelect(index) {
  if (index.startsWith('group-')) return
  router.push(index)
}
</script>

<style scoped>
.rb-sidebar {
  width: var(--rb-sidebar-width);
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid var(--rb-border);
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.rb-sidebar__brand {
  height: 58px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--rb-border);
}

.rb-sidebar__logo {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  background: var(--rb-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
}

.rb-sidebar__brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.rb-sidebar__brand-text .name {
  font-size: 14px;
  font-weight: 600;
  color: var(--rb-text-dark);
}

.rb-sidebar__brand-text .sub {
  font-size: 11px;
  color: var(--rb-text-light);
}

.rb-menu {
  flex: 1;
  padding: 8px 0;
  overflow-y: auto;
}

.rb-menu :deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  font-size: 14px;
}

.rb-menu :deep(.el-menu-item) {
  height: 40px;
  line-height: 40px;
  font-size: 14px;
  padding-left: 48px !important;
}

.rb-menu :deep(.el-menu-item.is-active) {
  background: var(--rb-table-hover);
  font-weight: 600;
}
</style>
