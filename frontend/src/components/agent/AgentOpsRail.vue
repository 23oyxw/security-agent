<template>
  <aside class="ops-rail">
    <header class="ops-rail-head">
      <div class="ops-brand">
        <span class="ops-pulse" :class="pulseClass" />
        <div>
          <strong class="ops-title">OPS COPILOT</strong>
          <span class="ops-sub">运维智能副驾 · L1–L5</span>
        </div>
      </div>
      <el-tag size="small" effect="dark" :type="modeTag">{{ modeLabel }}</el-tag>
    </header>

  <div class="ops-status-strip">
      <span class="ops-kpi">
        <em>阶段</em>{{ phaseLabel }}
      </span>
      <span class="ops-kpi" v-if="planId">
        <em>Plan</em><code>{{ planId }}</code>
      </span>
      <span class="ops-kpi" v-if="l2Verdict">
        <em>L2</em>
        <el-tag size="small" :type="l2Tag" effect="plain">{{ l2Label }}</el-tag>
      </span>
      <button
        v-if="l5TraceId"
        type="button"
        class="ops-l5-link"
        @click="goL5"
      >
        <em>L5</em>链路量化 →
      </button>
    </div>

    <nav class="ops-tabs" role="tablist">
      <button
        v-for="t in railTabs"
        :key="t.id"
        type="button"
        role="tab"
        class="ops-tab"
        :class="{ active: activeTab === t.id }"
        :aria-selected="activeTab === t.id"
        @click="activeTab = t.id"
      >
        {{ t.label }}
        <span v-if="t.badge" class="ops-tab-badge">{{ t.badge }}</span>
      </button>
    </nav>

    <div class="ops-tab-body">
      <template v-if="activeTab === 'flow'">
    <section class="ops-section ops-section--compact">
      <h3 class="ops-section-title">
        <span>五层流程 · L1→L5</span>
        <span class="ops-formula">门禁在 L2/L3 之间，非独立层</span>
      </h3>
      <div class="ops-spine">
        <template v-for="node in spineNodes" :key="node.id">
          <div
            class="ops-spine-node"
            :class="{
              active: node.active,
              done: node.done,
              blocked: node.blocked,
              clickable: node.clickable,
            }"
            :style="{ '--node-accent': node.color }"
            @click="node.clickable ? onSpineClick(node.id) : null"
          >
            <span class="spine-dot" />
            <div class="spine-body">
              <span class="spine-id">{{ node.id }}</span>
              <span class="spine-label">{{ node.label }}</span>
              <span v-if="node.status" class="spine-status">{{ node.status }}</span>
            </div>
          </div>
          <div
            v-if="node.id === 'L2'"
            class="ops-gate-bridge"
            :class="gateBridgeClass"
            :style="{ '--gate-accent': LAYER_ACCENTS.GATE }"
          >
            <div class="ops-gate-chip">
              <span class="ops-gate-icon" aria-hidden="true">⇒</span>
              <div class="ops-gate-text">
                <span class="ops-gate-title">层间门禁</span>
                <span class="ops-gate-sub">plan + L2 → execute · 非层级</span>
              </div>
              <span class="ops-gate-status">{{ gateStatus }}</span>
            </div>
          </div>
        </template>
      </div>
    </section>

    <section class="ops-section ops-section--cmds">
      <h3 class="ops-section-title">
        <span>L1 快捷指令</span>
        <span class="ops-hint">零执行 · 先分析</span>
      </h3>
      <div class="ops-cat-tabs">
        <button
          v-for="cat in categories"
          :key="cat.id"
          type="button"
          class="ops-cat-btn"
          :class="{ active: activeCat === cat.id }"
          @click="activeCat = cat.id"
        >
          <el-icon :size="14"><component :is="cat.icon" /></el-icon>
          {{ cat.label }}
        </button>
      </div>
      <div class="ops-cmd-grid">
        <button
          v-for="cmd in filteredCommands"
          :key="cmd.id"
          type="button"
          class="ops-cmd-card"
          @click="$emit('quick', cmd.prompt)"
        >
          <span class="cmd-label">{{ cmd.label }}</span>
          <span class="cmd-hint">{{ cmd.hint }}</span>
          <span class="cmd-cluster">{{ cmd.cluster }}</span>
        </button>
      </div>
    </section>
      </template>

      <section v-else-if="activeTab === 'timeline'" class="ops-section ops-section--timeline">
        <h3 class="ops-section-title">
          <span>指令时间线</span>
          <div class="ops-title-actions">
            <el-button link type="primary" size="small" @click="$emit('expand-timeline')">
              全屏
            </el-button>
            <el-button v-if="plan?.trace_id" link type="primary" size="small" @click="$emit('trace', plan.trace_id)">
              Trace
            </el-button>
          </div>
        </h3>
        <CommandInspectPanel @trace="$emit('trace', $event)" @expand="$emit('expand-timeline')" />
      </section>

      <section v-else class="ops-section ops-section--dossier ops-section--scroll">
      <el-collapse v-model="openPanels" class="ops-collapse">
      <el-collapse-item v-if="plan" name="plan" title="L1 分析卷宗">
        <PlanPanel :plan="plan" :l2-verdict="l2Verdict" />
      </el-collapse-item>
      <el-collapse-item v-if="lastExecute" name="exec" title="L3 执行摘要">
        <ExecutePanel :result="lastExecute" @trace="$emit('trace', $event)" />
      </el-collapse-item>
      <el-collapse-item v-if="lastAudit" name="audit" title="L4 审计卷宗">
        <AuditPanel :audit="lastAudit" @trace="$emit('trace', $event)" />
      </el-collapse-item>
      <el-collapse-item name="l5" title="L5 链路量化 · 六维迭代">
        <div class="ops-l5-panel">
          <p class="ops-l5-desc">
            汇总 L1–L4 数据做六维评分、3σ/IQR 离群检测与 L1 策略反写。
          </p>
          <div v-if="l5TraceId" class="ops-l5-meta">
            <code>trace {{ l5TraceId.slice(0, 12) }}</code>
          </div>
          <div class="ops-l5-actions">
            <el-button size="small" type="primary" @click="goL5">
              {{ l5TraceId ? '本任务 L5 分析' : '打开 L5 总览' }}
            </el-button>
            <el-button v-if="l5TraceId" size="small" plain @click="$emit('trace', l5TraceId)">
              L4 Trace
            </el-button>
          </div>
          <p v-if="!l5TraceId" class="ops-l5-hint">完成 L3/L4 后自动关联 trace，或直接进入总览查看历史样本。</p>
        </div>
      </el-collapse-item>
      <el-collapse-item name="batch" title="批量队列">
        <BatchQueue
          :queue="batchQueue"
          :processing="batchProcessing"
          @enqueue="$emit('batch-enqueue', $event)"
          @clear="$emit('batch-clear')"
          @select="$emit('batch-select', $event)"
        />
      </el-collapse-item>
    </el-collapse>
      </section>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, defineAsyncComponent, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentStore } from '../../stores/agent'
import { FORMULA } from '../../constants/from-contract'
import { L1_CMD_CATEGORIES, L1_QUICK_COMMANDS } from '../../constants/l1-quick-commands'
import { LAYER_ACCENTS } from '../../constants/layer-colors'
import { buildL5Query, buildSafetyQuery, buildTraceQuery } from '../../utils/pipeline-context'
import CommandInspectPanel from './CommandInspectPanel.vue'

const router = useRouter()

const PlanPanel = defineAsyncComponent(() => import('./PlanPanel.vue'))
const ExecutePanel = defineAsyncComponent(() => import('./ExecutePanel.vue'))
const AuditPanel = defineAsyncComponent(() => import('./AuditPanel.vue'))
const BatchQueue = defineAsyncComponent(() => import('./BatchQueue.vue'))

defineProps({
  batchProcessing: { type: Boolean, default: false },
})

defineEmits(['quick', 'trace', 'batch-enqueue', 'batch-clear', 'batch-select', 'expand-timeline'])

const agentStore = useAgentStore()
const categories = L1_CMD_CATEGORIES
const activeCat = ref('situation')
const openPanels = ref(['plan', 'exec', 'audit', 'l5'])
const formula = FORMULA

const commandCount = computed(() => agentStore.flowSessions?.length || 0)
const activeTab = ref(commandCount.value > 0 ? 'timeline' : 'flow')

const railTabs = computed(() => [
  { id: 'flow', label: '流水线' },
  { id: 'timeline', label: '时间线', badge: commandCount.value || null },
  { id: 'dossier', label: '卷宗' },
])

const plan = computed(() => agentStore.currentPlan)
const planId = computed(() => plan.value?.plan_id?.slice(0, 8) || '')
const l2Verdict = computed(() => agentStore.l2Result?.verdict || plan.value?.l2_verdict)
const lastExecute = computed(() => agentStore.lastExecute)
const lastAudit = computed(() => agentStore.lastAudit)
const batchQueue = computed(() => agentStore.batchQueue)

const l5TraceId = computed(() => agentStore.activeTraceId)

watch(activeTab, (tab) => {
  if (tab !== 'dossier') return
  const panels = []
  if (plan.value) panels.push('plan')
  if (lastExecute.value) panels.push('exec')
  if (lastAudit.value) panels.push('audit')
  panels.push('l5')
  openPanels.value = panels
})

function goL5() {
  router.push({ path: '/l5', query: buildL5Query(agentStore) })
}

function onSpineClick(id) {
  switch (id) {
    case 'L1': {
      agentStore.setMode('plan')
      const q = { tab: 'pipeline' }
      if (agentStore.currentPlan?.plan_id) q.plan_id = agentStore.currentPlan.plan_id
      router.push({ path: '/agent', query: q })
      break
    }
    case 'L2':
      router.push({ path: '/safety', query: buildSafetyQuery(agentStore) })
      break
    case 'L3':
      if (agentStore.canExecute) {
        agentStore.setMode('execute')
        router.push({ path: '/agent', query: { tab: 'plan' } })
      }
      break
    case 'L4':
      if (l5TraceId.value) {
        router.push({ path: '/trace', query: buildTraceQuery(agentStore) })
      }
      break
    case 'L5':
      goL5()
      break
    default:
      break
  }
}

const modeLabel = computed(() => (agentStore.mode === 'plan' ? 'L1 计划' : 'L3 执行'))
const modeTag = computed(() => (agentStore.mode === 'plan' ? 'primary' : 'success'))

const phaseLabel = computed(() => {
  const m = {
    idle: '待命',
    analyze: 'L1 分析中',
    analyzed: 'L1/L2 就绪',
    execute: 'L3 执行中',
    executed: '全流程完成',
  }
  return m[agentStore.dispatchPhase] || agentStore.dispatchPhase || '待命'
})

const pulseClass = computed(() => {
  if (agentStore.dispatchPhase === 'analyze' || agentStore.dispatchPhase === 'execute') return 'is-live'
  if (agentStore.isBlocked) return 'is-alert'
  return 'is-idle'
})

const l2Label = computed(() => {
  const v = l2Verdict.value
  if (v === 'pass') return '通过'
  if (v === 'deny') return '拒绝'
  if (v === 'confirm') return '需确认'
  return v || '—'
})

const l2Tag = computed(() => {
  const v = l2Verdict.value
  if (v === 'pass') return 'success'
  if (v === 'deny') return 'danger'
  if (v === 'confirm') return 'warning'
  return 'info'
})

const filteredCommands = computed(() =>
  L1_QUICK_COMMANDS.filter(c => c.category === activeCat.value),
)

const gateBridgeClass = computed(() => {
  const phase = agentStore.dispatchPhase
  const canExec = agentStore.canExecute
  const blocked = agentStore.isBlocked
  if (blocked) return 'is-blocked'
  if (canExec && phase !== 'idle') return 'is-unlocked'
  if (agentStore.mode === 'execute' && canExec && ['analyzed', 'idle'].includes(phase)) {
    return 'is-active'
  }
  return ''
})

const gateStatus = computed(() => {
  const phase = agentStore.dispatchPhase
  const canExec = agentStore.canExecute
  const blocked = agentStore.isBlocked
  if (blocked) return '锁定'
  if (canExec && ['execute', 'executed'].includes(phase)) return '已通行'
  if (canExec && phase !== 'idle') return '已解锁'
  if (agentStore.mode === 'execute' && canExec) return '待执行'
  return '等待 L2'
})

const spineNodes = computed(() => {
  const phase = agentStore.dispatchPhase
  const l2 = l2Verdict.value
  const canExec = agentStore.canExecute
  const blocked = agentStore.isBlocked

  function layerState(id) {
    if (id === 'L1') {
      const clickable = true
      if (phase === 'analyze') return { active: true, status: '分析中', clickable }
      if (['analyzed', 'execute', 'executed'].includes(phase)) {
        return { done: true, status: '完成', clickable }
      }
      return { clickable }
    }
    if (id === 'L2') {
      const clickable = true
      if (blocked) return { blocked: true, status: '拒绝', clickable }
      if (l2 === 'confirm') return { active: true, status: '需确认', clickable }
      if (['analyzed', 'execute', 'executed'].includes(phase)) {
        return { done: true, status: l2Label.value, clickable }
      }
      if (phase === 'analyze') return { active: true, status: '预检', clickable }
      return { clickable }
    }
    if (id === 'L3') {
      const clickable = canExec
      if (phase === 'execute') return { active: true, status: '执行中', clickable }
      if (phase === 'executed') return { done: true, status: '完成', clickable }
      return { status: canExec ? '可执行' : '锁定', clickable }
    }
    if (id === 'L4') {
      const clickable = Boolean(l5TraceId.value)
      if (lastAudit.value) {
        return { done: true, status: '已审计', clickable }
      }
      return { status: phase === 'executed' ? '—' : '待命', clickable }
    }
    if (id === 'L5') {
      const clickable = Boolean(l5TraceId.value) || phase === 'executed'
      if (phase === 'executed' && lastAudit.value) {
        return { done: true, status: '可量化', clickable }
      }
      if (phase === 'executed') {
        return { active: true, status: '待回流', clickable }
      }
      if (l5TraceId.value) {
        return { status: '有 trace', clickable }
      }
      return { status: '待命', clickable: false }
    }
    return {}
  }

  const defs = [
    { id: 'L1', label: '三感知分析', color: LAYER_ACCENTS.L1 },
    { id: 'L2', label: '安全沙箱', color: LAYER_ACCENTS.L2 },
    { id: 'L3', label: '推理执行', color: LAYER_ACCENTS.L3 },
    { id: 'L4', label: 'Trace 卷宗', color: LAYER_ACCENTS.L4 },
    { id: 'L5', label: '链路量化', color: LAYER_ACCENTS.L5 },
  ]

  return defs.map(d => ({ ...d, ...layerState(d.id) }))
})
</script>

<style scoped>
.ops-rail {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 42%, #1e293b 100%);
  color: #e2e8f0;
  border-left: 1px solid rgba(148, 163, 184, 0.2);
  font-family: var(--font-sans);
}

.ops-rail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.95), transparent);
}

.ops-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ops-pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #64748b;
  box-shadow: 0 0 0 2px rgba(100, 116, 139, 0.3);
  flex-shrink: 0;
}

.ops-pulse.is-live {
  background: #22d3ee;
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.7);
  animation: ops-pulse 1.4s ease-in-out infinite;
}

.ops-pulse.is-alert {
  background: #f87171;
  box-shadow: 0 0 8px rgba(248, 113, 113, 0.6);
}

@keyframes ops-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.55; transform: scale(0.9); }
}

.ops-title {
  display: block;
  font-size: 13px;
  letter-spacing: 0.12em;
  color: #f8fafc;
}

.ops-sub {
  font-size: var(--text-xs);
  color: #94a3b8;
}

.ops-status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(15, 23, 42, 0.6);
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  flex-shrink: 0;
}

.ops-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 14px 0;
  flex-shrink: 0;
}

.ops-tab {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: rgba(15, 23, 42, 0.5);
  color: #94a3b8;
  font-size: var(--text-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.ops-tab.active {
  background: rgba(30, 41, 59, 0.95);
  color: #e2e8f0;
  border-color: rgba(56, 189, 248, 0.35);
}

.ops-tab-badge {
  font-family: var(--font-mono);
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 8px;
  background: rgba(56, 189, 248, 0.2);
  color: #7dd3fc;
}

.ops-tab-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ops-section--timeline {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-bottom: none;
}

.ops-section--timeline .cmd-inspect {
  flex: 1;
  min-height: 0;
}

.ops-section--compact {
  padding-bottom: 8px;
}

.ops-title-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.ops-kpi {
  font-size: var(--text-sm);
  color: #cbd5e1;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.ops-kpi em {
  font-style: normal;
  color: #64748b;
  font-size: var(--text-xs);
  text-transform: uppercase;
}

.ops-kpi code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: #7dd3fc;
}

.ops-section {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.ops-section--scroll {
  flex: 1;
  min-height: 120px;
  overflow-y: auto;
}

.ops-collapse {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.ops-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 10px;
  font-size: var(--text-sm);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.ops-formula,
.ops-hint {
  font-size: 9px;
  font-weight: 500;
  color: #64748b;
  text-transform: none;
  letter-spacing: 0;
}

.ops-spine {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ops-spine-node {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  position: relative;
  opacity: 0.55;
}

.ops-spine-node:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 18px;
  bottom: -6px;
  width: 1px;
  background: rgba(148, 163, 184, 0.25);
}

.ops-spine-node.active,
.ops-spine-node.done {
  opacity: 1;
}

.ops-spine-node.blocked {
  opacity: 1;
}

.ops-gate-bridge {
  margin: 2px 0 2px 14px;
  padding-left: 10px;
  border-left: 2px dashed rgba(251, 146, 60, 0.35);
}

.ops-gate-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(251, 146, 60, 0.08);
  border: 1px solid rgba(251, 146, 60, 0.2);
  opacity: 0.7;
}

.ops-gate-bridge.is-active .ops-gate-chip,
.ops-gate-bridge.is-unlocked .ops-gate-chip {
  opacity: 1;
  border-color: rgba(251, 146, 60, 0.45);
  box-shadow: 0 0 0 1px rgba(251, 146, 60, 0.12);
}

.ops-gate-bridge.is-blocked .ops-gate-chip {
  opacity: 1;
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.08);
}

.ops-gate-icon {
  color: var(--gate-accent, #fb923c);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.ops-gate-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.ops-gate-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: #fdba74;
  letter-spacing: 0.04em;
}

.ops-gate-sub {
  font-size: 9px;
  color: #64748b;
}

.ops-gate-status {
  margin-left: auto;
  font-size: 9px;
  color: #94a3b8;
  white-space: nowrap;
}

.ops-spine-node.clickable {
  cursor: pointer;
}

.ops-spine-node.clickable:hover .spine-label {
  color: #7dd3fc;
}

.ops-l5-link {
  margin-left: auto;
  border: none;
  background: rgba(14, 165, 233, 0.15);
  color: #7dd3fc;
  font-size: var(--text-sm);
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.ops-l5-link em {
  font-style: normal;
  color: #64748b;
  font-size: var(--text-xs);
  margin-right: 4px;
}

.ops-l5-panel {
  padding: 4px 2px;
}

.ops-l5-desc {
  margin: 0 0 8px;
  font-size: var(--text-sm);
  color: #475569;
  line-height: 1.5;
}

.ops-l5-meta code {
  font-size: var(--text-sm);
  color: #0369a1;
}

.ops-l5-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.ops-l5-hint {
  margin: 8px 0 0;
  font-size: var(--text-sm);
  color: #64748b;
}

.spine-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-top: 3px;
  background: #475569;
  border: 2px solid var(--node-accent, #64748b);
  flex-shrink: 0;
  z-index: 1;
}

.ops-spine-node.active .spine-dot {
  background: var(--node-accent);
  box-shadow: 0 0 6px color-mix(in srgb, var(--node-accent) 60%, transparent);
}

.ops-spine-node.done .spine-dot {
  background: var(--node-accent);
}

.ops-spine-node.blocked .spine-dot {
  background: #ef4444;
  border-color: #fca5a5;
}

.spine-body {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  flex: 1;
}

.spine-id {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--node-accent);
}

.spine-label {
  font-size: var(--text-sm);
  color: #e2e8f0;
}

.spine-status {
  margin-left: auto;
  font-size: var(--text-xs);
  color: #94a3b8;
}

.ops-cat-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.ops-cat-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.5);
  color: #94a3b8;
  font-size: var(--text-xs);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.ops-cat-btn:hover,
.ops-cat-btn.active {
  border-color: #38bdf8;
  color: #e0f2fe;
  background: rgba(14, 165, 233, 0.15);
}

.ops-cmd-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.ops-cmd-card {
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(30, 41, 59, 0.85);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.ops-cmd-card:hover {
  border-color: #38bdf8;
  background: rgba(14, 165, 233, 0.12);
}

.cmd-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  color: #f1f5f9;
  margin-bottom: 2px;
}

.cmd-hint {
  display: block;
  font-size: 9px;
  color: #94a3b8;
  line-height: 1.3;
}

.cmd-cluster {
  display: inline-block;
  margin-top: 4px;
  font-size: 8px;
  font-family: var(--font-mono);
  color: #67e8f9;
  text-transform: uppercase;
}

.ops-collapse {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.4);
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: #f8fafc;
}

.ops-collapse :deep(.el-collapse-item__header) {
  color: #cbd5e1;
  font-size: var(--text-sm);
  padding: 0 14px;
  border-bottom-color: rgba(148, 163, 184, 0.1);
}

.ops-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.ops-section--dossier {
  flex: 1;
  min-height: 0;
  padding: 0;
  border-bottom: none;
}

.ops-collapse :deep(.el-collapse-item__content) {
  padding: 8px;
  max-height: none;
  overflow: visible;
}

/* 卷宗区恢复浅色可读 */
.ops-collapse :deep(.plan-panel),
.ops-collapse :deep(.execute-panel),
.ops-collapse :deep(.audit-panel) {
  color: var(--color-text-primary);
}
</style>

<style>
/* 指令时间线在深色侧栏内的样式覆盖 */
.ops-rail .cmd-inspect .cmd-row {
  background: rgba(30, 41, 59, 0.9);
  border-color: rgba(148, 163, 184, 0.2);
  color: #e2e8f0;
}

.ops-rail .cmd-inspect .cmd-code {
  background: rgba(15, 23, 42, 0.8);
  color: #bae6fd;
  font-family: var(--font-mono);
}

.ops-rail .cmd-inspect .cmd-empty {
  color: #64748b;
}

.ops-rail .cmd-inspect .cmd-meta {
  color: #94a3b8;
}

.ops-rail .cmd-inspect .cmd-flow-head {
  background: rgba(15, 23, 42, 0.6);
  border-color: rgba(148, 163, 184, 0.2);
}

.ops-rail .cmd-inspect .cmd-session-label {
  color: #64748b;
}

.ops-rail .cmd-inspect .cmd-step-no {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
}
</style>
