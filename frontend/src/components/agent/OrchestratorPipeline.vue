<template>
  <div class="orchestrator-pipeline reveal-item">
    <div class="pipeline-layers">
      <span class="layers-title">五层刚性流程</span>
      <div class="layers-row">
        <span
          v-for="l in layers"
          :key="l.id"
          class="layer-chip"
          :class="{ active: isLayerActive(l.id) }"
        >{{ l.id }} {{ l.label }}</span>
      </div>
      <span v-if="phase" class="phase-badge">{{ phaseLabel }}</span>
    </div>
    <div class="pipeline-user">
      <div class="pipeline-node user-node">
        <el-icon :size="18"><UserFilled /></el-icon>
        <span>用户</span>
      </div>
      <div class="pipeline-connector" :class="{ active: anyRunning }" />
    </div>

    <div class="pipeline-orchestrator">
      <div class="pipeline-node orch-node" :class="{ active: anyRunning }">
        <el-icon :size="18"><MagicStick /></el-icon>
        <div class="node-text">
          <strong>{{ orchestrator.displayName }}</strong>
          <span>{{ orchestrator.description }}</span>
        </div>
      </div>
      <div class="pipeline-connector fan-out" :class="{ active: anyRunning }" />
    </div>

    <div class="pipeline-agents">
      <template v-for="(a, idx) in agents" :key="a.agent">
        <div class="pipeline-agent-col">
          <div class="pipeline-node agent-node" :class="[a.status, a.color]">
            <div class="agent-node-head">
              <el-icon :size="16"><component :is="a.icon" /></el-icon>
              <span class="status-dot" :class="a.status" />
            </div>
            <strong>{{ a.displayName }}</strong>
            <el-tag size="small" effect="plain" class="layer-tag">{{ a.layer }}</el-tag>
            <span class="layer-note">{{ a.layerNote }}</span>
            <p class="agent-desc">{{ a.description }}</p>
            <p v-if="a.detail" class="agent-detail">{{ a.detail }}</p>
            <span v-else class="agent-status-label">{{ statusLabel(a.status) }}</span>
          </div>
        </div>
        <div
          v-if="idx < agents.length - 1"
          class="pipeline-connector horizontal"
          :class="{ active: isConnectorActive(idx) }"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ORCHESTRATOR, PIPELINE_LAYERS } from '../../constants/agents'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  phase: { type: String, default: 'idle' },
})

const layers = PIPELINE_LAYERS
const orchestrator = ORCHESTRATOR

const anyRunning = computed(() => props.agents.some(a => a.status === 'running'))

const phaseLabel = computed(() => {
  const m = {
    idle: '待命',
    analyze: 'L1 analyze',
    analyzed: 'L1/L2 完成',
    execute: 'L3 execute',
    executed: '全流程完成',
  }
  return m[props.phase] || props.phase
})

function isLayerActive(layerId) {
  if (props.phase === 'executed') return true
  if (layerId === 'L1' && ['analyze', 'analyzed', 'execute', 'executed'].includes(props.phase)) return true
  if (layerId === 'L2' && ['analyzed', 'execute', 'executed'].includes(props.phase)) return true
  if (layerId === 'L3' && ['execute', 'executed'].includes(props.phase)) return true
  if (layerId === 'L4' || layerId === 'L5') return props.phase === 'executed'
  return false
}

function statusLabel(s) {
  const m = { idle: '待命', running: '处理中', done: '完成', blocked: '拒绝', error: '失败' }
  return m[s] || s
}

function isConnectorActive(afterIndex) {
  const current = props.agents[afterIndex]
  const next = props.agents[afterIndex + 1]
  if (!current || !next) return false
  return current.status === 'done' || next.status === 'running' || next.status === 'done'
}
</script>

<style scoped>
.orchestrator-pipeline {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  background: var(--glass-surface, rgba(255, 255, 255, 0.55));
  overflow-x: auto;
}

.pipeline-layers {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px dashed var(--color-neutral-200);
}

.layers-title {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--color-neutral-400);
  text-transform: uppercase;
}

.layers-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.layer-chip {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-neutral-100);
  color: var(--color-neutral-400);
  border: 1px solid transparent;
}

.layer-chip.active {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
  border-color: var(--color-primary-200);
}

.phase-badge {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--color-primary-600);
  font-weight: 600;
}

.pipeline-user,
.pipeline-orchestrator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.pipeline-agents {
  display: flex;
  align-items: stretch;
  gap: 0;
  min-width: min(100%, 720px);
}

.pipeline-agent-col {
  flex: 1;
  min-width: 180px;
}

.pipeline-node {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-neutral-200);
  background: var(--glass-chip, #f8fafc);
  text-align: center;
  transition: border-color 0.25s, box-shadow 0.25s;
}

.pipeline-node strong {
  display: block;
  font-size: var(--text-sm);
  margin: var(--space-1) 0;
}

.user-node {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  width: fit-content;
}

.orch-node {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
  border-color: var(--color-primary-300);
  background: linear-gradient(135deg, var(--color-primary-50, #eff6ff), transparent);
}

.orch-node.active {
  box-shadow: 0 0 0 2px var(--color-primary-200);
}

.node-text span {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-top: 2px;
}

.agent-node {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.agent-node.running {
  border-color: var(--color-primary-400);
  box-shadow: 0 0 12px -4px var(--color-primary-300);
}

.agent-node.done { border-color: var(--color-success); }
.agent-node.blocked, .agent-node.error { border-color: var(--color-danger); }

.agent-node-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  justify-content: center;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-neutral-300);
}
.status-dot.running { background: var(--color-primary-500); animation: agent-pulse 1s infinite; }
.status-dot.done { background: var(--color-success); }
.status-dot.blocked, .status-dot.error { background: var(--color-danger); }

@keyframes agent-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}

.layer-tag { margin: 4px 0 2px; }
.layer-note {
  font-size: 9px;
  color: var(--color-neutral-400);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.agent-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  line-height: 1.35;
  margin: var(--space-2) 0 0;
  flex: 1;
}

.agent-detail, .agent-status-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  margin-top: var(--space-2);
}

.pipeline-connector {
  flex-shrink: 0;
  background: var(--color-neutral-200);
  transition: background 0.3s;
}

.pipeline-connector:not(.horizontal) {
  width: 2px;
  height: 20px;
  margin-left: 24px;
}

.pipeline-connector.horizontal {
  width: 24px;
  height: 2px;
  align-self: center;
  margin-top: 60px;
}

.pipeline-connector.fan-out {
  width: 100%;
  height: 2px;
  margin: var(--space-2) 0;
}

.pipeline-connector.active {
  background: linear-gradient(90deg, var(--color-primary-400), var(--color-success));
}

@media (max-width: 768px) {
  .pipeline-agents { flex-direction: column; }
  .pipeline-connector.horizontal {
    width: 2px;
    height: 16px;
    margin: 0 auto;
  }
}
</style>
