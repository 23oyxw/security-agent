<template>
  <div class="sa-page-header reveal-item">
    <div class="sa-page-header-main">
      <div class="sa-page-tags">
        <el-tag v-if="layer" size="small" :type="layerTagType" effect="plain">{{ layerLabel || layer }}</el-tag>
        <el-tag v-if="agent" size="small" effect="dark" type="info">{{ agentLabel }}</el-tag>
        <slot name="tags" />
      </div>
      <h1 class="sa-page-title">{{ title }}</h1>
      <p v-if="subtitle" class="sa-page-subtitle">
        {{ subtitle }}
        <slot name="subtitle-extra" />
      </p>
    </div>
    <div v-if="$slots.actions" class="sa-page-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AGENTS } from '../../constants/agents'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  layer: { type: String, default: '' },
  layerLabel: { type: String, default: '' },
  agent: { type: String, default: '' },
})

const layerTagType = computed(() => {
  const m = { L1: 'primary', L2: 'warning', L3: 'success', L4: 'info', L5: '', 'L1+L3': 'primary', 'L1-L5': 'info' }
  return m[props.layer] ?? 'info'
})

const agentLabel = computed(() => {
  if (!props.agent) return ''
  const hit = AGENTS.find(a => a.agent === props.agent)
  return hit?.displayName || props.agent
})
</script>

<style scoped>
.sa-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.sa-page-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.sa-page-title {
  font-size: var(--text-2xl);
  font-weight: var(--weight-bold, 700);
  margin: 0;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.sa-page-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin: var(--space-1) 0 0;
  line-height: 1.45;
}

.sa-page-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
</style>
