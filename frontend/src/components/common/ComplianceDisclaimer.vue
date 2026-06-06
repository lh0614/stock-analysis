<template>
  <el-alert
    class="disclaimer"
    :title="text"
    type="warning"
    :closable="false"
    show-icon
  />
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: '分析结论仅供研究和复盘，不构成投资建议；系统不提供实盘交易能力。'
  }
})
</script>

<style scoped>
.disclaimer {
  margin-bottom: 12px;
}
</style>
