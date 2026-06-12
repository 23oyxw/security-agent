<template>
  <div v-if="result" class="execute-panel reveal-item is-visible">
    <div class="exec-header">
      <div class="exec-meta">
        <el-tag size="small" type="success" effect="dark">核心调度代理 · L3 execute</el-tag>
        <el-tag v-if="result.plan_id" size="small" effect="plain">plan: {{ result.plan_id }}</el-tag>
        <el-tag v-if="result.degradation_level" size="small" effect="plain">
          {{ result.degradation_level }}
        </el-tag>
      </div>
      <el-link v-if="result.trace_id" type="primary" @click="$emit('trace', result.trace_id)">
        查看 Trace
      </el-link>
    </div>

    <div v-if="result.tools_used?.length" class="exec-tools">
      <span class="exec-label">已调用工具</span>
      <el-tag v-for="t in result.tools_used" :key="t" size="small" effect="plain">{{ t }}</el-tag>
    </div>

    <div v-if="result.skill_flow" class="exec-flow">
      <span class="exec-label">Skill Flow</span>
      <el-tag size="small" type="warning">{{ result.skill_flow }}</el-tag>
    </div>

    <div class="exec-reply">
      <span class="exec-label">执行摘要</span>
      <div class="exec-reply-body">{{ result.reply || '（无文本回复）' }}</div>
    </div>

    <div v-if="metaRows.length" class="exec-stats">
      <div v-for="row in metaRows" :key="row.k" class="exec-stat">
        <span class="stat-k">{{ row.k }}</span>
        <span class="stat-v">{{ row.v }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, default: null },
})

defineEmits(['trace'])

const metaRows = computed(() => {
  const r = props.result
  if (!r) return []
  const rows = []
  if (r.model_used) rows.push({ k: '模型', v: r.model_used })
  if (r.cost_tokens) rows.push({ k: 'Token', v: r.cost_tokens })
  if (r.risk_level) rows.push({ k: '风险', v: r.risk_level })
  if (r.fallback_used) rows.push({ k: '降级', v: '是' })
  return rows
})
</script>

<style scoped>
.execute-panel {
  padding: var(--space-4);
  border: 1px solid var(--color-success);
  border-radius: var(--radius-lg);
  background: var(--color-success-bg, rgba(34, 197, 94, 0.06));
  margin-bottom: var(--space-4);
}

.exec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.exec-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.exec-label {
  display: block;
  font-size: 10px;
  color: var(--color-neutral-400);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.exec-tools, .exec-flow {
  margin-bottom: var(--space-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  align-items: center;
}

.exec-tools .exec-label, .exec-flow .exec-label {
  margin-right: var(--space-2);
  margin-bottom: 0;
}

.exec-reply-body {
  font-size: var(--text-sm);
  line-height: 1.55;
  color: var(--color-neutral-800);
  white-space: pre-wrap;
}

.exec-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-neutral-200);
}

.exec-stat {
  font-size: var(--text-xs);
}

.stat-k {
  color: var(--color-neutral-400);
  margin-right: 4px;
}

.stat-v {
  font-weight: 600;
}
</style>
