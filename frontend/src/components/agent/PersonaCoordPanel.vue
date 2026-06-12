<template>
  <div class="persona-coord">
    <div class="persona-coord-header">
      <h3>角色协调</h3>
      <el-segmented v-model="activePersona" :options="personaOptions" size="small" />
    </div>

    <div class="persona-hint">
      <el-icon :size="14"><InfoFilled /></el-icon>
      <span>{{ dynamicHint }}</span>
    </div>

    <div class="persona-entities">
      <div class="entity-row" v-for="e in entities" :key="e.key">
        <code>{{ e.key }}</code>
        <span class="entity-val">{{ entityValue(e.key) }}</span>
      </div>
    </div>

    <div class="persona-links">
      <router-link
        v-for="r in currentRoutes"
        :key="r.path"
        :to="r.path"
        class="persona-link"
      >
        {{ r.name }}
      </router-link>
    </div>

    <div class="persona-layers">
      <div
        v-for="layer in layers"
        :key="layer.id"
        class="layer-chip"
        :class="{ active: activeLayer === layer.id }"
      >
        <span class="layer-id">{{ layer.id }}</span>
        <span class="layer-label">{{ layer.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  DATA_ENTITIES,
  PERSONAS,
  resolvePersonaHint,
} from '../../constants/pipeline'
import { PIPELINE_LAYERS } from '../../constants/agents'
import { NAV_PAGES } from '../../constants/navigation'

const props = defineProps({
  mode: { type: String, default: 'plan' },
  phase: { type: String, default: 'analyze' },
  planId: { type: String, default: '' },
  traceId: { type: String, default: '' },
  batchId: { type: String, default: '' },
  l2Verdict: { type: String, default: '' },
  isBlocked: { type: Boolean, default: false },
  batchCount: { type: Number, default: 0 },
})

const activePersona = ref('user')
const entities = DATA_ENTITIES
const layers = PIPELINE_LAYERS

const personaOptions = Object.values(PERSONAS).map(p => ({ label: p.label, value: p.id }))

const currentRoutes = computed(() => {
  const persona = PERSONAS[activePersona.value]
  if (!persona?.routeIds) return []
  return persona.routeIds
    .map(id => NAV_PAGES[id])
    .filter(Boolean)
    .map(p => ({ path: p.path, name: p.shortLabel || p.label }))
})

const activeLayer = computed(() => {
  if (props.mode === 'plan' || props.phase === 'analyze') return 'L1'
  if (!props.l2Verdict && props.planId) return 'L2'
  if (props.mode === 'execute') return 'L3'
  return 'L4'
})

const dynamicHint = computed(() =>
  resolvePersonaHint(activePersona.value, {
    mode: props.mode,
    l2Verdict: props.l2Verdict,
    hasPlan: !!props.planId,
    isBlocked: props.isBlocked,
    batchCount: props.batchCount,
    planId: props.planId,
    traceId: props.traceId,
  })
)

function entityValue(key) {
  const map = {
    plan_id: props.planId || '—',
    trace_id: props.traceId || '—',
    batch_id: props.batchId || '—',
    session_id: '—',
  }
  return map[key] || '—'
}
</script>

<style scoped>
.persona-coord {
  padding: 12px;
  border-radius: var(--radius-md, 8px);
  background: var(--surface-elevated, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
}

.persona-coord-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.persona-coord-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.persona-hint {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-muted, #94a3b8);
  margin-bottom: 10px;
}

.persona-entities {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
  font-size: 11px;
}

.entity-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.entity-row code {
  color: var(--accent-primary, #60a5fa);
  font-size: 10px;
}

.entity-val {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.persona-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.persona-link {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(96, 165, 250, 0.12);
  color: var(--accent-primary, #60a5fa);
  text-decoration: none;
}

.persona-layers {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.layer-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  opacity: 0.5;
  border: 1px solid transparent;
}

.layer-chip.active {
  opacity: 1;
  border-color: var(--accent-primary, #60a5fa);
  background: rgba(96, 165, 250, 0.1);
}

.layer-id {
  font-weight: 700;
}
</style>
