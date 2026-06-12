<template>
  <div v-if="audit" class="audit-panel reveal-item is-visible">
    <div class="audit-header">
      <el-tag size="small" type="info" effect="dark">审计迭代代理 · L4+L5</el-tag>
      <el-tag v-if="audit.trace_id" size="small" effect="plain">trace: {{ audit.trace_id.slice(0, 12) }}</el-tag>
      <el-tag size="small" :type="audit.wiki_reflux === 'pending' ? 'warning' : 'success'">
        Wiki {{ audit.wiki_reflux === 'pending' ? '待回流' : '已归档' }}
      </el-tag>
    </div>

    <div class="audit-grid">
      <div class="audit-cell">
        <span class="cell-k">审计状态</span>
        <span class="cell-v">{{ audit.audit_status || '—' }}</span>
      </div>
      <div class="audit-cell">
        <span class="cell-k">L2 结论</span>
        <span class="cell-v">{{ audit.l2_verdict || '—' }}</span>
      </div>
      <div class="audit-cell">
        <span class="cell-k">工具调用</span>
        <span class="cell-v">{{ audit.tools_invoked ?? 0 }}</span>
      </div>
      <div v-if="audit.metrics_snapshot?.intent" class="audit-cell">
        <span class="cell-k">意图</span>
        <span class="cell-v">{{ audit.metrics_snapshot.intent }}</span>
      </div>
    </div>

    <div v-if="audit.charts" class="audit-charts">
      <span class="charts-label">数学模型三场景</span>
      <el-tag size="small" effect="plain">静态 {{ audit.charts.static_perception }}</el-tag>
      <el-tag size="small" effect="plain">链路 {{ audit.charts.link_trace }}</el-tag>
      <el-tag size="small" effect="plain">指标 {{ audit.charts.global_metrics }}</el-tag>
    </div>

    <el-link v-if="audit.trace_id" type="primary" @click="$emit('trace', audit.trace_id)">
      打开 Trace 卷宗
    </el-link>
  </div>
</template>

<script setup>
defineProps({
  audit: { type: Object, default: null },
})
defineEmits(['trace'])
</script>

<style scoped>
.audit-panel {
  padding: var(--space-4);
  border: 1px solid var(--color-neutral-300);
  border-radius: var(--radius-lg);
  background: var(--glass-surface, rgba(248, 250, 252, 0.8));
  margin-bottom: var(--space-4);
}

.audit-header {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.audit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.audit-cell {
  padding: var(--space-2);
  background: var(--glass-chip, #f1f5f9);
  border-radius: var(--radius-md);
  text-align: center;
}

.cell-k {
  display: block;
  font-size: 10px;
  color: var(--color-neutral-400);
}

.cell-v {
  font-weight: 600;
  font-size: var(--text-sm);
}

.audit-charts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-2);
}

.charts-label {
  font-size: 10px;
  color: var(--color-neutral-400);
  margin-right: var(--space-1);
}
</style>
