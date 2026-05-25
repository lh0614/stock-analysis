<template>
  <div class="app-pagination">
    <el-pagination
      v-model:current-page="innerPage"
      v-model:page-size="innerSize"
      :total="total"
      :page-sizes="pageSizes"
      :layout="layout"
      :background="background"
      :hide-on-single-page="hideOnSinglePage"
      @current-change="emitPage"
      @size-change="emitSize"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
  layout: {
    type: String,
    default: 'total, sizes, prev, pager, next, jumper'
  },
  background: { type: Boolean, default: true },
  hideOnSinglePage: { type: Boolean, default: false }
})

const emit = defineEmits(['update:page', 'update:pageSize', 'change'])

const innerPage = ref(props.page)
const innerSize = ref(props.pageSize)

watch(
  () => props.page,
  (v) => {
    innerPage.value = v
  }
)
watch(
  () => props.pageSize,
  (v) => {
    innerSize.value = v
  }
)

function emitPage(p) {
  emit('update:page', p)
  emit('change', { page: p, pageSize: innerSize.value })
}

function emitSize(s) {
  innerSize.value = s
  innerPage.value = 1
  emit('update:pageSize', s)
  emit('update:page', 1)
  emit('change', { page: 1, pageSize: s })
}
</script>

<style scoped>
.app-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  flex-shrink: 0;
}
</style>
