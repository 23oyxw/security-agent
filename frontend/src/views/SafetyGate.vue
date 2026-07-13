<template>
  <div class="safety-page">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
      :agent="pageMeta.agent"
    >
      <template #actions>
        <PipelineBtn action="goAgent" size="small" @click="router.push('/agent')" />
      </template>
    </PageHeader>

    <el-alert
      v-if="linkedPlan"
      type="info"
      :closable="false"
      show-icon
      class="plan-link-banner"
      :title="`已关联 L1 计划 · ${linkedPlan.plan_id?.slice(0, 8)}`"
    >
      <template #default>
        <span>{{ linkedPlan.message }}</span>
        <span v-if="agentL2Label" class="plan-l2-tag"> · 流水线 L2：{{ agentL2Label }}</span>
      </template>
    </el-alert>

    <!-- 三层防御说明 -->
    <el-card class="section-card defense-intro" shadow="never">
      <div class="defense-intro-head">
        <strong>三层安全防御</strong>
        <span class="defense-formula">{{ DEFENSE_FORMULA }}</span>
      </div>
      <div class="defense-layer-grid">
        <div v-for="l in DEFENSE_LAYERS" :key="l.id" class="defense-layer-chip" :style="{ '--dl-color': l.color }">
          <span class="dl-weight">{{ l.weightPct }}%</span>
          <span class="dl-name">{{ l.name }}</span>
          <span class="dl-desc">{{ l.desc }}</span>
        </div>
      </div>
      <p class="defense-note">
        <strong>评估通过 ≠ 执行成功</strong>：前两层判「能不能做」，第3层还检查沙箱/权限与本机平台；
        右侧执行区展示真实退出码与 stderr。
      </p>
    </el-card>

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
            <span class="verdict-text">{{ verdictLabelText }}</span>
            <span class="verdict-score">评分: {{ result.score || 0 }} / 100</span>
          </div>
          <div v-if="result.message" class="verdict-msg">{{ result.message }}</div>
          <el-alert
            v-if="result.execution_feasibility && !result.execution_feasibility.ok"
            type="warning"
            :closable="false"
            show-icon
            class="feasibility-alert"
            :title="'第3层平台提示：本机可能无法执行'"
            :description="(result.execution_feasibility.reason || '') + (result.execution_feasibility.hint ? ' — ' + result.execution_feasibility.hint : '')"
          />
          <div v-if="normalizedLayers.length" ref="defenseChartRef" class="chart-box chart-box--defense" />
          <div v-for="l in normalizedLayers" :key="l.id" class="layer-card" :style="{ '--dl-color': l.color }">
            <div class="layer-card-head">
              <span class="layer-name">{{ l.name }}</span>
              <el-tag size="small" :type="layerVerdictTag(l.verdict)" effect="plain">{{ l.verdict }}</el-tag>
              <span class="layer-weight">{{ l.weightPct }}%</span>
            </div>
            <el-progress :percentage="l.score||0" :color="l.color" :stroke-width="8" :show-text="true" />
            <p v-if="l.detail" class="layer-detail">{{ l.detail }}</p>
          </div>
          <div v-if="result.decision_path?.length" class="decision-path">
            <span class="path-label">决策路径</span>
            <code v-for="(p,i) in result.decision_path" :key="i" class="path-item">{{ p }}</code>
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
            <el-alert
              v-if="evalExecGap"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom:8px"
              title="评估与执行不一致"
              :description="evalExecGap"
            />
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
          <div v-if="verdictClass === 'deny'" style="text-align:center;padding:40px 0;color:#999">
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
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { NAV_PAGES } from '../constants/navigation'
import {
  DEFENSE_FORMULA,
  DEFENSE_LAYERS,
  normalizeDefenseLayer,
  verdictLabel as formatVerdictLabel,
  layerVerdictTag,
} from '../constants/three-layer-defense'
import { initChart, scheduleChartResize } from '../composables/useEcharts'
import { buildDefenseLayersChartOption } from '../utils/chartTheme'
import { useAgentStore } from '../stores/agent'

const pageMeta = NAV_PAGES.safety
const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()

const form = reactive({ target: '', user_message: '', sandbox: true })
const evaluating = ref(false)
const executing = ref(false)
const result = ref(null)
const execResult = ref(null)
const defenseChartRef = ref(null)
let defenseChart = null

const isWin = typeof navigator !== 'undefined' && /Win/i.test(navigator.platform)

const linkedPlan = computed(() => {
  const qid = route.query.plan_id
  const plan = agentStore.currentPlan
  if (!plan) return null
  if (qid && plan.plan_id !== qid) return null
  return plan
})

const agentL2Label = computed(() => {
  const v = agentStore.l2Result?.verdict || linkedPlan.value?.l2_verdict
  if (!v) return ''
  if (v === 'pass') return '通过'
  if (v === 'deny') return '拒绝'
  if (v === 'confirm') return '需确认'
  return v
})

const quickTasks = [
  ...(isWin ? [
    { name:'win-port', label:'🔍 查看端口(Win)', cmd:'netstat -ano', type:'primary' },
    { name:'win-ps', label:'📊 进程(Win)', cmd:'tasklist', type:'' },
    { name:'win-disk', label:'💾 磁盘(Win)', cmd:'wmic logicaldisk get size,freespace,caption', type:'success' },
  ] : []),
  { name:'port', label:'🔍 查看端口', cmd:'ss -tulnp', type:'primary' },
  { name:'log', label:'📋 系统日志', cmd:'journalctl -n 20 --no-pager', type:'info' },
  { name:'ps', label:'📊 进程列表', cmd:'ps aux --sort=-%cpu | head -20', type:'' },
  { name:'disk', label:'💾 磁盘使用', cmd:'df -h', type:'success' },
  { name:'mem', label:'🧠 内存状态', cmd:'free -h', type:'warning' },
  { name:'net', label:'🌐 网络连接', cmd:'ss -tan', type:'info' },
  { name:'suid', label:'⚠️ SUID排查', cmd:'find / -perm -4000 -type f 2>/dev/null | head -20', type:'danger' },
  { name:'cron', label:'🕐 定时任务', cmd:'crontab -l 2>/dev/null; ls -la /etc/cron*', type:'' },
]

const normalizedLayers = computed(() =>
  (result.value?.layers || []).map((l, i) => normalizeDefenseLayer(l, i))
)

const verdictLabelText = computed(() => formatVerdictLabel(result.value?.verdict))

const evalExecGap = computed(() => {
  if (!result.value || !execResult.value || execResult.value.success) return ''
  const v = String(result.value.verdict || '').toLowerCase()
  if (v !== 'allow' && v !== 'confirm') return ''
  const err = execResult.value.error || '未知错误'
  const hint = result.value.execution_feasibility?.hint
  return hint ? `${err}。${hint}` : `${err}（安全评估已通过，失败来自执行环境/命令本身）`
})

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

async function renderDefenseChart() {
  await nextTick()
  if (!defenseChartRef.value || !normalizedLayers.value.length) return
  if (!defenseChart) defenseChart = await initChart(defenseChartRef.value)
  if (!defenseChart) return
  defenseChart.setOption(buildDefenseLayersChartOption(normalizedLayers.value), true)
  scheduleChartResize(defenseChart)
}

async function evaluate() {
  if (!form.target.trim()) { ElMessage.warning('请输入命令'); return }
  evaluating.value = true
  result.value = null
  execResult.value = null
  defenseChart?.dispose()
  defenseChart = null
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
      message: res.message || res.eval_note || '',
      suggestions: res.suggestions || [],
      decision_path: res.decision_path || [],
      execution_feasibility: res.execution_feasibility || null,
      requires_sandbox: res.requires_sandbox,
      trace_id: res.trace_id,
    }
    await renderDefenseChart()
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

// Agent / 路由上下文自动填充
function initFromContext() {
  const plan = agentStore.currentPlan
  const cmd = route.query.cmd || plan?.message || plan?.user_message_resolved
  const intent = route.query.intent || plan?.message || ''
  if (!cmd) return
  form.target = String(cmd)
  form.user_message = String(intent || cmd)
  if (route.query.autoeval !== '0') evaluate()
}

onMounted(() => {
  initFromContext()
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

.defense-intro { margin-bottom: 12px; }
.defense-intro-head { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.defense-formula { font-size: 12px; color: var(--color-neutral-500); background: var(--color-neutral-100); padding: 2px 8px; border-radius: 4px; }
.defense-layer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; }
.defense-layer-chip { border-left: 3px solid var(--dl-color); padding: 8px 10px; background: #fff; border-radius: 6px; border: 1px solid var(--color-neutral-200); border-left-width: 3px; border-left-color: var(--dl-color); }
.dl-weight { font-size: 11px; font-weight: 700; color: var(--dl-color); margin-right: 6px; }
.dl-name { font-size: 12px; font-weight: 600; display: block; margin: 2px 0; }
.dl-desc { font-size: 11px; color: var(--color-neutral-500); line-height: 1.4; }
.defense-note { margin: 10px 0 0; font-size: 12px; color: var(--color-neutral-600); line-height: 1.5; }

.chart-box--defense { min-height: 140px; margin: 8px 0 12px; }
.layer-card { margin-bottom: 10px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--color-neutral-200); border-left: 3px solid var(--dl-color); background: #fff; }
.layer-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.layer-card .layer-name { font-size: 12px; font-weight: 600; flex: 1; }
.layer-weight { font-size: 10px; color: var(--color-neutral-400); }
.layer-detail { margin: 6px 0 0; font-size: 11px; color: var(--color-neutral-500); line-height: 1.45; }
.decision-path { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.path-label { font-size: 11px; color: var(--color-neutral-400); margin-right: 4px; }
.path-item { font-size: 10px; background: var(--color-neutral-100); padding: 2px 6px; border-radius: 4px; }
.feasibility-alert { margin-bottom: 8px; }

.plan-link-banner { margin-bottom: 12px; }
.plan-l2-tag { color: var(--color-neutral-500); font-size: 12px; }

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
