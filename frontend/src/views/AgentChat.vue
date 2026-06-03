<template>
  <div class="agent-chat">
    <el-row :gutter="12" style="height: calc(100vh - 100px)">
      <!-- 左侧：对话区域 -->
      <el-col :span="18">
        <el-card style="height: 100%; display: flex; flex-direction: column">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🤖 安全运维智能助手 <el-tag size="small" type="primary" effect="dark">L3 编排</el-tag></span>
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <el-tag size="small" type="info">会话: {{ sessionId }}</el-tag>
                <el-tag size="small" :type="useRest ? 'warning' : 'success'">
                  传输: {{ useRest ? 'REST' : 'WebSocket' }}
                </el-tag>
                <el-tag v-if="lastSentChannel" size="small" type="info">上条: {{ lastSentChannel }}</el-tag>
                <el-tag size="small" :type="connected ? 'success' : 'danger'">{{ connected ? '在线' : '离线' }}</el-tag>
                <el-button size="small" plain @click="testApi">测 API</el-button>
                <el-button size="small" type="warning" plain @click="simulateWsFallback">① REST</el-button>
                <el-button size="small" type="success" plain @click="reconnectWs">② WS</el-button>
                <el-button size="small" text @click="clearChat">清空</el-button>
              </div>
            </div>
          </template>
          <el-alert
            v-if="useRest"
            type="warning"
            :closable="false"
            show-icon
            style="margin:0 0 8px"
            title="当前为 REST 模式：请在下方输入框发一条消息（或点快捷按钮）。看到「上条: REST」即验收通过。"
          />

          <!-- 消息列表 -->
          <div ref="msgBox" class="msg-container">
            <div v-if="!messages.length" class="welcome">
              <el-icon :size="48" color="#409EFF"><ChatDotRound /></el-icon>
              <h3>安全运维智能助手</h3>
              <p>本页是 <strong>L3</strong>：负责理解、推理、选择工具或 L2 流程；<strong>Trace</strong> 只记录过程，在「推理溯源」查看。</p>
              <div class="quick-actions">
                <el-button size="small" :disabled="loading" @click="quickSend('查看系统健康状态')">系统健康</el-button>
                <el-button size="small" :disabled="loading" @click="quickSend('扫描系统安全状态')">安全扫描</el-button>
                <el-button size="small" :disabled="loading" @click="quickSend('检查异常进程')">进程检查</el-button>
                <el-button size="small" :disabled="loading" @click="quickSend('分析最近的系统日志')">日志分析</el-button>
                <el-button size="small" type="success" :disabled="loading" @click="quickSend('生成扫描报告')">扫描报告</el-button>
                <el-button size="small" type="warning" :disabled="loading" @click="quickSend('告警响应处理')">告警响应</el-button>
              </div>
            </div>

            <div v-for="(m, i) in messages" :key="i" class="msg-item" :class="m.role">
              <div class="msg-avatar">
                <el-icon v-if="m.role === 'user'" :size="20"><User /></el-icon>
                <el-icon v-else :size="20"><Monitor /></el-icon>
              </div>
              <div class="msg-body">
                <div class="msg-header">
                  <span class="msg-role">{{ m.role === 'user' ? '您' : '安全助手' }}</span>
                  <span class="msg-time">{{ m.time }}</span>
                  <el-tag
                    v-if="m.role === 'assistant' && assistantTokenBrief(m)"
                    size="small"
                    type="info"
                    effect="plain"
                    class="msg-token-badge"
                  >{{ assistantTokenBrief(m) }}</el-tag>
                </div>
                <div class="msg-content" v-html="renderContent(m.content)"></div>
                <!-- 工具调用信息 -->
                <div v-if="l1ToolsForMessage(m).length" class="msg-tools">
                  <el-divider content-position="left" style="margin:8px 0">
                    <el-icon><Connection /></el-icon> L1 调用 {{ l1ToolsForMessage(m).length }} 次
                  </el-divider>
                  <el-tag v-for="t in l1ToolsForMessage(m)" :key="t" size="small" type="info" style="margin:2px">L1 · {{ t }}</el-tag>
                </div>
                <!-- 风险等级 -->
                <div v-if="m.risk_level && m.risk_level !== 'low'" class="msg-risk">
                  <el-tag :type="m.risk_level === 'high' ? 'danger' : 'warning'" size="small" effect="dark">
                    ⚠️ 风险等级: {{ m.risk_level }}
                  </el-tag>
                </div>
                <!-- 执行分层 L3/L2 -->
                <div v-if="m.role === 'assistant' && m.execution_meta?.layer" class="msg-layer">
                  <el-tag :type="m.execution_meta.layer === 'L2' ? 'success' : 'primary'" size="small" effect="dark">
                    {{ m.execution_meta.layer_title || m.execution_meta.layer }}
                  </el-tag>
                  <el-tag v-if="m.execution_meta.route" size="small" type="info" style="margin-left:4px">{{ m.execution_meta.route }}</el-tag>
                  <span v-if="m.execution_meta.hint" class="layer-hint">{{ m.execution_meta.hint }}</span>
                </div>
                <!-- 可观测性 -->
                <div v-if="m.trace_id || (m.degradation_level && m.degradation_level !== 'S0') || m.fallback_used" class="msg-obs">
                  <el-tag v-if="m.trace_id" size="small" type="warning" style="margin:2px;cursor:pointer" @click="goTrace(m.trace_id)">Trace 记录: {{ m.trace_id }}</el-tag>
                  <el-tag v-if="m.degradation_level && m.degradation_level !== 'S0'" size="small" type="warning" style="margin:2px">{{ m.degradation_level }}</el-tag>
                  <el-tag v-if="m.fallback_used" size="small" type="warning" style="margin:2px">Fallback</el-tag>
                </div>
                <!-- Token / L2 流程（助手消息始终展示一行） -->
                <div v-if="m.role === 'assistant'" class="msg-cost">
                  <el-tag v-if="m.skill_flow && m.execution_meta?.layer !== 'L2'" size="small" type="success" style="margin:2px">L2: {{ m.skill_flow }}</el-tag>
                  <el-tag size="small" :type="tokenDetail(m).total ? 'info' : 'warning'" style="margin:2px">
                    {{ tokenDetail(m).line }}
                  </el-tag>
                </div>
              </div>
            </div>

            <div v-if="loading" class="msg-item assistant">
              <div class="msg-avatar"><el-icon :size="20"><Monitor /></el-icon></div>
              <div class="msg-body">
                <div class="msg-content thinking">
                  <span class="dot-typing"></span> 思考中...
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <el-input
              v-model="input"
              type="textarea"
              :rows="2"
              placeholder="输入安全运维问题，例如：帮我检查系统安全状态、分析最近的登录日志..."
              @keydown.enter.ctrl="send"
              @keydown.enter.exact.prevent="send"
              :disabled="loading"
              resize="none"
            />
            <div class="input-actions">
              <span class="input-hint">Enter 发送 · Ctrl+Enter 换行</span>
              <el-button type="primary" :loading="loading" @click="send" :disabled="!input.trim()">
                <el-icon><Promotion /></el-icon> 发送
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：会话信息（可滚动） -->
      <el-col :span="6" class="right-panel">
        <ArchitectureLayers highlight="L3" :trace-id="lastTraceId" />
        <el-card header="Token · 费用" style="margin-bottom:10px">
          <div class="token-panel">
            <div class="token-panel-row">
              <span class="token-panel-label">本会话 API 计费</span>
              <span class="token-panel-value">{{ formatTokenNum(sessionTokenStats.total) }} tok</span>
            </div>
            <div class="token-panel-row">
              <span class="token-panel-label">累计费用（估）</span>
              <span class="token-panel-value cost-cny">{{ sessionTokenStats.costCnyDisplay }}</span>
            </div>
            <div class="token-panel-row">
              <span class="token-panel-label">输入 / 输出</span>
              <span class="token-panel-sub">{{ formatTokenNum(sessionTokenStats.prompt) }} ↑ · {{ formatTokenNum(sessionTokenStats.completion) }} ↓</span>
            </div>
            <el-divider style="margin:10px 0" />
            <div class="token-panel-row">
              <span class="token-panel-label">上下文占比</span>
              <span class="token-panel-sub">{{ contextBar.label }}</span>
            </div>
            <el-progress
              :percentage="contextBar.percent"
              :status="contextBar.status"
              :stroke-width="10"
              style="margin:6px 0 10px"
            />
            <div class="token-panel-row">
              <span class="token-panel-label">上条 API 费用</span>
              <span class="token-panel-value cost-cny">{{ lastReplyTokenStats.costDisplay || '—' }}</span>
            </div>
            <div class="token-panel-row">
              <span class="token-panel-label">上条计费 token</span>
              <span class="token-panel-value token-panel-last">{{ lastReplyTokenStats.line }}</span>
            </div>
            <div v-if="lastReplyTokenStats.model" class="token-panel-model">模型: {{ lastReplyTokenStats.model }}</div>
            <div v-if="lastReplyTokenStats.pending" class="token-panel-hint">正在从 Trace 补全统计…</div>
            <el-divider style="margin:10px 0" />
            <div style="display:flex;gap:8px">
              <el-button size="small" @click="router.push('/trace')">
                <el-icon><List /></el-icon> Trace 溯源
              </el-button>
              <el-button size="small" @click="router.push('/alerts')">
                <el-icon><Bell /></el-icon> 告警管理
              </el-button>
            </div>
            <div class="token-panel-hint">费用按模型单价×API 计费 token</div>
          </div>
        </el-card>

        <el-card header="会话信息" style="margin-bottom:10px">
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="会话 ID">{{ sessionId }}</el-descriptions-item>
            <el-descriptions-item label="传输">{{ transport === 'ws' ? 'WebSocket' : 'HTTP REST' }}</el-descriptions-item>
            <el-descriptions-item label="消息数">{{ messages.length }}</el-descriptions-item>
            <el-descriptions-item label="工具调用">{{ totalTools }}</el-descriptions-item>
            <el-descriptions-item label="最近 Trace">{{ lastTraceId || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card style="margin-bottom:10px">
          <template #header>
            <span>可用 Skill</span>
            <el-text type="info" size="small" style="margin-left:8px">点击即在助手中发送</el-text>
          </template>
          <div v-if="flowSkills.length" class="skill-group-title">
            <el-tag type="warning" size="small" effect="plain">L2</el-tag>
            <span>固定流程（Skill 流程页同款）</span>
          </div>
          <div
            v-for="skill in flowSkills"
            :key="'flow-' + skill.name"
            class="skill-item"
            @click="quickSend(skill.prompt)"
          >
            <el-icon :color="skill.color"><component :is="skill.icon" /></el-icon>
            <div class="skill-item-body">
              <div class="skill-item-title">{{ skill.label }}</div>
              <div class="skill-item-desc">{{ skill.desc }}</div>
            </div>
          </div>
          <el-divider v-if="flowSkills.length && mcpSkills.length" style="margin:10px 0" />
          <div v-if="mcpSkills.length" class="skill-group-title">
            <el-tag type="success" size="small" effect="plain">L1</el-tag>
            <span>MCP 能力（L3 编排调工具）</span>
          </div>
          <div
            v-for="skill in mcpSkills"
            :key="'mcp-' + skill.name"
            class="skill-item"
            @click="quickSend(skill.prompt)"
          >
            <el-icon :color="skill.color"><component :is="skill.icon" /></el-icon>
            <div class="skill-item-body">
              <div class="skill-item-title">{{ skill.label }}</div>
              <div class="skill-item-desc">{{ skill.desc }}</div>
            </div>
          </div>
          <el-empty v-if="!flowSkills.length && !mcpSkills.length" description="加载中..." :image-size="30" />
        </el-card>

        <el-card v-if="recentTools.length" header="最近工具调用">
          <el-timeline>
            <el-timeline-item v-for="(t, i) in recentTools" :key="i" :timestamp="t.time" placement="top" :type="t.success ? 'success' : 'danger'">
              <span style="font-size:13px">{{ t.name }}</span>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useMcpStore } from '../stores/mcp'
import { useAgentWs } from '../composables/useAgentWs'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const mcpStore = useMcpStore()
const { transport, connect, disconnect, chatViaWs } = useAgentWs()

const forceRestMode = ref(false)
const lastSentChannel = ref('')

const useRest = computed(() => forceRestMode.value || transport.value !== 'ws')

function simulateWsFallback() {
  forceRestMode.value = true
  disconnect()
  ElMessage.warning('已切换 REST：请点「扫描报告」或输入后发送，看到标签「上条: REST」即通过')
}

function reconnectWs() {
  forceRestMode.value = false
  lastSentChannel.value = ''
  connect()
  ElMessage.success('已尝试重连 WebSocket，标签应变绿「传输: WebSocket」')
}

async function testApi() {
  try {
    const h = await api.get('/health')
    ElMessage.success(`API 正常 v${h.version || '?'} @ ${window.location.host}`)
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '网络错误'
    ElMessage.error(`API 不可达: ${msg}。请执行 bash boot_start.sh 并用 http://127.0.0.1:8900 打开`)
  }
}

const input = ref(''), messages = ref([]), loading = ref(false), msgBox = ref(null)
const connected = ref(true)
const sessionId = ref('s-' + Math.random().toString(36).slice(2, 8))

const flowSkills = ref([])
const mcpSkills = ref([])
const recentTools = ref([])

const totalTools = computed(() => messages.value.reduce((s, m) => s + (m.tools_used?.length || 0), 0))

function messageTokenTotal(m) {
  const tu = m?.token_usage || {}
  return Number(tu.total_tokens ?? m?.cost_tokens ?? 0) || 0
}

const sessionTokenStats = computed(() => {
  let prompt = 0
  let completion = 0
  let total = 0
  let costCny = 0
  for (const m of messages.value) {
    if (m.role !== 'assistant') continue
    const tu = m.token_usage || {}
    prompt += Number(tu.prompt_tokens || 0)
    completion += Number(tu.completion_tokens || 0)
    total += messageTokenTotal(m)
    costCny += Number(m.cost_estimate?.cost?.cny || 0)
  }
  return {
    prompt,
    completion,
    total,
    costCny,
    costCnyDisplay: costCny > 0 ? formatCny(costCny) : '—',
  }
})

const contextBar = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const cu = messages.value[i].context_usage
    if (cu && cu.context_limit) {
      const pct = Math.min(Number(cu.usage_percent_raw ?? cu.usage_percent ?? 0), 100)
      const est = Number(cu.estimated_tokens || 0)
      const limit = Number(cu.context_limit || 0)
      return {
        percent: pct,
        limit,
        label: `${formatTokenNum(est)} / ${formatTokenNum(limit)}（${pct}%）`,
        status: cu.is_over_limit ? 'exception' : pct >= 85 ? 'warning' : undefined,
      }
    }
  }
  return { percent: 0, limit: 124000, label: '—', status: undefined }
})

const lastReplyTokenStats = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'assistant') return tokenDetail(m)
  }
  return { total: 0, prompt: 0, completion: 0, line: '—', model: '', pending: false }
})

const lastTraceId = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].trace_id) return messages.value[i].trace_id
  }
  return ''
})

function formatTokenNum(n) {
  const v = Number(n) || 0
  return v.toLocaleString('zh-CN')
}

function formatCny(v) {
  const n = Number(v) || 0
  if (n >= 1) return `≈ ¥${n.toFixed(3)}`
  if (n >= 0.01) return `≈ ¥${n.toFixed(2)}`
  if (n > 0) return `≈ ${(n * 100).toFixed(1)} 分`
  return '¥0'
}

function now() { return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }

function scroll() { nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight }) }

function renderContent(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>').replace(/`([^`]+)`/g, '<code>$1</code>')
}

function tokenDetail(m) {
  if (m.skill_flow && !messageTokenTotal(m)) {
    return { total: 0, prompt: 0, completion: 0, line: 'L2 固定流程 · 不消耗 LLM', costDisplay: '', model: '', pending: false }
  }
  const tu = m.token_usage || {}
  const total = messageTokenTotal(m)
  const prompt = Number(tu.prompt_tokens || 0)
  const completion = Number(tu.completion_tokens || 0)
  const costDisplay = m.cost_estimate?.display_cny || (m.cost_estimate?.cost?.cny ? formatCny(m.cost_estimate.cost.cny) : '')
  if (!total) {
    const hint = (m.tools_used?.length || 0) > 0 ? 'LLM 统计未返回（见 Trace）' : '无 LLM 调用'
    return { total: 0, prompt: 0, completion: 0, line: hint, costDisplay: costDisplay || '—', model: m.model_used || '', pending: Boolean(m._tokenPending) }
  }
  const ctxPct = m.context_usage?.usage_percent
  const ctxSuffix = ctxPct != null ? ` · 上下文 ${ctxPct}%` : ''
  const line = `${formatTokenNum(prompt)}↑ ${formatTokenNum(completion)}↓ · ${formatTokenNum(total)}${costDisplay ? ' · ' + costDisplay : ''}${ctxSuffix}`
  return { total, prompt, completion, line, costDisplay, model: m.model_used || '', pending: false }
}

function assistantTokenBrief(m) {
  const d = tokenDetail(m)
  if (m.skill_flow && !messageTokenTotal(m)) return 'L2'
  if (d.costDisplay && d.costDisplay !== '—') return d.costDisplay
  if (d.total) return `${formatTokenNum(d.total)} tok`
  if (m.skill_flow) return 'L2'
  return ''
}

function normalizeChatBody(raw) {
  const body = raw?.data ?? raw ?? {}
  const tu = body.token_usage || {}
  const total = Number(tu.total_tokens ?? body.cost_tokens ?? 0) || 0
  return {
    reply: body.reply || body.message || '（无回复）',
    tools_used: body.tools_used || [],
    risk_level: body.risk_level || 'low',
    cost_tokens: total,
    token_usage: {
      prompt_tokens: Number(tu.prompt_tokens ?? 0),
      completion_tokens: Number(tu.completion_tokens ?? 0),
      total_tokens: total,
    },
    model_used: body.model_used || '',
    skill_flow: body.skill_flow || '',
    trace_id: body.trace_id || '',
    degradation_level: body.degradation_level || 'S0',
    fallback_used: Boolean(body.fallback_used),
    cost_estimate: body.cost_estimate || {},
    context_usage: body.context_usage || {},
    execution_meta: body.execution_meta || {},
    plan_summary: body.plan_summary || {},
  }
}

async function enrichTokensFromTrace(msg) {
  if (!msg.trace_id || messageTokenTotal(msg) > 0) return
  msg._tokenPending = true
  try {
    const bundle = await api.get(`/trace/${msg.trace_id}/export`)
    const report = bundle?.reasoning_report || bundle?.reasoning?.report
    const used = Number(report?.tokens_used ?? report?.summary?.tokens_used ?? 0)
    if (used > 0) {
      msg.cost_tokens = used
      msg.token_usage = { ...msg.token_usage, total_tokens: used }
      msg.model_used = msg.model_used || report?.model || ''
    }
  } catch {
    /* ignore */
  } finally {
    msg._tokenPending = false
  }
}

function goTrace(traceId) {
  if (traceId) router.push({ path: '/trace', query: { id: traceId } })
}

/** 本条回复实际调用的 L1 工具名（不含 L2 flow: 前缀） */
function l1ToolsForMessage(m) {
  const fromMeta = m.execution_meta?.l1_tools
  if (Array.isArray(fromMeta) && fromMeta.length) return fromMeta
  return (m.tools_used || [])
    .filter(t => typeof t === 'string' && !t.startsWith('flow:'))
    .map(t => (typeof t === 'string' ? t : t.tool || t.name))
    .filter(Boolean)
}

function clearChat() { messages.value = []; recentTools.value = []; sessionId.value = 's-' + Math.random().toString(36).slice(2, 8) }

function quickSend(msg) {
  sendMessage(msg)
}

async function send() {
  await sendMessage(input.value)
}

async function sendMessage(raw) {
  if (!raw?.trim() || loading.value) return
  const msg = raw.trim()
  messages.value.push({ role: 'user', content: msg, time: now() })
  input.value = ''
  loading.value = true
  connected.value = true
  scroll()
  try {
    let res
    let channel = 'REST'
    if (!useRest.value) {
      try {
        res = await chatViaWs(msg)
        channel = 'WebSocket'
      } catch {
        ElMessage.warning('WebSocket 失败，已改用 REST')
        res = await api.post('/agent/chat', { message: msg, session_id: sessionId.value })
        channel = 'REST'
      }
    } else {
      res = await api.post('/agent/chat', { message: msg, session_id: sessionId.value })
      channel = 'REST'
    }
    lastSentChannel.value = channel
    const body = normalizeChatBody(res)
    const assistantMsg = {
      role: 'assistant',
      content: body.reply,
      time: now(),
      tools_used: body.tools_used,
      risk_level: body.risk_level,
      cost_tokens: body.cost_tokens,
      token_usage: body.token_usage,
      model_used: body.model_used,
      skill_flow: body.skill_flow,
      trace_id: body.trace_id,
      degradation_level: body.degradation_level,
      fallback_used: body.fallback_used,
      cost_estimate: body.cost_estimate,
      context_usage: body.context_usage,
      execution_meta: body.execution_meta,
      plan_summary: body.plan_summary,
    }
    messages.value.push(assistantMsg)
    if (!body.cost_tokens && body.trace_id) {
      enrichTokensFromTrace(assistantMsg)
    }
    const tools = body.tools_used || []
    if (tools.length) {
      tools.forEach(t => {
        recentTools.value.unshift({ name: typeof t === 'string' ? t : t.tool || t.name, time: now(), success: true })
      })
      if (recentTools.value.length > 10) recentTools.value = recentTools.value.slice(0, 10)
    }
  } catch (e) {
    const detail = e.response?.data?.detail
    const errText = typeof detail === 'object' ? JSON.stringify(detail) : (detail || e.message || '网络错误')
    messages.value.push({
      role: 'assistant',
      content: `请求失败 (${lastSentChannel.value || '—'}): ${errText}\n\n提示: 先点「测 API」；REST 验收请点「① REST」后发「生成扫描报告」`,
      time: now(),
    })
    connected.value = false
    ElMessage.error(errText.slice(0, 120))
  } finally { loading.value = false; scroll() }
}

const FLOW_SKILL_META = {
  scan_report: { label: '扫描报告', icon: 'Document', color: '#409EFF', prompt: '生成扫描报告', desc: 'L2：扫描+端口+HTML' },
  alert_response: { label: '告警响应', icon: 'Bell', color: '#E6A23C', prompt: '告警响应处理', desc: 'L2：告警 Skill 路由' },
  secure_exec: { label: '安全命令执行', icon: 'Lock', color: '#F56C6C', prompt: '安全执行 ls -la /tmp', desc: 'L2：三层防御→执行（可不加反引号）' },
  block_process: { label: '进程拦截 (kill)', icon: 'CircleClose', color: '#F56C6C', prompt: '拦截进程 4911', desc: 'L2：kill/终止 PID' },
}

onMounted(async () => {
  connect()
  try {
    await mcpStore.fetchServers()
    const mcpRes = { servers: mcpStore.servers }
    const iconMap = {
      healthcheck: { label: '健康巡检', icon: 'FirstAidKit', color: '#67C23A', prompt: '执行一次系统健康巡检', desc: 'L1：CPU/内存/磁盘/网络' },
      scan: { label: '安全扫描', icon: 'Search', color: '#409EFF', prompt: '扫描系统安全状态', desc: 'L3：多工具+LLM（≠ L2 扫描报告）' },
      process: { label: '进程管理', icon: 'List', color: '#E6A23C', prompt: '检查异常进程', desc: 'L1：进程列表与风险' },
      log_analyzer: { label: '日志分析', icon: 'Document', color: '#909399', prompt: '分析最近的系统日志', desc: 'L1：日志异常模式' },
      security_hardening: { label: '安全加固', icon: 'Lock', color: '#F56C6C', prompt: '执行安全加固扫描', desc: 'L1：SSH/防火墙/漏洞' },
      monitor: { label: '实时监控', icon: 'View', color: '#409EFF', prompt: '启动监控服务', desc: 'L1：进程与路径监控' },
      knowledge: { label: '安全知识库', icon: 'Reading', color: '#67C23A', prompt: '检索安全知识库', desc: 'L1：Playbook 查询' },
      config_manager: { label: '配置管理', icon: 'Files', color: '#E6A23C', prompt: '审计配置文件状态', desc: 'L1：配置变更检测' },
      incident_responder: { label: '故障响应', icon: 'Warning', color: '#F56C6C', prompt: '执行故障诊断', desc: 'L1：根因分析与自愈' },
      terminal: { label: '终端运维', icon: 'Terminal', color: '#909399', prompt: '自主运维：全量安全巡检（端口、高危进程、健康、敏感路径）', desc: 'L3：多步自动规划' },
      system_info: { label: '系统信息', icon: 'Platform', color: '#409EFF', prompt: '运行一键综合体检', desc: 'L1：全面安全检查' },
    }
    let flows = []
    try {
      const flowRes = await api.get('/skills/flows/')
      flows = (flowRes.flows || []).map((f) => {
        const meta = FLOW_SKILL_META[f.name] || {}
        return {
          name: f.name,
          label: f.display_name || f.name,
          icon: meta.icon || 'Document',
          color: meta.color || '#409EFF',
          prompt: meta.prompt || f.name,
          desc: meta.desc || f.description || 'L2 固定流程',
        }
      })
    } catch {
      flows = Object.entries(FLOW_SKILL_META).map(([name, meta]) => ({
        name,
        label: meta.label || name,
        ...meta,
      }))
    }
    const mcps = (mcpRes.servers || [])
      .filter(s => iconMap[s.name])
      .map(s => {
        const meta = iconMap[s.name]
        return { name: s.name, label: meta.label || s.name, ...meta }
      })
    flowSkills.value = flows
    mcpSkills.value = mcps
  } catch {}
})

onUnmounted(() => disconnect())
</script>

<style scoped>
.agent-chat { height: calc(100vh - 120px); }
.msg-container { flex: 1; overflow-y: auto; padding: 12px; background: #f9f9f9; border-radius: 8px; margin-bottom: 12px; min-height: 300px; }
.welcome { text-align: center; padding: 60px 20px; color: #666; }
.welcome h3 { margin: 12px 0 8px; color: #333; }
.welcome p { font-size: 13px; margin-bottom: 16px; }
.quick-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; position: relative; z-index: 2; }
.quick-actions .el-button { pointer-events: auto; }
.msg-item { display: flex; gap: 10px; margin: 12px 0; }
.msg-item.user { flex-direction: row-reverse; }
.msg-item.user .msg-body { align-items: flex-end; }
.msg-item.user .msg-content { background: #ecf5ff; border-color: #d9ecff; }
.msg-avatar { width: 36px; height: 36px; border-radius: 50%; background: #f0f2f5; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.msg-item.user .msg-avatar { background: #409EFF; color: #fff; }
.msg-body { display: flex; flex-direction: column; max-width: 75%; }
.msg-header { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.msg-role { font-size: 12px; font-weight: 600; color: #333; }
.msg-time { font-size: 11px; color: #999; }
.msg-content { background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; padding: 10px 14px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.msg-content :deep(code) { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 13px; color: #c7254e; }
.msg-tools { margin-top: 6px; }
.msg-risk { margin-top: 4px; }
.msg-cost { margin-top: 4px; }
.msg-token-badge { margin-left: 4px; }
.token-panel { font-size: 13px; }
.token-panel-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; gap: 8px; }
.token-panel-label { color: #909399; flex-shrink: 0; }
.token-panel-value { font-weight: 600; color: #303133; font-variant-numeric: tabular-nums; }
.token-panel-last { font-size: 12px; text-align: right; max-width: 65%; word-break: break-word; }
.token-panel-sub { color: #606266; font-variant-numeric: tabular-nums; }
.token-panel-model { font-size: 11px; color: #909399; margin-top: 4px; }
.token-panel-hint { font-size: 11px; color: #909399; margin-top: 4px; line-height: 1.4; }
.cost-cny { color: #e6a23c; }
.msg-layer { margin-top: 6px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.layer-hint { font-size: 11px; color: #909399; margin-left: 4px; flex: 1 1 100%; }
.thinking { color: #999; display: flex; align-items: center; gap: 8px; }
.dot-typing { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #409EFF; animation: blink 1.4s infinite both; }
@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }
.input-area { border-top: 1px solid #eee; padding-top: 8px; }
.input-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; }
.input-hint { font-size: 11px; color: #999; }
.skill-group-title { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #606266; margin: 4px 0 6px; }
.skill-item { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.2s; }
.skill-item:hover { background: #f5f7fa; }
.skill-item-body { flex: 1; min-width: 0; }
.skill-item-title { font-weight: 500; font-size: 13px; }
.skill-item-desc { color: #999; font-size: 11px; line-height: 1.4; }
</style>