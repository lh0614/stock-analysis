<template>
  <el-alert
    v-if="level === 'C'"
    class="quality-banner"
    :title="cText"
    type="warning"
    show-icon
    :closable="false"
  />
  <el-alert
    v-else-if="level === 'D'"
    class="quality-banner"
    :title="dText"
    type="error"
    show-icon
    :closable="false"
  />
</template>

<script setup>
const props = defineProps({
  level: { type: String, default: '' },
  hint: { type: String, default: '' }
})

const cText =
  '数据存在单源或轻微异常，结论仅供参考'
const dText =
  '数据缺失或冲突严重，本次不生成方向结论'
</script>

<style scoped>
.quality-banner {
  margin-bottom: 12px;
}
</style>
