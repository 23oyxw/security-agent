<template>
  <div class="cmd-inspect" :class="{ expanded }">
    <header v-if="showToolbar" class="cmd-toolbar">
      <div class="cmd-session-bar">
        <label class="cmd-session-label">流程</label>
        <el-select
          v-model="selectedFlowKey"
          size="small"
          class="cmd-session-select"
          placeholder="选择一次完整流程"
          @change="onSessionChange"
        >
          <el-option
            v-for="s in sessionOptions"
            :key="s.flowKey"
            :label="s.label"
            :value="s.flowKey"
          >
            <div class="cmd-option">
              <span class="cmd-option-msg">{{ s.shortMessage }}</span>
              <span class="cmd-option-meta">{{ s.timeLabel }} · {{ s.statusLabel }}</span>
            </div>
          </el-option>
        </el-select>
        <el-tag v-if="activeSession" size="small" :type="statusTag(activeSession.status)" effect="plain">
          {{ activeSession.statusLabel || activeSession.status }}
        </el-tag>
      </div>
      <div class="cmd-toolbar-actions">
        <el-button v-if="activeSession?.planId" link type="primary" size="small" @click="$emit('trace', activeSession.traceId)">
          Trace
        </el-button>
        <el-button v-if="pipelineSteps.length" link type="primary" size="small" @click="copyFlow">
          复制本流程
        </el-button>
        <el-button v-if="!expanded" link type="primary" size="small" @click="$emit('expand')">
          展开
        </el-button>
      </div>
    </header>

    <div v-if="activeSession" class="cmd-flow-head">
      <p class="cmd-flow-title">{{ activeSession.message }}</p>
      <div class="cmd-flow-meta">
        <code v-if="activeSession.planId">plan {{ activeSession.planId.slice(0, 8) }}</code>
        <span v-if="activeSession.intent">意图 {{ activeSession.intent }}</span>
        <span v-if="activeSession.l2Verdict">L2 {{ activeSession.l2Verdict }}</span>
      </div>
      <div class="cmd-pipeline-rail" aria-hidden="true">
        <span
          v-for="stage in pipelineStages"
          :key="stage.id"
          class="cmd-pipeline-node"
          :class="stage.state"
        >
          {{ stage.id }}
        </span>
      </div>
    </div>

    <div ref="listRef" class="cmd-list">
      <p v-if="!activeSession" class="cmd-empty">
        暂无流程记录。每次 L1 分析会生成一条独立流程，不会与历史混淆。
      </p>
      <p v-else-if="!pipelineSteps.length" class="cmd-empty">该流程尚无步骤记录。</p>
      <div
        v-for="(e, i) in pipelineSteps"
        :key="e._key || i"
        class="cmd-row"
        :class="e.layer"
      >
        <div class="cmd-head">
          <span class="cmd-step-no">{{ i + 1 }}</span>
          <el-tag size="small" :type="layerTag(e.layer)" effect="plain">{{ e.layer }}</el-tag>
          <span class="cmd-type">{{ e.typeLabel }}</span>
          <span class="cmd-time">{{ formatTime(e.ts) }}</span>
          <el-button
            v-if="e.command"
            link
            type="primary"
            size="small"
            class="cmd-copy"
            @click="copyText(e.command)"
          >
            复制
          </el-button>
        </div>
        <pre
          v-if="e.command"
          class="cmd-code"
          :class="{ 'cmd-code--full': expanded }"
        >{{ e.command }}</pre>
        <p v-if="e.intent" class="cmd-meta">意图: {{ e.intent }}</p>
        <p v-if="e.verdict" class="cmd-meta">判定: {{ e.verdict }}</p>
        <div v-if="e.tools?.length" class="cmd-tools">
          <el-tag v-for="t in e.tools" :key="t" size="small" effect="plain">{{ t }}</el-tag>
        </div>
        <el-link v-if="e.trace_id" type="primary" @click="$emit('trace', e.trace_id)">
          Trace {{ e.trace_id.slice(0, 8) }}
        </el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../../stores/agent'

const props = defineProps({
  expanded: { type: Boolean, default: false },
  showToolbar: { type: Boolean, default: true },
  autoScroll: { type: Boolean, default: true },
})

defineEmits(['trace', 'expand'])

const agentStore = useAgentStore()
const listRef = ref(null)
const selectedFlowKey = ref('')

const TYPE_LABELS = {
  user_message: '用户指令',
  plan: 'L1 计划',
  boundary: '边界命中',
  l2_defense: 'L2 安全沙箱',
  execute: 'L3 执行',
  audit: 'L4 审计',
  l5_ready: 'L5 量化就绪',
  tool: '工具调用',
}

const LAYER_ORDER = { L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 }

function sessionLabel(s) {
  const msg = (s.message || '未命名').replace(/\s+/g, ' ').slice(0, 28)
  const time = formatTime(s.startedAt)
  return `${time} · ${msg}`
}

const sessionOptions = computed(() =>
  (agentStore.flowSessions || []).map(s => ({
    flowKey: s.planId || s.flowKey,
    label: sessionLabel(s),
    shortMessage: (s.message || '未命名').slice(0, 36),
    timeLabel: formatTime(s.startedAt),
    statusLabel: s.statusLabel || s.status,
  })),
)

const activeSession = computed(() => {
  if (!selectedFlowKey.value) return agentStore.activeFlowSession || agentStore.flowSessions?.[0] || null
  return agentStore.findFlow({ planId: selectedFlowKey.value, flowKey: selectedFlowKey.value })
    || agentStore.flowSessions?.find(s => (s.planId || s.flowKey) === selectedFlowKey.value)
    || null
})

const pipelineSteps = computed(() => {
  const steps = activeSession.value?.steps || []
  return [...steps]
    .sort((a, b) => {
      const la = LAYER_ORDER[a.layer] || 9
      const lb = LAYER_ORDER[b.layer] || 9
      if (la !== lb) return la - lb
      return (a.ts || 0) - (b.ts || 0)
    })
    .map((e, i) => ({
      ...e,
      _key: `${e.type}|${e.ts}|${i}`,
      typeLabel: TYPE_LABELS[e.type] || e.type,
    }))
})

const pipelineStages = computed(() => {
  const layers = new Set(pipelineSteps.value.map(s => s.layer))
  const status = activeSession.value?.status
  return ['L1', 'L2', 'L3', 'L4', 'L5'].map(id => {
    let state = 'pending'
    if (layers.has(id)) state = 'done'
    if (id === 'L3' && status === 'executing') state = 'active'
    if (id === 'L1' && status === 'analyzing') state = 'active'
    if (status === 'blocked' && id === 'L2') state = 'blocked'
    if (id === 'L5' && status === 'executed' && !layers.has('L5')) state = 'active'
    return { id, state }
  })
})

watch(
  () => agentStore.activeFlowSession?.flowKey || agentStore.activeFlowSession?.planId,
  key => {
    if (key) selectedFlowKey.value = agentStore.activeFlowSession?.planId || key
  },
  { immediate: true },
)

watch(
  () => agentStore.flowSessions?.length,
  () => {
    const current = agentStore.activeFlowSession
    if (current) {
      selectedFlowKey.value = current.planId || current.flowKey
    }
  },
)

watch(
  () => pipelineSteps.value.length,
  () => {
    if (!props.autoScroll) return
    nextTick(() => {
      if (listRef.value) listRef.value.scrollTop = 0
    })
  },
)

function onSessionChange() {
  nextTick(() => {
    if (listRef.value) listRef.value.scrollTop = 0
  })
}

function statusTag(status) {
  const map = {
    analyzing: 'primary',
    analyzed: 'info',
    executing: 'warning',
    executed: 'success',
    blocked: 'danger',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function layerTag(layer) {
  const map = { L1: 'primary', L2: 'warning', L3: 'success', L4: 'info' }
  return map[layer] || 'info'
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败')
  }
}

function copyFlow() {
  if (!activeSession.value) return
  const lines = [
    `【流程】${activeSession.value.message}`,
    `plan: ${activeSession.value.planId || '—'}`,
    `trace: ${activeSession.value.traceId || '—'}`,
    `状态: ${activeSession.value.statusLabel || activeSession.value.status}`,
    '',
  ]
  for (const step of pipelineSteps.value) {
    lines.push(`--- ${step.layer} ${step.typeLabel} ${formatTime(step.ts)} ---`)
    if (step.command) lines.push(step.command)
    if (step.verdict) lines.push(`判定: ${step.verdict}`)
    lines.push('')
  }
  copyText(lines.join('\n'))
}
</script>

<style scoped>
.cmd-inspect {
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 8px;
}

.cmd-inspect.expanded {
  height: 100%;
}

.cmd-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.cmd-session-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cmd-session-label {
  font-size: var(--text-xs);
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.cmd-session-select {
  flex: 1;
  min-width: 140px;
}

.cmd-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.cmd-option-msg {
  font-size: var(--text-sm);
}

.cmd-option-meta {
  font-size: var(--text-xs);
  color: #94a3b8;
}

.cmd-toolbar-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.cmd-flow-head {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(148, 163, 184, 0.15);
  flex-shrink: 0;
}

.cmd-flow-title {
  margin: 0 0 6px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: #e2e8f0;
  line-height: 1.4;
}

.cmd-flow-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: var(--text-xs);
  color: #94a3b8;
  margin-bottom: 8px;
}

.cmd-flow-meta code {
  font-family: var(--font-mono);
  color: #7dd3fc;
}

.cmd-pipeline-rail {
  display: flex;
  gap: 6px;
}

.cmd-pipeline-node {
  flex: 1;
  text-align: center;
  font-size: 9px;
  font-family: var(--font-mono);
  padding: 3px 0;
  border-radius: 4px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #64748b;
}

.cmd-pipeline-node.done {
  border-color: rgba(34, 197, 94, 0.4);
  color: #86efac;
  background: rgba(34, 197, 94, 0.1);
}

.cmd-pipeline-node.active {
  border-color: rgba(56, 189, 248, 0.5);
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.12);
}

.cmd-pipeline-node.blocked {
  border-color: rgba(248, 113, 113, 0.5);
  color: #fca5a5;
}

.cmd-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cmd-empty {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  text-align: center;
  padding: 16px;
}

.cmd-row {
  padding: 10px;
  border: 1px solid var(--color-border-default);
  border-radius: 8px;
  background: #fff;
}

.cmd-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.cmd-step-no {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.2);
  color: #64748b;
  font-size: var(--text-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cmd-type {
  font-size: var(--text-sm);
  font-weight: 600;
  flex: 1;
}

.cmd-time {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.cmd-copy {
  margin-left: auto;
}

.cmd-code {
  margin: 0;
  font-size: var(--text-sm);
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-neutral-50);
  padding: 8px;
  border-radius: 6px;
  max-height: 160px;
  overflow: auto;
}

.cmd-code--full {
  max-height: none;
}

.cmd-meta {
  margin: 4px 0 0;
  font-size: var(--text-sm);
  color: var(--color-neutral-500);
}

.cmd-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
</style>
