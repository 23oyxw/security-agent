<template>
  <div class="agent-page">
    <!-- 精简顶栏 -->
    <header class="agent-bar">
      <div class="agent-bar-left">
        <span class="agent-bar-title">{{ agentPage.label }}</span>
        <el-tag size="small" effect="plain" type="info">{{ agentPage.layerLabel }}</el-tag>
        <el-segmented v-model="agentStore.mode" :options="modeOptions" size="small" />
      </div>
      <div class="agent-bar-right">
        <el-button size="small" plain @click="drawerOpen = true">流水线 / 分析</el-button>
        <PipelineBtn action="clear" size="small" @click="clearChat" />
      </div>
    </header>

    <!-- 对话主体：占满剩余高度 -->
    <div class="chat-shell">
      <div
        v-if="agentStore.mode === 'execute' && agentStore.currentPlan && !agentStore.canExecute"
        class="chat-notice"
      >
        执行模式未解锁：请先在计划模式完成 L1，并等待 L2 通过
      </div>

      <div class="chat-messages" ref="messagesRef">
        <div v-if="!messages.length && !thinking" class="chat-welcome">
          <p class="welcome-title">输入运维指令，先 L1 分析再 L3 执行</p>
          <p class="welcome-sub">右侧「流水线 / 分析」可查看五层状态与计划详情</p>
          <div class="quick-cmds">
            <button
              v-for="cmd in quickCommands"
              :key="cmd"
              type="button"
              class="quick-cmd"
              @click="applyQuick(cmd)"
            >{{ cmd }}</button>
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

    <!-- 流水线/分析：按需抽屉，不阻塞对话区 -->
    <el-drawer v-model="drawerOpen" title="流水线与分析" direction="rtl" size="380px" destroy-on-close>
      <el-tabs v-model="sideTab">
        <el-tab-pane label="状态" name="pipeline">
          <OrchestratorPipeline
            v-if="drawerOpen"
            :agents="agentStore.agentStages"
            :phase="agentStore.dispatchPhase"
          />
        </el-tab-pane>
        <el-tab-pane label="分析" name="plan">
          <PlanPanel
            v-if="agentStore.currentPlan"
            :plan="agentStore.currentPlan"
            :l2-verdict="agentStore.l2Result?.verdict"
          />
          <el-empty v-else description="发送指令后显示 L1 结果" :image-size="48" />
          <ExecutePanel v-if="agentStore.lastExecute" :result="agentStore.lastExecute" @trace="goTrace" />
          <AuditPanel v-if="agentStore.lastAudit" :audit="agentStore.lastAudit" @trace="goTrace" />
        </el-tab-pane>
        <el-tab-pane label="批量" name="batch">
          <BatchQueue
            :queue="agentStore.batchQueue"
            :processing="batchProcessing"
            @enqueue="onBatchEnqueue"
            @clear="agentStore.clearBatch()"
            @select="onBatchSelect"
          />
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'
import { useAgentWs } from '../composables/useAgentWs'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { AGENTS, ORCHESTRATOR } from '../constants/agents'
import { NAV_PAGES } from '../constants/navigation'

const agentPage = NAV_PAGES.agent
const quickCommands = [
  '查看当前系统健康状态',
  '执行安全扫描并生成报告',
  '分析磁盘与内存告警',
  '列出异常进程与开放端口',
]

const OrchestratorPipeline = defineAsyncComponent(() => import('../components/agent/OrchestratorPipeline.vue'))
const PlanPanel = defineAsyncComponent(() => import('../components/agent/PlanPanel.vue'))
const ExecutePanel = defineAsyncComponent(() => import('../components/agent/ExecutePanel.vue'))
const AuditPanel = defineAsyncComponent(() => import('../components/agent/AuditPanel.vue'))
const BatchQueue = defineAsyncComponent(() => import('../components/agent/BatchQueue.vue'))

const modeOptions = ORCHESTRATOR.modes.map(m => ({ label: m.label, value: m.value }))

const inputPlaceholder = computed(() =>
  agentStore.mode === 'plan'
    ? '输入运维指令，Enter 或点 L1 三感知分析'
    : '执行模式：需 plan + L2 通过后点 L3 执行'
)

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const thinkingLabel = ref('')
const messagesRef = ref(null)
const batchProcessing = ref(false)
const autoExecute = ref(false)
const drawerOpen = ref(true)
const sideTab = ref('pipeline')

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
    if (tab === 'pipeline' || tab === 'plan' || tab === 'batch') {
      sideTab.value = tab
      drawerOpen.value = true
    }
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

function goTrace(traceId) {
  router.push({ path: '/trace', query: { id: traceId } })
}

function pushAgentMessage(agent, content, meta, extra = {}) {
  const hit = AGENTS.find(a => a.agent === agent)
  messages.value.push({
    role: 'assistant',
    roleLabel: hit?.displayName || '助手',
    agent,
    content,
    meta,
    timestamp: Date.now(),
    ...extra,
  })
}

async function sendAnalyze() {
  const text = input.value.trim()
  if (!text || thinking.value) return
  messages.value.push({ role: 'user', content: text, timestamp: Date.now() })
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
    drawerOpen.value = true
    sideTab.value = 'plan'
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
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    thinking.value = false
  }
}

function appendExecuteResult(res) {
  pushAgentMessage('core_dispatch', res.reply || '（无回复）', 'L3', {
    plan_id: res.plan_id,
    trace_id: res.trace_id,
  })
}

function appendAuditSummary(audit) {
  pushAgentMessage('audit_iteration', `审计完成 · 工具 ${audit.tools_invoked ?? 0} 次`, 'L4', {
    trace_id: audit.trace_id,
  })
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
    drawerOpen.value = true
    sideTab.value = 'plan'
    ElMessage.success('L3/L4 完成')
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
  drawerOpen.value = true
  sideTab.value = 'batch'
  try {
    await agentStore.processBatchQueue(item => {
      if (item.status === 'analyzing') {
        messages.value.push({ role: 'user', content: `[批量] ${item.message}`, timestamp: Date.now() })
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
  messages.value = [{
    role: 'assistant',
    content: '对话已清空。在下方输入指令，计划模式下点 **L1 三感知分析**。',
    timestamp: Date.now(),
  }]
  agentStore.resetPlan()
}

onMounted(() => {
  messages.value.push({
    role: 'assistant',
    content: '你好，请在**下方输入框**输入运维需求，然后点 **L1 三感知分析**。',
    timestamp: Date.now(),
  })
  connectWs()
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
  gap: var(--space-2);
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

/* 对话壳：flex 子项占满剩余空间 */
.chat-shell {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  border: 2px solid var(--color-primary-400);
  border-radius: var(--radius-lg);
  background: #fff;
  overflow: hidden;
}

.chat-notice {
  flex-shrink: 0;
  padding: 8px 12px;
  font-size: 12px;
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
  background: var(--color-neutral-50);
}

.chat-welcome {
  margin: auto;
  max-width: 520px;
  text-align: center;
  padding: var(--space-6) var(--space-4);
}

.welcome-title {
  margin: 0 0 6px;
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.welcome-sub {
  margin: 0 0 var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.quick-cmds {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.quick-cmd {
  padding: 6px 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border-default);
  background: #fff;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.quick-cmd:hover {
  border-color: var(--color-primary-400);
  color: var(--color-primary-600);
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
  background: var(--color-primary-500);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-bubble.agent {
  background: #fff;
  border: 1px solid var(--color-border-default);
  border-bottom-left-radius: 4px;
}

.msg-bubble.thinking { color: var(--color-text-muted); font-style: italic; }

.msg-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 11px;
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
  background: #fff;
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
</style>
