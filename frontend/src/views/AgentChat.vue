<template>
  <div class="agent-page">
    <div class="agent-layout">
      <div class="agent-main">
        <header class="agent-bar">
          <div class="agent-bar-left">
            <span class="agent-bar-title">{{ agentPage.label }}</span>
            <el-tag size="small" effect="plain" type="info">{{ agentPage.layerLabel }}</el-tag>
            <el-segmented v-model="agentStore.mode" :options="modeOptions" size="small" />
          </div>
          <div class="agent-bar-right">
            <el-badge :value="commandCount" :hidden="!commandCount" :max="99">
              <el-button size="small" plain @click="openTimelineDrawer">
                指令时间线
              </el-button>
            </el-badge>
            <el-button
              v-if="activeTraceId"
              size="small"
              :type="tracePanelVisible ? 'primary' : 'default'"
              plain
              @click="toggleTracePanel"
            >
              Trace 纪要
            </el-button>
            <el-button v-if="!railOpen" size="small" type="primary" plain @click="railOpen = true">
              打开副驾栏
            </el-button>
            <PipelineBtn action="clear" size="small" @click="clearChat" />
          </div>
        </header>

        <div class="chat-shell">
          <div
            v-if="agentStore.mode === 'execute' && agentStore.currentPlan && !agentStore.canExecute"
            class="chat-notice"
          >
            执行模式未解锁：请先在计划模式完成 L1，并等待 L2 通过
          </div>

          <div class="chat-messages" ref="messagesRef">
            <div v-if="!messages.length && !thinking" class="chat-welcome">
              <p class="welcome-eyebrow">L1 · 三感知分析入口</p>
              <p class="welcome-title">运维智能助手</p>
              <p class="welcome-sub">
                输入自然语言运维需求，或点选下方 / 右侧 <strong>L1 快捷指令</strong>，先完成计划再进 L3 执行
              </p>
              <div class="welcome-cats">
                <button
                  v-for="cat in cmdCategories"
                  :key="cat.id"
                  type="button"
                  class="welcome-cat"
                  :class="{ active: welcomeCat === cat.id }"
                  @click="welcomeCat = cat.id"
                >
                  <el-icon :size="14"><component :is="cat.icon" /></el-icon>
                  {{ cat.label }}
                </button>
              </div>
              <div class="quick-cmds">
                <button
                  v-for="cmd in welcomeCommands"
                  :key="cmd.id"
                  type="button"
                  class="quick-cmd"
                  @click="applyQuick(cmd.prompt)"
                >
                  <span class="quick-cmd-label">{{ cmd.label }}</span>
                  <span class="quick-cmd-hint">{{ cmd.hint }}</span>
                </button>
              </div>
            </div>
            <div v-for="(msg, i) in messages" :key="i" class="msg-row" :class="msg.role">
              <div class="msg-bubble" :class="msg.role">
                <div class="msg-meta">
                  <span class="msg-who">{{ msg.role === 'user' ? '你' : (msg.roleLabel || '助手') }}</span>
                  <span v-if="msg.meta" class="msg-layer">{{ msg.meta }}</span>
                </div>
                <div class="msg-text" v-html="renderContent(msg.content)"></div>
                <div v-if="msg.plan_id" class="msg-tags">
                  <el-tag size="small" type="info">{{ msg.plan_id.slice(0, 8) }}</el-tag>
                  <el-link v-if="msg.trace_id" type="primary" @click="goTrace(msg.trace_id)">Trace</el-link>
                </div>
              </div>
            </div>
            <div v-if="thinking" class="msg-row agent">
              <div class="msg-bubble agent thinking">处理中… {{ thinkingLabel }}</div>
            </div>
          </div>

          <div v-if="agentStore.mode === 'plan'" class="chat-quick-strip">
            <span class="strip-label">L1 快捷</span>
            <div class="strip-scroll">
              <button
                v-for="cmd in stripCommands"
                :key="cmd.id"
                type="button"
                class="strip-cmd"
                :disabled="thinking"
                @click="applyQuick(cmd.prompt)"
              >{{ cmd.label }}</button>
            </div>
          </div>

          <div class="chat-foot">
            <el-input
              v-model="input"
              type="textarea"
              :rows="2"
              resize="none"
              :placeholder="inputPlaceholder"
              @keydown.enter.exact.prevent="primaryAction"
              :disabled="thinking"
            />
            <div class="chat-foot-actions">
              <el-checkbox
                v-if="agentStore.mode === 'execute'"
                v-model="autoExecute"
                size="small"
                :disabled="thinking"
              >
                L2 通过后自动执行
              </el-checkbox>
              <div class="chat-btns">
                <PipelineBtn
                  v-if="agentStore.mode === 'plan'"
                  action="l1Analyze"
                  :loading="thinking"
                  :disabled="!input.trim()"
                  @click="sendAnalyze"
                />
                <template v-else>
                  <PipelineBtn
                    v-if="agentStore.needsConfirm"
                    action="l3ConfirmExecute"
                    :loading="thinking"
                    :disabled="!agentStore.currentPlan || agentStore.isBlocked"
                    @click="dispatchExecute(true)"
                  />
                  <PipelineBtn
                    action="l3Execute"
                    :loading="thinking"
                    :disabled="!agentStore.canExecute || agentStore.isBlocked"
                    @click="dispatchExecute(agentStore.needsConfirm)"
                  />
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <TraceMemoDock
        v-if="activeTraceId && traceDockOpen && !isNarrow"
        :trace-id="activeTraceId"
        @close="traceDockOpen = false"
        @open-full="openTraceFull(activeTraceId)"
      />

      <AgentOpsRail
        v-show="railOpen && !isNarrow"
        class="agent-rail"
        :batch-processing="batchProcessing"
        @quick="applyQuick"
        @trace="goTrace"
        @batch-enqueue="onBatchEnqueue"
        @batch-clear="agentStore.clearBatch()"
        @batch-select="onBatchSelect"
        @expand-timeline="openTimelineDrawer"
      />
    </div>

    <el-drawer
      v-model="traceDrawerOpen"
      title="Trace 阶段图 · 纪要"
      direction="rtl"
      size="min(100%, 420px)"
      class="trace-drawer"
      :with-header="true"
      destroy-on-close
    >
      <TraceMemoDock
        v-if="activeTraceId && traceDrawerOpen"
        :trace-id="activeTraceId"
        drawer
        @close="traceDrawerOpen = false"
        @open-full="openTraceFull(activeTraceId)"
      />
    </el-drawer>

    <el-drawer
      v-model="timelineOpen"
      title="指令时间线"
      direction="rtl"
      size="min(100%, 520px)"
      class="timeline-drawer"
      :with-header="true"
    >
      <CommandInspectPanel expanded :auto-scroll="true" @trace="goTrace" />
    </el-drawer>

    <el-drawer
      v-model="drawerOpen"
      title="OPS COPILOT · 运维副驾"
      direction="rtl"
      size="min(100%, 420px)"
      class="ops-drawer"
      :with-header="true"
    >
      <AgentOpsRail
        :batch-processing="batchProcessing"
        @quick="applyQuick($event); drawerOpen = false"
        @trace="goTrace"
        @batch-enqueue="onBatchEnqueue"
        @batch-clear="agentStore.clearBatch()"
        @batch-select="onBatchSelect"
        @expand-timeline="openTimelineDrawer"
      />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useWindowSize } from '@vueuse/core'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'
import { useAgentWs } from '../composables/useAgentWs'
import { buildAgentQuery, traceQuery } from '../utils/pipeline-context'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import AgentOpsRail from '../components/agent/AgentOpsRail.vue'
import CommandInspectPanel from '../components/agent/CommandInspectPanel.vue'
import TraceMemoDock from '../components/agent/TraceMemoDock.vue'
import { AGENTS, ORCHESTRATOR } from '../constants/agents'
import { NAV_PAGES } from '../constants/navigation'
import { L1_CMD_CATEGORIES, L1_QUICK_COMMANDS } from '../constants/l1-quick-commands'

const agentPage = NAV_PAGES.agent
const cmdCategories = L1_CMD_CATEGORIES
const welcomeCat = ref('situation')
const welcomeCommands = computed(() =>
  L1_QUICK_COMMANDS.filter(c => c.category === welcomeCat.value),
)
const stripCommands = L1_QUICK_COMMANDS

const modeOptions = ORCHESTRATOR.modes.map(m => ({ label: m.label, value: m.value }))

const inputPlaceholder = computed(() =>
  agentStore.mode === 'plan'
    ? '输入运维指令，Enter 或点 L1 三感知分析 · 也可用右侧快捷指令'
    : '执行模式：需 plan + L2 通过后点 L3 执行',
)

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const { chatMessages: messages } = storeToRefs(agentStore)
const input = ref('')
const thinking = ref(false)
const thinkingLabel = ref('')
const messagesRef = ref(null)
const batchProcessing = ref(false)
const autoExecute = ref(false)
const railOpen = ref(true)
const drawerOpen = ref(false)
const timelineOpen = ref(false)
const traceDockOpen = ref(true)
const traceDrawerOpen = ref(false)

const commandCount = computed(() => agentStore.flowSessions?.length || 0)
const activeTraceId = computed(() => agentStore.activeTraceId)
const tracePanelVisible = computed(() =>
  isNarrow.value ? traceDrawerOpen.value : traceDockOpen.value,
)

function toggleTracePanel() {
  if (!activeTraceId.value) return
  if (isNarrow.value) {
    traceDrawerOpen.value = !traceDrawerOpen.value
  } else {
    traceDockOpen.value = !traceDockOpen.value
  }
}

function openTraceFull(traceId) {
  traceDrawerOpen.value = false
  router.push({ path: '/trace', query: { ...traceQuery(traceId, agentStore), tab: 'stages' } })
}

function openTimelineDrawer() {
  timelineOpen.value = true
}

const { width } = useWindowSize()
const isNarrow = computed(() => width.value < 1100)

watch(activeTraceId, id => {
  if (!id) return
  if (isNarrow.value) traceDrawerOpen.value = true
  else traceDockOpen.value = true
})

watch(isNarrow, narrow => {
  if (narrow) railOpen.value = false
  else drawerOpen.value = false
})

const { connect: connectWs, disconnect: disconnectWs } = useAgentWs()

function renderContent(content) {
  if (!content) return ''
  return content
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '• $1<br>')
    .replace(/\n/g, '<br>')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
}

function applyQuick(text) {
  input.value = text
  if (agentStore.mode === 'plan') sendAnalyze()
}

watch(messages, scrollToBottom, { deep: true })

watch(
  () => route.query.tab,
  tab => {
    if (tab && isNarrow.value) drawerOpen.value = true
  },
  { immediate: true },
)

const autorunHandled = ref(false)

watch(
  () => [route.query.autorun, agentStore.currentPlan?.plan_id, agentStore.canExecute],
  async ([autorun]) => {
    if (autorun !== '1' || autorunHandled.value || thinking.value) return
    if (!agentStore.canExecute || agentStore.isBlocked) return
    autorunHandled.value = true
    const goL5 = route.query.toL5 === '1'
    router.replace({ path: '/agent', query: {} })
    await dispatchExecute(agentStore.needsConfirm, { goL5 })
  },
  { immediate: true },
)

function syncPipelineQuery(extra = {}) {
  const q = buildAgentQuery(agentStore, { ...route.query, ...extra })
  delete q.autorun
  delete q.toL5
  router.replace({ path: '/agent', query: q })
}

function goTrace(traceId) {
  router.push({ path: '/trace', query: { ...traceQuery(traceId, agentStore), tab: 'analysis' } })
}

function pushAgentMessage(agent, content, meta, extra = {}) {
  const hit = AGENTS.find(a => a.agent === agent)
  agentStore.pushChatMessage({
    role: 'assistant',
    roleLabel: hit?.displayName || '助手',
    agent,
    content,
    meta,
    ...extra,
  })
}

async function sendAnalyze() {
  const text = input.value.trim()
  if (!text || thinking.value) return
  agentStore.pushChatMessage({ role: 'user', content: text })
  input.value = ''
  thinking.value = true
  thinkingLabel.value = 'L1 分析中'
  try {
    const res = await agentStore.analyze(text, {
      autoExecute: autoExecute.value && agentStore.mode === 'execute',
      userConfirmed: autoExecute.value,
    })
    const l2 = res.l2
    const l2Text = l2.verdict === 'pass' ? '通过' : l2.verdict === 'deny' ? '拒绝' : '需确认'
    pushAgentMessage(
      'core_dispatch',
      `L1 完成 · 意图 ${res.plan.intent} · 边界 ${(res.plan.boundary_hits || []).length} · 知识 ${(res.plan.knowledge_refs || []).length}`,
      'L1',
      { plan_id: res.plan.plan_id, trace_id: res.plan.trace_id },
    )
    pushAgentMessage('safety_sandbox', `L2：${l2Text}`, 'L2')
    if (isNarrow.value) drawerOpen.value = true
    if (res.execute) {
      appendExecuteResult(res.execute)
      if (res.audit) appendAuditSummary(res.audit)
      if (route.query.toL5 === '1') {
        const tid = res.execute.trace_id || res.audit?.trace_id
        router.push({ path: '/l5', query: tid ? { trace: tid } : {} })
      }
    } else if (l2.verdict === 'deny') {
      ElMessage.warning('L2 拒绝')
    } else {
      ElMessage.success('L1/L2 完成')
    }
    syncPipelineQuery()
  } catch (e) {
    const detail = e.response?.data?.detail || e.message || '分析失败'
    ElMessage.error(detail)
    pushAgentMessage('core_dispatch', `分析失败：${detail}`, 'L1')
  } finally {
    thinking.value = false
  }
}

function appendExecuteResult(res) {
  const dup = messages.value.some(
    m => m.meta === 'L3' && m.trace_id && m.trace_id === res.trace_id,
  )
  if (dup) return
  pushAgentMessage('core_dispatch', res.reply || '（无回复）', 'L3', {
    plan_id: res.plan_id,
    trace_id: res.trace_id,
  })
}

function appendAuditSummary(audit) {
  pushAgentMessage(
    'audit_iteration',
    `审计完成 · 工具 ${audit.tools_invoked ?? 0} 次 · 可进入 **L5 链路量化** 查看六维评分`,
    'L4',
    { trace_id: audit.trace_id },
  )
}

function primaryAction() {
  if (agentStore.mode === 'plan') sendAnalyze()
  else if (agentStore.canExecute) dispatchExecute(agentStore.needsConfirm)
}

async function dispatchExecute(userConfirmed = false, { goL5 = false } = {}) {
  thinking.value = true
  thinkingLabel.value = 'L3 执行中'
  try {
    const res = await agentStore.runExecute({ userConfirmed })
    appendExecuteResult(res)
    if (agentStore.lastAudit) appendAuditSummary(agentStore.lastAudit)
    if (isNarrow.value) drawerOpen.value = true
    ElMessage.success('L3/L4 完成')
    syncPipelineQuery()
    if (goL5) {
      const tid = res.trace_id || agentStore.lastAudit?.trace_id
      router.push({ path: '/l5', query: tid ? { trace: tid } : {} })
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    thinking.value = false
  }
}

async function onBatchEnqueue(text) {
  agentStore.addBatchLines(text)
  batchProcessing.value = true
  if (isNarrow.value) drawerOpen.value = true
  try {
    await agentStore.processBatchQueue(item => {
      if (item.status === 'analyzing') {
        agentStore.pushChatMessage({ role: 'user', content: `[批量] ${item.message}` })
      }
    })
  } finally {
    batchProcessing.value = false
  }
}

function onBatchSelect(item) {
  if (item.message) input.value = item.message
}

function clearChat() {
  agentStore.clearChatMessages()
  agentStore.clearFlowHistory()
  agentStore.pushChatMessage({
    role: 'assistant',
    content: '对话已清空。使用 **L1 快捷指令** 或输入框发起新的运维分析。',
  })
  agentStore.resetPlan()
  router.replace({ path: '/agent', query: {} })
}

onMounted(async () => {
  if (!Array.isArray(messages.value)) {
    agentStore.clearChatMessages()
  }
  if (!messages.value.length) {
    agentStore.pushChatMessage({
      role: 'assistant',
      content: '运维智能副驾已就绪。右侧 **OPS COPILOT** 可查看流水线、快捷指令与时间线。',
    })
  }
  const planId = route.query.plan_id
  if (planId && agentStore.currentPlan?.plan_id !== planId) {
    await agentStore.hydrateFromPlan(String(planId))
  }
  connectWs()
  if (isNarrow.value) railOpen.value = false
})

onUnmounted(() => disconnectWs())
</script>

<style scoped>
.agent-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  min-height: 0;
}

.agent-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 0;
}

.agent-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.agent-rail {
  width: 440px;
  flex-shrink: 0;
  min-height: 0;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  overflow: hidden;
}

.agent-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  flex-shrink: 0;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border-default);
}

.agent-bar-left,
.agent-bar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.agent-bar-title {
  font-weight: 700;
  font-size: var(--text-base);
  color: var(--color-text-primary);
}

.chat-shell {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  background: var(--color-surface, #fafbfc);
  overflow: hidden;
}

.chat-notice {
  flex-shrink: 0;
  padding: 8px 12px;
  font-size: var(--text-sm);
  background: var(--color-warning-bg);
  color: var(--color-warning-muted);
}

.chat-messages {
  flex: 1;
  min-height: 160px;
  overflow-y: auto;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: #f8fafc;
}

.chat-welcome {
  margin: auto;
  max-width: 640px;
  text-align: center;
  padding: var(--space-6) var(--space-4);
}

.welcome-eyebrow {
  margin: 0 0 4px;
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-primary-600);
}

.welcome-title {
  margin: 0 0 6px;
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.welcome-sub {
  margin: 0 0 var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  line-height: 1.55;
}

.welcome-cats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-bottom: 12px;
}

.welcome-cat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--color-border-default);
  background: #fff;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.welcome-cat.active {
  border-color: var(--color-primary-400);
  background: var(--color-primary-50);
  color: var(--color-primary-700);
}

.quick-cmds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  text-align: left;
}

.quick-cmd {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-default);
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.quick-cmd:hover {
  border-color: var(--color-primary-400);
  box-shadow: var(--shadow-sm);
}

.quick-cmd-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.quick-cmd-hint {
  display: block;
  margin-top: 2px;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.chat-quick-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--color-border-default);
  background: #f1f5f9;
  flex-shrink: 0;
}

.strip-label {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--color-primary-600);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.strip-scroll {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  flex: 1;
  padding-bottom: 2px;
}

.strip-cmd {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border-default);
  background: #fff;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.strip-cmd:hover:not(:disabled) {
  border-color: var(--color-primary-400);
  color: var(--color-primary-700);
}

.msg-row.user { align-self: flex-end; max-width: 85%; }
.msg-row.agent { align-self: flex-start; max-width: 90%; }

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: var(--text-sm);
  line-height: 1.5;
}

.msg-bubble.user {
  background: var(--color-primary-600);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-bubble.agent {
  background: #fafbfc;
  border: 1px solid var(--color-border-default);
  border-bottom-left-radius: 4px;
}

.msg-bubble.thinking { color: var(--color-text-muted); font-style: italic; }

.msg-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: var(--text-sm);
  opacity: 0.85;
}

.msg-layer { color: var(--color-primary-500); }
.msg-who { font-weight: 600; }

.msg-tags {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
}

.chat-foot {
  flex-shrink: 0;
  padding: var(--space-3);
  border-top: 1px solid var(--color-border-default);
  background: #fafbfc;
}

.chat-foot-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-2);
  flex-wrap: wrap;
  gap: var(--space-2);
}

.chat-btns { display: flex; gap: var(--space-2); }

@media (max-width: 1100px) {
  .agent-rail { display: none !important; }
}
</style>

<style>
.ops-drawer .el-drawer__body {
  padding: 0;
  height: 100%;
  overflow: hidden;
}

.ops-drawer .ops-rail {
  width: 100%;
  height: 100%;
  border-left: none;
  border-radius: 0;
}

.timeline-drawer .el-drawer__body {
  padding: 12px 16px;
  height: calc(100% - 56px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.timeline-drawer .cmd-inspect {
  height: 100%;
}
</style>
