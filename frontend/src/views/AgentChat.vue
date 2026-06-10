<template>
  <div class="agent-chat">
    <div class="page-header">
      <div>
        <h1 class="page-title">智能助手</h1>
        <p class="page-subtitle">与安全运维 Agent 对话 · 支持命令执行、知识检索、安全评估</p>
      </div>
      <div class="page-actions">
        <el-button size="small" plain @click="clearChat">
          <el-icon style="margin-right:4px"><Delete /></el-icon> 清空对话
        </el-button>
      </div>
    </div>

    <div class="chat-layout">
      <div class="chat-main">
        <div class="chat-messages" ref="messagesRef">
          <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
            <div class="message-avatar">
              <div class="avatar" :class="msg.role">
                <el-icon :size="16"><component :is="msg.role === 'user' ? 'UserFilled' : 'MagicStick'" /></el-icon>
              </div>
            </div>
            <div class="message-body">
              <div class="message-header">
                <span class="message-role">{{ msg.role === 'user' ? '你' : 'Agent' }}</span>
                <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="message-content" v-html="renderContent(msg.content)"></div>
              <div v-if="msg.tool_calls?.length" class="message-tools">
                <div v-for="(tc, ti) in msg.tool_calls" :key="ti" class="tool-call">
                  <span class="tool-call-tag">{{ tc.name }}</span>
                  <span class="tool-call-args">{{ JSON.stringify(tc.arguments) }}</span>
                </div>
              </div>
              <div v-if="msg.tool_results?.length" class="message-tools">
                <div v-for="(tr, ti) in msg.tool_results" :key="ti" class="tool-result">
                  <span class="tool-result-tag">{{ tr.name }}</span>
                  <pre class="tool-result-content">{{ typeof tr.result === 'string' ? tr.result.slice(0, 500) : JSON.stringify(tr.result).slice(0, 500) }}</pre>
                </div>
              </div>
            </div>
          </div>
          <div v-if="thinking" class="message agent">
            <div class="message-avatar">
              <div class="avatar agent">
                <el-icon :size="16"><MagicStick /></el-icon>
              </div>
            </div>
            <div class="message-body">
              <div class="message-header">
                <span class="message-role">Agent</span>
              </div>
              <div class="thinking-indicator">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <div class="input-wrap">
            <el-input
              v-model="input"
              type="textarea"
              :rows="2"
              placeholder="输入你的问题或指令..."
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="thinking"
            />
          </div>
          <div class="input-actions">
            <div class="input-tools">
              <el-tooltip content="知识检索" placement="top">
                <button class="input-tool-btn" @click="toggleKnowledge">
                  <el-icon :size="16"><Reading /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="安全评估" placement="top">
                <button class="input-tool-btn" @click="toggleSafety">
                  <el-icon :size="16"><Lock /></el-icon>
                </button>
              </el-tooltip>
            </div>
            <el-button type="primary" :loading="thinking" @click="sendMessage" :disabled="!input.trim()">
              <el-icon style="margin-right:4px"><Promotion /></el-icon> 发送
            </el-button>
          </div>
        </div>
      </div>

      <aside class="chat-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <h3>快捷指令</h3>
          </div>
          <div class="quick-commands">
            <div v-for="cmd in quickCommands" :key="cmd.label" class="quick-command" @click="insertCommand(cmd.text)">
              <el-icon :size="14"><component :is="cmd.icon" /></el-icon>
              <span>{{ cmd.label }}</span>
            </div>
          </div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <h3>对话历史</h3>
          </div>
          <div class="history-list">
            <div v-for="h in history" :key="h.id" class="history-item" @click="loadHistory(h.id)">
              <span class="history-title">{{ h.title }}</span>
              <span class="history-time">{{ formatTime(h.timestamp) }}</span>
            </div>
            <div v-if="!history.length" class="history-empty">暂无历史记录</div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const messagesRef = ref(null)
const history = ref([])
const streamContent = ref('')
const showSuggestions = ref(true)

// DeepSeek-GUI 风格：消息分组
const messageGroups = computed(() => {
  const groups = []
  let currentGroup = null
  for (const msg of messages.value) {
    if (msg.role === 'user') {
      if (currentGroup) groups.push(currentGroup)
      currentGroup = { user: msg, assistant: null }
    } else if (msg.role === 'assistant' && currentGroup) {
      currentGroup.assistant = msg
      groups.push(currentGroup)
      currentGroup = null
    } else {
      groups.push({ user: null, assistant: msg })
    }
  }
  if (currentGroup) groups.push(currentGroup)
  return groups
})

const quickCommands = [
  { label: '查看系统状态', icon: 'Cpu', text: '查看当前系统运行状态和资源使用情况' },
  { label: '安全扫描', icon: 'Search', text: '执行一次安全扫描，检查异常进程和端口' },
  { label: '日志分析', icon: 'Document', text: '分析最近的系统日志，查找异常' },
  { label: '网络检查', icon: 'Connection', text: '检查网络连接状态和开放端口' },
  { label: '进程管理', icon: 'SetUp', text: '列出当前运行的进程，检查异常进程' },
  { label: '知识检索', icon: 'Reading', text: '搜索安全知识库，查找入侵排查方案' },
]

// 初始欢迎消息（DeepSeek-GUI 风格）
const welcomeMessage = {
  role: 'assistant',
  content: '你好！我是 **安全运维 Agent**，可以帮你：\n\n- 🔍 执行系统安全扫描\n- 📊 分析系统运行状态\n- 🛡️ 评估命令安全性\n- 📚 检索安全知识库\n- 🔧 执行运维操作\n\n请问有什么可以帮你的？',
  timestamp: Date.now(),
}

function formatTime(ts) {
  if (!ts) return ''
  if (typeof ts === 'number') return new Date(ts).toLocaleString('zh-CN')
  return String(ts).replace('T', ' ').slice(0, 19)
}

// DeepSeek-GUI 风格：Markdown 渲染 + 代码高亮 + 命令可点击执行
function renderContent(content) {
  if (!content) return ''
  let html = content
    // 代码块 — bash/sh 块内容变成可点击执行按钮
    .replace(/```(?:bash|sh|shell)?\n([\s\S]*?)```/g, (match, code) => {
      const commands = code.trim().split('\n').filter(c => c.trim() && !c.trim().startsWith('#'))
      const chips = commands.map(c => {
        const escaped = escapeHtml(c.trim().slice(0, 120))
        return `<button class="cmd-chip" onclick="window.__execCmd &amp;&amp; window.__execCmd('${escaped.replace(/'/g, "\\\'")}')" title="点击在安全执行中运行">▶ ${escaped}</button>`
      }).join('')
      return `<div class="code-block-wrapper"><div class="code-block-header"><span>bash</span><button class="copy-btn" onclick="navigator.clipboard.writeText(\`${code.replace(/`/g, '\\`')}\`)">📋 复制</button></div><pre class="code-block"><code>${escapeHtml(code)}</code></pre>${chips ? `<div style="padding:6px 12px;display:flex;flex-wrap:wrap;gap:4px;background:#f8fafc;border-top:1px solid #e5e7eb">${chips}</div>` : ''}</div>`
    })
    // 行内代码 — 检测是否为完整命令并使其可点击
    .replace(/`([^`]+)`/g, (match, code) => {
      const trimmed = code.trim()
      // 看起来像一个命令 (不是单个词)
      if (trimmed.includes(' ') && trimmed.length > 10 && /^[a-z0-9\-/.]+/.test(trimmed)) {
        const escaped = escapeHtml(trimmed.slice(0, 80))
        return `<button class="cmd-chip-inline" onclick="window.__execCmd &amp;&amp; window.__execCmd('${escaped.replace(/'/g, "\\\'")}')" title="点击执行">▶ ${escaped}</button>`
      }
      return `<code class="inline-code">${escapeHtml(trimmed)}</code>`
    })
    // 加粗
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // 列表
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // 换行
    .replace(/\n/g, '<br>')
  return html
}

function setupExecBridge() {
  window.__execCmd = (cmd) => {
    if (!cmd) return
    router.push({ path: '/safety', query: { cmd, intent: 'Agent 建议执行' } })
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
    .replace(/"/g, '"')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 自动滚动
watch([messages, streamContent], scrollToBottom)

async function sendMessage() {
  const text = input.value.trim()
  if (!text || thinking.value) return

  showSuggestions.value = false
  messages.value.push({ role: 'user', content: text, timestamp: Date.now() })
  input.value = ''
  thinking.value = true
  streamContent.value = ''
  scrollToBottom()

  const startTime = Date.now()
  try {
    const res = await api.post('/agent/chat', {
      message: text,
      stream: false,
    }, { timeout: 120000 })
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
    const reply = res.reply || res.response || res.message || res.content || ''
    messages.value.push({
      role: 'assistant',
      content: reply || '（无文本回复）',
      tool_calls: res.tool_calls || [],
      tool_results: res.tool_results || [],
      timestamp: Date.now(),
      meta: reply ? `⏱ ${elapsed}s · ${res.model_used || 'LLM'}` : '—',
    })
  } catch (e) {
    const errMsg = e.code === 'ECONNABORTED' ? '⏰ 请求超时（LLM 推理中，可重试）'
      : e.response?.data?.detail || e.message || '请求失败'
    messages.value.push({
      role: 'assistant',
      content: `❌ ${errMsg}`,
      timestamp: Date.now(),
    })
  } finally {
    thinking.value = false
    streamContent.value = ''
    scrollToBottom()
  }
}

function clearChat() {
  messages.value = []
  showSuggestions.value = true
}

function insertCommand(text) {
  input.value = text
}

function toggleKnowledge() {
  insertCommand('搜索安全知识库：')
}

function toggleSafety() {
  insertCommand('安全评估：')
}

function loadHistory(id) {
  // Placeholder for history loading
}

onMounted(async () => {
  setupExecBridge()
  // 显示欢迎消息
  messages.value.push(welcomeMessage)
  try {
    const res = await api.get('/agent/history').catch(() => ({ history: [] }))
    history.value = res.history || []
  } catch {}
})
</script>

<style scoped>
.agent-chat {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  height: calc(100vh - var(--topbar-height) - var(--space-6) * 2);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-neutral-900);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin: var(--space-1) 0 0;
}

.page-actions {
  display: flex;
  gap: var(--space-2);
}

/* ---- 对话布局 ---- */
.chat-layout {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* ---- 消息区 ---- */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.message {
  display: flex;
  gap: var(--space-3);
  max-width: 85%;
  animation: slide-up var(--duration-normal) var(--ease-out) both;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
  animation-name: slide-left;
}

.message.agent {
  animation-name: slide-right;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar.user {
  background: var(--color-primary-500);
  color: #fff;
}

.avatar.agent {
  background: var(--color-success);
  color: #fff;
}

.message-body {
  min-width: 0;
}

.message-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.message-role {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-neutral-600);
}

.message-time {
  font-size: 10px;
  color: var(--color-neutral-300);
}

.message-content {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--color-neutral-800);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  background: var(--color-neutral-50);
  position: relative;
}

/* Agent 消息左侧色条 */
.message.agent .message-content {
  border-left: 3px solid var(--color-primary-400);
  border-top-left-radius: 0;
}

/* 用户消息右侧色条 */
.message.user .message-content {
  background: var(--color-primary-50);
  color: var(--color-primary-900);
  border-right: 3px solid var(--color-primary-400);
  border-top-right-radius: 0;
}

.message-content :deep(.code-block) {
  background: var(--color-neutral-900);
  color: #e2e5ef;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  margin: var(--space-2) 0;
}

.message-content :deep(code) {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  background: var(--color-neutral-100);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
}

/* ---- 工具调用 ---- */
.message-tools {
  margin-top: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  animation: slide-down var(--duration-normal) var(--ease-out) both;
}

.tool-call, .tool-result {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--color-neutral-50);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
}

.tool-call-tag, .tool-result-tag {
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.tool-call-tag {
  background: var(--color-info-bg);
  color: var(--color-info);
}

.tool-result-tag {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.tool-call-args {
  font-family: var(--font-mono);
  color: var(--color-neutral-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-result-content {
  font-family: var(--font-mono);
  color: var(--color-neutral-600);
  margin: 0;
  overflow-x: auto;
  max-height: 100px;
}

/* ---- 思考指示器 ---- */
.thinking-indicator {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-3);
  align-items: center;
}

.dot {
  width: 4px;
  height: 16px;
  border-radius: var(--radius-full);
  background: var(--color-primary-400);
  animation: wave 1.2s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes wave {
  0%, 100% { transform: scaleY(0.4); opacity: 0.4; }
  50% { transform: scaleY(1); opacity: 1; }
}

/* ---- 输入区 ---- */
.chat-input {
  padding: var(--space-4);
  border-top: 1px solid var(--color-neutral-200);
  transition: border-color var(--duration-fast) var(--ease-out);
}

.chat-input:focus-within {
  border-top-color: var(--color-primary-300);
}

.input-wrap {
  margin-bottom: var(--space-2);
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.input-tools {
  display: flex;
  gap: var(--space-1);
}

.input-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-neutral-400);
  transition: all var(--duration-fast) var(--ease-out);
}

.input-tool-btn:hover {
  background: var(--color-neutral-100);
  color: var(--color-primary-500);
}

/* ---- 侧边栏 ---- */
.chat-sidebar {
  width: 240px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex-shrink: 0;
}

.sidebar-section {
  background: #fff;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.sidebar-section-header {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-neutral-100);
}

.sidebar-section-header h3 {
  margin: 0;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-neutral-500);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.quick-commands {
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.quick-command {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-xs);
  color: var(--color-neutral-600);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

/* 左侧色条展开动画 */
.quick-command::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--color-primary-500);
  transform: scaleY(0);
  transition: transform var(--duration-fast) var(--ease-out);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.quick-command:hover {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
}

.quick-command:hover::before {
  transform: scaleY(1);
}

.history-list {
  padding: var(--space-2);
  max-height: 200px;
  overflow-y: auto;
}

.history-item {
  padding: var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}

.history-item:hover {
  background: var(--color-neutral-50);
}

.history-title {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-neutral-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-time {
  display: block;
  font-size: 10px;
  color: var(--color-neutral-300);
  margin-top: var(--space-1);
}

.history-empty {
  padding: var(--space-4);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-neutral-300);
}

/* 可点击命令芯片 */
.cmd-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; margin: 2px;
  background: linear-gradient(135deg, #4f6ef7, #6366f1);
  color: #fff; border: none; border-radius: var(--radius-full);
  font-size: 11px; font-family: var(--font-mono); cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out); white-space: nowrap; max-width: 280px; overflow: hidden; text-overflow: ellipsis;
}
.cmd-chip:hover { background: linear-gradient(135deg, #4338ca, #4f46e5); transform: scale(1.05); box-shadow: 0 2px 8px rgba(79,110,247,.3); }

.cmd-chip-inline {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 1px 8px; margin: 0 2px;
  background: var(--color-primary-50); color: var(--color-primary-600);
  border: 1px solid var(--color-primary-200); border-radius: var(--radius-sm);
  font-size: 11px; font-family: var(--font-mono); cursor: pointer;
  transition: all .15s; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis;
}
.cmd-chip-inline:hover { background: var(--color-primary-100); border-color: var(--color-primary-400); }

@media (max-width: 900px) {
  .chat-sidebar { display: none; }
}
</style>
