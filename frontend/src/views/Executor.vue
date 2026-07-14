<template>
  <div class="executor">
    <div class="page-header">
      <div>
        <h1 class="page-title">命令执行器</h1>
        <p class="page-subtitle">安全命令执行 · 三层防御评估 · 实时输出</p>
      </div>
    </div>

    <div class="executor-layout">
      <div class="executor-main">
        <div v-if="fromSafety" class="safety-banner">
          <el-icon><CircleCheckFilled /></el-icon>
          <span>已通过三层防御评估，命令可直接执行</span>
          <el-button size="small" text @click="router.push('/safety')">← 返回安全评估</el-button>
        </div>
        <div class="section-card">
          <div class="section-card-header">
            <h3>命令输入</h3>
            <div class="section-card-actions">
              <el-tooltip content="清空输出" placement="top">
                <el-button size="small" plain @click="clearOutput">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
          <div class="executor-body">
            <div class="executor-input">
              <div class="executor-input-wrapper">
                <el-input
                  v-model="command"
                  type="textarea"
                  :rows="3"
                  placeholder="输入要执行的命令，如：ls -la /tmp"
                  @keydown.enter.prevent="execute"
                  @keydown.up.prevent="navigateHistory(-1)"
                  @keydown.down.prevent="navigateHistory(1)"
                  :disabled="executing"
                />
                <!-- CLI-Anything 风格：命令历史下拉 -->
                <div v-if="filteredHistory.length > 0 && command.trim()" class="history-dropdown">
                  <div
                    v-for="(h, i) in filteredHistory"
                    :key="i"
                    class="history-item"
                    :class="{ active: i === historyIndex }"
                    @click="selectHistory(h)"
                  >
                    <el-icon :size="12"><Clock /></el-icon>
                    <span>{{ h }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="executor-options">
              <el-checkbox v-model="sudo">使用 sudo</el-checkbox>
              <el-checkbox v-model="confirm">需要用户确认</el-checkbox>
              <div class="approval-id-input">
                <span class="approval-id-label">审批单号</span>
                <el-input v-model="approvalId" placeholder="可选，审批通过后填入" size="small" style="width:200px" clearable />
              </div>
            </div>
            <div class="executor-actions">
              <el-button type="primary" :loading="executing" @click="execute" :disabled="!command.trim()">
                <el-icon style="margin-right:4px"><CaretRight /></el-icon> 执行
              </el-button>
              <el-button plain @click="command = ''">清空</el-button>
              <span v-if="executionTime" class="exec-time">耗时 {{ executionTime }}ms</span>
            </div>
          </div>
        </div>

        <div class="section-card">
          <div class="section-card-header">
            <h3>执行输出</h3>
            <div class="section-card-actions">
              <el-button size="small" plain @click="copyOutput" v-if="output">
                <el-icon><CopyDocument /></el-icon>
              </el-button>
            </div>
          </div>
          <div class="output-body">
            <div v-if="output" class="output-content">
              <pre class="output-text">{{ output }}</pre>
            </div>
            <div v-else-if="!executing" class="output-empty">
              <el-icon :size="32" color="var(--color-neutral-200)"><Terminal /></el-icon>
              <p>输入命令并点击执行</p>
            </div>
            <div v-if="executing" class="output-loading">
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-text">执行中...</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="executor-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <h3>安全评估</h3>
          </div>
          <div v-if="assessment" class="assessment-body">
            <div class="assessment-verdict" :class="assessment.verdict === 'safe' ? 'safe' : assessment.verdict === 'blocked' ? 'blocked' : 'review'">
              <el-icon v-if="assessment.verdict === 'safe'" :size="16" color="var(--color-success)"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="assessment.verdict === 'blocked'" :size="16" color="var(--color-danger)"><CircleCloseFilled /></el-icon>
              <el-icon v-else :size="16" color="var(--color-warning)"><WarningFilled /></el-icon>
              <span>{{ assessment.verdict === 'safe' ? '安全' : assessment.verdict === 'blocked' ? '已拦截' : '需审核' }}</span>
            </div>
            <div class="assessment-score">
              <span class="assessment-score-label">安全评分</span>
              <span class="assessment-score-value" :class="assessment.verdict === 'safe' ? 'safe' : assessment.verdict === 'blocked' ? 'blocked' : 'review'">{{ assessment.score || assessment.total_score || 0 }}</span>
            </div>
            <div v-if="assessment.layers?.length" class="assessment-layers">
              <div v-for="(layer, i) in assessment.layers" :key="i" class="assessment-layer">
                <div class="assessment-layer-header">
                  <span>{{ layer.name || `第 ${i + 1} 层` }}</span>
                  <span :class="layer.ok ? 'pass' : 'fail'">{{ layer.score || 0 }}分</span>
                </div>
                <div class="assessment-layer-bar">
                  <div class="assessment-layer-fill" :style="{ width: (layer.score || 0) + '%', background: layer.ok ? 'var(--color-success)' : 'var(--color-danger)' }"></div>
                </div>
                <div v-if="layer.reason" class="assessment-layer-reason">{{ layer.reason }}</div>
              </div>
            </div>
          </div>
          <div v-else class="assessment-empty">
            <p>执行命令后将显示安全评估结果</p>
          </div>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <h3>常用命令</h3>
          </div>
          <div class="quick-commands">
            <div v-for="cmd in quickCommands" :key="cmd.label" class="quick-command" @click="command = cmd.cmd">
              <el-icon :size="14"><component :is="cmd.icon" /></el-icon>
              <span>{{ cmd.label }}</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const command = ref(route.query.command || '')
const fromSafety = ref(!!route.query.from_safety)
const sudo = ref(false)
const confirm = ref(true)
const approvalId = ref('')
const executing = ref(false)
const output = ref('')
const executionTime = ref(null)
const assessment = ref(null)
const historyIndex = ref(-1)
const commandHistory = ref([])
const outputRef = ref(null)

// CLI-Anything 风格：命令历史搜索
const filteredHistory = computed(() => {
  if (!command.value.trim()) return []
  return commandHistory.value.filter(h => h.includes(command.value)).slice(0, 8)
})

// 命令语法高亮（模拟终端效果）
const highlightedOutput = computed(() => {
  if (!output.value) return ''
  return output.value
    .replace(/(error|Error|ERROR|failed|Failed|FAILED)/g, '<span class="hl-error">$1</span>')
    .replace(/(warning|Warning|WARNING)/g, '<span class="hl-warn">$1</span>')
    .replace(/(\d{1,3}\.){3}\d{1,3}/g, '<span class="hl-ip">$1</span>')
    .replace(/`[^`]+`/g, '<span class="hl-code">$&</span>')
})

// 自动滚动到输出底部
watch(output, async () => {
  await nextTick()
  if (outputRef.value) {
    outputRef.value.scrollTop = outputRef.value.scrollHeight
  }
})

const quickCommands = [
  { label: '查看目录', icon: 'FolderOpened', cmd: 'ls -la /tmp' },
  { label: '查看进程', icon: 'SetUp', cmd: 'ps aux --sort=-%cpu | head -20' },
  { label: '磁盘使用', icon: 'DataBoard', cmd: 'df -h' },
  { label: '内存使用', icon: 'Coin', cmd: 'free -h' },
  { label: '网络连接', icon: 'Connection', cmd: 'ss -tlnp' },
  { label: '系统日志', icon: 'Document', cmd: 'journalctl -n 50 --no-pager' },
  { label: '系统信息', icon: 'Monitor', cmd: 'uname -a' },
  { label: '运行时间', icon: 'Timer', cmd: 'uptime' },
]

async function execute() {
  if (!command.value.trim() || executing.value) return
  executing.value = true
  output.value = ''
  assessment.value = null
  const t0 = Date.now()
  try {
    const payload = {
      command: command.value,
      sudo: sudo.value,
      require_confirmation: confirm.value,
    }
    if (approvalId.value) payload.approval_id = approvalId.value
    const res = await api.post('/executor/execute', payload)
    executionTime.value = Date.now() - t0
    output.value = res.output || res.stdout || ''
    if (res.stderr) output.value += '\n\n[STDERR]\n' + res.stderr
    assessment.value = res.assessment || res.safety || null
    if (res.blocked) {
      ElMessage.warning('命令已被安全策略拦截')
    } else if (res.exit_code !== 0) {
      ElMessage.warning(`命令执行异常，退出码: ${res.exit_code}`)
    } else {
      ElMessage.success('命令执行成功')
    }
  } catch (e) {
    executionTime.value = Date.now() - t0
    const detail = e.response?.data?.detail || e.message || '未知错误'
    output.value = `执行失败: ${detail}`
    assessment.value = e.response?.data?.assessment || null
    if (detail.includes('审批') || detail.includes('人工')) {
      ElMessage.warning('⚠️ 需要人工审批')
      output.value = `⚠️ 权限不足，需要人工审批\n\n${detail}\n\n→ 请前往「L2 安全防护沙箱」页面提交审批申请\n→ 审批通过后将获得审批单号\n→ 在此处填入审批单号后重新执行`
    } else {
      ElMessage.error('执行失败: ' + detail)
    }
  } finally {
    executing.value = false
  }
}

function navigateHistory(direction) {
  const history = filteredHistory.value
  if (!history.length) return
  historyIndex.value += direction
  if (historyIndex.value < 0) historyIndex.value = 0
  if (historyIndex.value >= history.length) historyIndex.value = history.length - 1
  command.value = history[historyIndex.value]
}

function selectHistory(cmd) {
  command.value = cmd
  historyIndex.value = -1
}

function clearOutput() {
  output.value = ''
  assessment.value = null
  executionTime.value = null
}

async function copyOutput() {
  try {
    await navigator.clipboard.writeText(output.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败')
  }
}
</script>

<style scoped>
.executor {
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

/* ---- 布局 ---- */
.executor-layout {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.executor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

/* ---- 卡片 ---- */
.section-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.section-card-header h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
  letter-spacing: var(--tracking-tight);
}

.section-card-actions {
  display: flex;
  gap: var(--space-2);
}

/* ---- 执行器主体 ---- */
.executor-body {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ---- 命令输入区域 ---- */
.executor-input-wrapper {
  position: relative;
}

.history-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 100;
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  max-height: 240px;
  overflow-y: auto;
  margin-top: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--color-neutral-600);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.history-item:hover,
.history-item.active {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
}

.history-item.active {
  font-weight: 600;
}

.executor-options {
  display: flex;
  gap: var(--space-4);
  align-items: center;
  flex-wrap: wrap;
}

.approval-id-input {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.approval-id-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  white-space: nowrap;
}

.executor-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.exec-time {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  font-variant-numeric: tabular-nums;
}

/* ---- 输出 ---- */
.output-body {
  position: relative;
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto;
}

.output-content {
  padding: var(--space-4) var(--space-5);
}

.output-text {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: var(--leading-relaxed);
  color: var(--color-neutral-700);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.output-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8);
  color: var(--color-neutral-300);
}

.output-empty p {
  margin: 0;
  font-size: var(--text-sm);
}

.output-loading {
  position: absolute;
  bottom: var(--space-4);
  left: var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary-500);
  animation: pulse 1.4s infinite ease-in-out;
}

.loading-dot:nth-child(2) { animation-delay: 0.2s; }
.loading-dot:nth-child(3) { animation-delay: 0.4s; }

.loading-text {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-left: var(--space-1);
}

@keyframes pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ---- 侧边栏 ---- */
.executor-sidebar {
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex-shrink: 0;
}

.sidebar-section {
  background: transparent;
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

/* ---- 安全评估 ---- */
.assessment-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.assessment-verdict {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 600;
}

.assessment-verdict.safe { background: var(--color-success-bg); color: var(--color-success); }
.assessment-verdict.blocked { background: var(--color-danger-bg); color: var(--color-danger); }
.assessment-verdict.review { background: var(--color-warning-bg); color: var(--color-warning); }

.assessment-score {
  text-align: center;
  padding: var(--space-2);
}

.assessment-score-label {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-bottom: var(--space-1);
}

.assessment-score-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.assessment-score-value.safe { color: var(--color-success); }
.assessment-score-value.review { color: var(--color-warning); }
.assessment-score-value.blocked { color: var(--color-danger); }

.assessment-layers {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.assessment-layer {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.assessment-layer-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--color-neutral-600);
}

.assessment-layer-header .pass { color: var(--color-success); font-weight: 600; }
.assessment-layer-header .fail { color: var(--color-danger); font-weight: 600; }

.assessment-layer-bar {
  height: 4px;
  background: var(--color-neutral-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.assessment-layer-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: transform var(--duration-slow) var(--ease-out);
  transform-origin: left;
}

.assessment-layer-reason {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.assessment-empty {
  padding: var(--space-4);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-neutral-300);
}

.assessment-empty p {
  margin: 0;
}

/* ---- 常用命令 ---- */
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
  padding: var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-xs);
  color: var(--color-neutral-600);
  transition: all var(--duration-fast) var(--ease-out);
}

.quick-command:hover {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
}

.safety-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-success-bg);
  border: 1px solid var(--color-success);
  border-radius: var(--radius-md);
  color: var(--color-success);
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}

@media (max-width: 900px) {
  .executor-sidebar { display: none; }
}
</style>
