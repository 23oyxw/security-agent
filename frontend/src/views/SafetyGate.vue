<template>
  <div class="safety-page">
    <div class="page-header">
      <h1 class="page-title">安全执行</h1>
      <p class="page-subtitle">命令输入 → 三层防御评估 → 沙箱执行 → 结果输出 (一个流程，一页完成)</p>
    </div>

    <el-row :gutter="16">
      <!-- 左侧: 输入 + 评估 -->
      <el-col :span="12">
        <el-card header="① 命令输入与评估" class="section-card">
          <el-form :model="form" label-width="90px" size="small">
            <el-form-item label="快捷任务">
              <div style="display:flex;flex-wrap:wrap;gap:4px">
                <el-button size="small" v-for="t in quickTasks" :key="t.name" @click="form.target=t.cmd; form.user_message=t.label" :type="t.type" plain>{{ t.label }}</el-button>
              </div>
            </el-form-item>
            <el-form-item label="运维意图">
              <el-input v-model="form.user_message" placeholder="你要做什么？（例: 查看端口监听状态）" />
            </el-form-item>
            <el-form-item label="命令">
              <el-input v-model="form.target" placeholder="输入或用快捷任务填充" @keydown.enter="evaluate" />
            </el-form-item>
            <el-form-item label="沙箱模式">
              <el-switch v-model="form.sandbox" active-text="隔离执行" />
              <span style="font-size:11px;color:#999;margin-left:8px">写操作自动进沙箱，只读命令正常执行</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="evaluate" :loading="evaluating" icon="Search">评估风险</el-button>
              <el-button @click="clearAll">清空</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 评估结果 -->
        <el-card v-if="result" header="② 三层防御评估结果" class="section-card" style="margin-top:12px">
          <div class="verdict-banner" :class="verdictClass">
            <span class="verdict-icon">{{ verdictIcon }}</span>
            <span class="verdict-text">{{ verdictLabel }}</span>
            <span class="verdict-score">评分: {{ result.score || 0 }} / 100</span>
          </div>
          <div v-if="result.message" class="verdict-msg">{{ result.message }}</div>
          <div v-for="(l,i) in (result.layers||[])" :key="i" class="layer-bar">
            <span class="layer-name">{{ l.name || 'L'+(i+1) }}</span>
            <el-progress :percentage="l.score||0" :color="l.ok ? '#67C23A' : '#F56C6C'" :stroke-width="8" :show-text="true" style="flex:1;margin:0 8px" />
            <span style="font-size:10px;color:#999">{{ l.verdict || l.status }}</span>
          </div>
          <div v-if="result.suggestions?.length" class="suggestions">
            <div v-for="(s,i) in result.suggestions" :key="i" class="sug-item">→ {{ s }}</div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧: 执行结果 -->
      <el-col :span="12">
        <el-card header="③ 执行结果" class="section-card">
          <!-- 执行按钮 -->
          <div v-if="canExecute && !executing" style="text-align:center;padding:40px 0">
            <el-button type="success" size="large" @click="execute" icon="CaretRight">
              执行: {{ form.target?.slice(0, 40) }}
            </el-button>
            <div v-if="form.sandbox" style="font-size:11px;color:#999;margin-top:8px">沙箱隔离模式</div>
          </div>

          <!-- 执行中 -->
          <div v-if="executing" style="text-align:center;padding:30px 0">
            <el-icon :size="32" class="is-loading" color="#409EFF"><Loading /></el-icon>
            <div style="margin-top:8px;color:#999">执行中... {{ form.target?.slice(0, 30) }}</div>
          </div>

          <!-- 执行结果 -->
          <div v-if="execResult">
            <el-alert v-if="execResult.auto_rollback_triggered" title="⏪ 自动回滚已触发" type="warning" :closable="false" show-icon style="margin-bottom:8px">
              命令失败且风险等级IRREVERSIBLE — 已自动恢复快照
            </el-alert>
            <el-alert v-else :title="execResult.success ? '执行完成' : '执行失败'" :type="execResult.success ? 'success' : 'error'" :closable="false" show-icon style="margin-bottom:8px" />
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="退出码">{{ execResult.exit_code ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="耗时">{{ execResult.duration_ms ? (execResult.duration_ms/1000).toFixed(2)+'s' : '—' }}</el-descriptions-item>
              <el-descriptions-item label="执行模式">{{ execResult.execution_mode || '—' }}</el-descriptions-item>
              <el-descriptions-item label="风险等级">
                <el-tag :type="execResult.risk_level==='CRITICAL'?'danger':execResult.risk_level==='IRREVERSIBLE'?'warning':'info'" size="small">{{ execResult.risk_label || execResult.risk_level || '—' }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item v-if="execResult.snapshot_id" label="快照 ID">{{ execResult.snapshot_id }}</el-descriptions-item>
              <el-descriptions-item v-if="execResult.rollback_id" label="回滚 ID">{{ execResult.rollback_id }}</el-descriptions-item>
            </el-descriptions>
            <div v-if="execResult.output" style="margin-top:8px;background:#1e293b;color:#e2e8f0;padding:12px;border-radius:6px;max-height:300px;overflow:auto">
              <pre style="margin:0;font-size:12px;white-space:pre-wrap">{{ execResult.output }}</pre>
            </div>
            <div v-if="execResult.error" style="margin-top:4px;color:#F56C6C;font-size:12px">{{ execResult.error }}</div>
          </div>

          <!-- 被拦截 -->
          <div v-if="verdictClass === 'blocked'" style="text-align:center;padding:40px 0;color:#999">
            <el-icon :size="48" color="#F56C6C"><CircleCloseFilled /></el-icon>
            <div style="margin-top:12px">🚫 三层防御已拦截此命令，不会执行</div>
            <div style="font-size:12px;color:#999;margin-top:4px">{{ result?.message }}</div>
          </div>

          <!-- 未评估 -->
          <div v-if="!result && !executing && !execResult" style="text-align:center;padding:40px 0;color:#999">
            先输入命令并点击「评估风险」，通过后在此执行
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()

const form = reactive({ target: '', user_message: '', sandbox: true })
const evaluating = ref(false)
const executing = ref(false)
const result = ref(null)
const execResult = ref(null)

const quickTasks = [
  { name:'port', label:'🔍 查看端口', cmd:'ss -tulnp', type:'primary' },
  { name:'log', label:'📋 系统日志', cmd:'journalctl -n 20 --no-pager', type:'info' },
  { name:'ps', label:'📊 进程列表', cmd:'ps aux --sort=-%cpu | head -20', type:'' },
  { name:'disk', label:'💾 磁盘使用', cmd:'df -h', type:'success' },
  { name:'mem', label:'🧠 内存状态', cmd:'free -h', type:'warning' },
  { name:'net', label:'🌐 网络连接', cmd:'ss -tan', type:'info' },
  { name:'suid', label:'⚠️ SUID排查', cmd:'find / -perm -4000 -type f 2>/dev/null | head -20', type:'danger' },
  { name:'cron', label:'🕐 定时任务', cmd:'crontab -l 2>/dev/null; ls -la /etc/cron*', type:'' },
]

const canExecute = computed(() => {
  if (!result.value) return false
  const v = result.value.verdict
  return v === 'allow' || v === 'confirm'
})

const verdictClass = computed(() => {
  if (!result.value) return ''
  const v = result.value.verdict
  return v === 'allow' ? 'allow' : v === 'deny' ? 'deny' : v === 'confirm' ? 'confirm' : ''
})

const verdictIcon = computed(() => {
  const map = { allow: '✅', deny: '🚫', confirm: '⚠️' }
  return map[result.value?.verdict] || '—'
})

const verdictLabel = computed(() => {
  const map = { allow: '安全 · 通过', deny: '已拦截 · 拒绝', confirm: '需用户确认' }
  return map[result.value?.verdict] || result.value?.verdict || '—'
})

async function evaluate() {
  if (!form.target.trim()) { ElMessage.warning('请输入命令'); return }
  evaluating.value = true
  result.value = null
  execResult.value = null
  try {
    const res = await api.post('/safety/defense/evaluate', {
      target: form.target,
      target_type: 'terminal',
      user_message: form.user_message || form.target,
      sudo: false,
    })
    result.value = {
      verdict: res.overall_verdict || res.verdict || 'unknown',
      score: res.overall_score || res.score || 0,
      layers: res.layers || [],
      message: res.message || '',
      suggestions: res.suggestions || [],
    }
  } catch (e) {
    ElMessage.error('评估失败: ' + (e.response?.data?.detail || e.message))
  } finally { evaluating.value = false }
}

async function execute() {
  executing.value = true
  execResult.value = null
  try {
    const res = await api.post('/executor/execute', {
      command: form.target,
      confirm: result.value?.verdict === 'confirm',
      sandbox: form.sandbox,
      timeout: 30,
    })
    execResult.value = res
    if (res.success) ElMessage.success('执行完成')
    else ElMessage.warning('执行失败: ' + (res.error || ''))
  } catch (e) {
    execResult.value = { success: false, error: e.response?.data?.detail || e.message }
  } finally { executing.value = false }
}

// Agent 跳转时自动填充命令
onMounted(() => {
  const cmd = route.query.cmd
  const intent = route.query.intent
  if (cmd) {
    form.target = cmd
    form.user_message = intent || ''
    evaluate()
  }
})

function clearAll() {
  form.target = ''
  form.user_message = ''
  result.value = null
  execResult.value = null
}
</script>

<style scoped>
.safety-page { max-width: var(--content-max-width,1200px); margin: 0 auto; }
.page-header { margin-bottom: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 700; margin: 0; }
.page-subtitle { font-size: var(--text-sm); color: var(--color-neutral-400); margin: 4px 0 0; }
.section-card { background: transparent; border: 1px solid var(--page-card-border, var(--color-neutral-200)); border-radius: var(--radius-lg); margin-bottom: 12px; }

/* 三步流程连接线 */
.safety-page :deep(.el-row) {
  position: relative;
}
.safety-page :deep(.el-col:first-child) .section-card::after {
  content: '';
  position: absolute;
  right: -16px;
  top: 50%;
  width: 12px;
  height: 2px;
  background: var(--color-neutral-300);
}

.verdict-banner {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  border-radius: var(--radius-md); margin-bottom: 8px; font-weight: 600;
  animation: slide-down var(--duration-normal) var(--ease-out) both,
             scale-in var(--duration-normal) var(--ease-spring) both;
}
.verdict-banner.allow { background: #f0fdf4; border: 1px solid #86efac; color: #166534; }
.verdict-banner.deny {
  background: #fef2f2; border: 1px solid #fca5a5; color: #991b1b;
  animation: border-pulse 2s ease-in-out infinite;
}
.verdict-banner.confirm { background: #fffbeb; border: 1px solid #fcd34d; color: #92400e; }
.verdict-icon { font-size: 24px; }
.verdict-text { font-size: 16px; flex: 1; }
.verdict-score { font-size: 14px; opacity: .7; }
.verdict-msg { font-size: 12px; color: var(--color-neutral-500); margin-bottom: 8px; }

.layer-bar {
  display: flex; align-items: center; padding: 4px 0;
  animation: slide-right var(--duration-normal) var(--ease-out) both;
}
.layer-bar:nth-child(2) { animation-delay: 80ms; }
.layer-bar:nth-child(3) { animation-delay: 160ms; }
.layer-name { font-size: 11px; font-weight: 600; color: var(--color-neutral-600); min-width: 30px; }

.suggestions { margin-top: 8px; animation: fade-in var(--duration-slow) var(--ease-out) 300ms both; }
.sug-item { font-size: 12px; color: var(--color-neutral-500); padding: 2px 0; }

/* 执行按钮增强 */
.safety-page :deep(.el-button--success) {
  transition: all var(--duration-normal) var(--ease-out);
}
.safety-page :deep(.el-button--success):hover {
  box-shadow: var(--shadow-glow-success);
  transform: translateY(-2px);
}

.is-loading { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }

/* 沙箱开关过渡 */
.safety-page :deep(.el-switch) {
  transition: all var(--duration-normal) var(--ease-out);
}

/* 执行结果代码块 */
.safety-page pre {
  position: relative;
}
.safety-page pre::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: linear-gradient(transparent, rgba(30, 41, 59, 0.8));
  pointer-events: none;
  border-radius: 0 0 6px 6px;
}

@keyframes border-pulse {
  0%, 100% { border-color: #fca5a5; }
  50% { border-color: #ef4444; }
}
</style>
