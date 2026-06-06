<template>
  <el-card class="rb-card direction-cards" shadow="never">
    <template #header>
      <span>分析方向</span>
      <el-tag v-if="loading" type="info" size="small">计算中</el-tag>
    </template>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="3" animated />
    </div>

    <el-alert v-else-if="error" :title="error" type="warning" show-icon :closable="false" />

    <template v-else>
      <QualityBanner v-if="qualityLevel" :level="qualityLevel" :hint="qualityHint" />

      <el-row v-if="directions && !directionBlocked" :gutter="16">
      <el-col v-for="item in cards" :key="item.key" :xs="24" :sm="8">
        <div class="direction-item" :class="item.bias">
          <div class="dir-header">
            <span class="horizon">{{ item.label }}</span>
            <el-tag :type="item.tagType" effect="dark" size="small">{{ item.biasLabel }}</el-tag>
          </div>
          <el-progress
            :percentage="item.confidence"
            :color="item.progressColor"
            :stroke-width="8"
          />
          <p class="summary">{{ item.summary }}</p>
          <ul v-if="item.evidence?.length" class="evidence">
            <li v-for="(ev, i) in item.evidence.slice(0, 3)" :key="i">
              {{ ev.name }}：{{ ev.value }}
            </li>
          </ul>
          <el-alert
            v-if="item.contradictions?.length"
            :title="item.contradictions[0]"
            type="info"
            :closable="false"
            show-icon
            class="contra"
          />
        </div>
      </el-col>
      </el-row>

      <el-empty v-else-if="directionBlocked" description="数据质量 D 级，已阻断方向结论" />

      <el-empty v-else description="暂无方向数据" />
    </template>

    <p class="disclaimer">分析结论仅供研究和复盘，不构成投资建议；系统不提供实盘交易能力。</p>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import QualityBanner from '@/components/common/QualityBanner.vue'

const props = defineProps({
  directions: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  qualityLevel: { type: String, default: '' },
  qualityHint: { type: String, default: '' }
})

const directionBlocked = computed(() => {
  if (props.qualityLevel === 'D') return true
  const d = props.directions
  return d?.short?.bias === 'blocked' || d?.medium?.bias === 'blocked'
})

const HORIZON_META = {
  short: { label: '短线', key: 'short' },
  medium: { label: '中线', key: 'medium' },
  long: { label: '长线', key: 'long' }
}

const tagMap = { bullish: 'danger', bearish: 'success', neutral: 'info' }
const progressMap = { bullish: '#f56c6c', bearish: '#67c23a', neutral: '#909399' }

const cards = computed(() => {
  if (!props.directions) return []
  return Object.values(HORIZON_META)
    .map((meta) => {
      const d = props.directions[meta.key]
      if (!d) return null
      return {
        key: meta.key,
        label: meta.label,
        bias: d.bias,
        biasLabel: d.bias_label || d.bias,
        tagType: tagMap[d.bias] || 'info',
        confidence: d.confidence ?? 50,
        progressColor: progressMap[d.bias],
        summary: d.summary,
        evidence: d.evidence,
        contradictions: d.contradictions
      }
    })
    .filter(Boolean)
})
</script>

<style scoped>
.direction-cards :deep(.el-card__header) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.direction-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  min-height: 200px;
  background: var(--el-fill-color-blank);
}

.direction-item.bullish {
  border-top: 3px solid #f56c6c;
}

.direction-item.bearish {
  border-top: 3px solid #67c23a;
}

.direction-item.neutral {
  border-top: 3px solid #909399;
}

.dir-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.horizon {
  font-weight: 600;
  font-size: 15px;
}

.summary {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 10px 0 6px;
}

.evidence {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.contra {
  margin-top: 8px;
}

.disclaimer {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
}

.loading-wrap {
  padding: 8px 0;
}
</style>
