<template>
  <el-card shadow="never" class="rb-card analysis-toolbar">
    <el-form :inline="true">
      <el-form-item label="工作流">
        <el-select
          :model-value="workflowId"
          placeholder="选择工作流"
          style="width: 180px"
          @update:model-value="$emit('update:workflowId', $event)"
        >
          <el-option
            v-for="w in workflows"
            :key="w.id"
            :label="w.name + (w.is_default ? ' (默认)' : '')"
            :value="w.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="策略">
        <el-select
          :model-value="strategyId"
          placeholder="选择策略"
          style="width: 200px"
          @update:model-value="$emit('update:strategyId', $event)"
        >
          <el-option
            v-for="s in strategies"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="$emit('run')">
          运行分析
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
defineProps({
  workflows: { type: Array, default: () => [] },
  strategies: { type: Array, default: () => [] },
  workflowId: { type: String, default: '' },
  strategyId: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

defineEmits(['update:workflowId', 'update:strategyId', 'run'])
</script>

<style scoped>
.analysis-toolbar {
  margin-bottom: 16px;
}

.analysis-toolbar :deep(.el-form-item) {
  margin-bottom: 0;
}
</style>
