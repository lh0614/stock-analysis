<template>
  <el-card v-if="data" class="rb-card interp-card" shadow="never">
    <template #header>
      <span>智能解读</span>
      <el-tag size="small" type="info">规则引擎</el-tag>
    </template>
    <el-alert :title="data.summary" type="info" :closable="false" show-icon />
    <el-divider />
    <div v-for="sec in data.sections" :key="sec.horizon" class="sec-block">
      <h4>{{ sec.label }}</h4>
      <p>{{ sec.text }}</p>
    </div>
    <el-collapse v-if="data.citations?.length">
      <el-collapse-item title="数据引用" name="cite">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item
            v-for="(c, i) in data.citations"
            :key="i"
            :label="c.source"
          >
            {{ c.field }} = {{ c.value }}
          </el-descriptions-item>
        </el-descriptions>
      </el-collapse-item>
    </el-collapse>
    <p class="disclaimer">{{ data.disclaimer }}</p>
  </el-card>
</template>

<script setup>
defineProps({
  data: { type: Object, default: null }
})
</script>

<style scoped>
.interp-card {
  margin-bottom: 20px;
}

.sec-block {
  margin-bottom: 12px;
}

.sec-block h4 {
  margin: 0 0 6px;
  font-size: 14px;
}

.sec-block p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

.disclaimer {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 12px;
}
</style>
