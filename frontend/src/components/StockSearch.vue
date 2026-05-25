<template>
  <div class="search-section">
    <el-card class="search-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>🔍 股票查询</span>
        </div>
      </template>

      <div class="search-form">
        <div class="search-input-group">
          <el-input
            :model-value="searchSymbol"
            @update:model-value="$emit('update:searchSymbol', $event)"
            placeholder="请输入股票代码，如：000001（平安银行）、600519（茅台）"
            size="large"
            @keyup.enter="handleSearch"
            clearable
          >
            <template #prepend>
              <span class="input-label">股票代码</span>
            </template>
          </el-input>

          <div class="search-buttons">
            <el-button
              type="primary"
              size="large"
              @click="handleSearch"
              :loading="searchLoading"
              :icon="Search"
            >
              查询
            </el-button>

            <el-button
              type="info"
              size="large"
              @click="$emit('show-example')"
              :icon="Collection"
            >
              示例股票
            </el-button>

            <el-button
              type="warning"
              size="large"
              @click="$emit('refresh')"
              :loading="refreshing"
              :icon="Refresh"
              :disabled="!currentSymbol"
            >
              刷新
            </el-button>
          </div>
        </div>

        <div class="example-stocks">
          <p class="example-title">常用股票示例：</p>
          <div class="stock-tags">
            <el-tag
              v-for="stock in exampleStocks"
              :key="stock.code"
              class="stock-tag"
              :type="stock.type"
              @click="$emit('select-example', stock.code)"
              effect="light"
              round
            >
              {{ stock.name }} ({{ stock.code }})
            </el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { Search, Collection, Refresh } from '@element-plus/icons-vue'

defineProps({
  searchSymbol: {
    type: String,
    default: ''
  },
  currentSymbol: {
    type: String,
    default: ''
  },
  searchLoading: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  },
  exampleStocks: {
    type: Array,
    default: () => []
  }
})

defineEmits(['update:searchSymbol', 'search', 'show-example', 'select-example', 'refresh'])

const handleSearch = () => {
  const event = new CustomEvent('search')
  window.dispatchEvent(event)
}
</script>
