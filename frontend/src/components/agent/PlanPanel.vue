<template>
  <div v-if="plan" class="plan-panel reveal-item is-visible">
    <div class="plan-header">
      <div class="plan-meta">
        <el-tag size="small" type="info">L1 三感知 · analyze</el-tag>
        <code class="plan-id">{{ plan.plan_id }}</code>
        <el-tag size="small" effect="plain">意图: {{ plan.intent }}</el-tag>
        <el-tag v-if="plan.trace_id" size="small" effect="plain">trace: {{ plan.trace_id.slice(0, 8) }}</el-tag>
      </div>
      <el-tag v-if="l2Verdict" size="small" :type="l2TagType" effect="dark">L2 {{ l2Label }}</el-tag>
    </div>

    <p class="triple-intro">并行三感知（零工具 · 零执行 · 零决策）— 对抗边界 · 灵敏检索 · 静态之眼</p>

    <div class="triple-cards">
      <div
        v-for="card in perceptionCards"
        :key="card.id"
        class="triple-card"
        :class="card.id"
      >
        <div class="triple-card-head">
          <el-icon :size="16"><component :is="card.icon" /></el-icon>
          <strong>{{ card.title }}</strong>
        </div>
        <p class="triple-card-desc">{{ card.desc }}</p>
        <p class="triple-card-stat">{{ card.stat }}</p>
      </div>
    </div>

    <div class="plan-steps">
      <div v-for="s in plan.steps" :key="s.id" class="plan-step" :class="s.status">
        <span class="step-layer">{{ s.layer }}</span>
        <span class="step-title">{{ s.title }}</span>
        <el-icon v-if="s.status === 'done'" class="step-icon ok"><CircleCheckFilled /></el-icon>
      </div>
    </div>

    <el-collapse class="plan-collapse" v-model="openPanels">
      <el-collapse-item name="boundary">
        <template #title>
          <span class="collapse-title">① 抗性边界感知</span>
          <el-tag size="small" effect="plain" type="warning">对抗训练 · 权限跃迁阻力</el-tag>
        </template>
        <p v-if="calibrationSummary" class="calibration-line">{{ calibrationSummary }}</p>
        <div v-if="privilegeProbes.length" class="probe-block">
          <span class="probe-label">权限跃迁阻力探针</span>
          <el-tag v-for="p in privilegeProbes" :key="p.probe_id" size="small" type="danger" effect="plain">
            {{ p.label }}
          </el-tag>
        </div>
        <div v-if="!plan.boundary_hits?.length && !privilegeProbes.length" class="empty-hint">
          未检测到越界指令，抗性边界通过
        </div>
        <div v-for="(b, i) in plan.boundary_hits" :key="i" class="hit-row">
          <el-tag size="small" :type="verdictType(b.verdict)">{{ b.verdict }}</el-tag>
          <code>{{ b.input }}</code>
          <span v-if="b.reasons?.length" class="hit-reason">{{ b.reasons[0] }}</span>
        </div>
      </el-collapse-item>

      <el-collapse-item name="knowledge">
        <template #title>
          <span class="collapse-title">② 灵敏知识库检索</span>
          <el-tag v-if="knowledgeSensitivity" size="small" effect="plain" :type="knowledgeSensitivity === 'high' ? 'success' : 'info'">
            灵敏度 {{ knowledgeSensitivity }}
          </el-tag>
        </template>
        <div v-if="!plan.knowledge_refs?.length" class="empty-hint">无命中（可扩充 Gitee Wiki 知识库）</div>
        <div v-for="(k, i) in plan.knowledge_refs" :key="i" class="kb-row">
          <strong>{{ k.title }}</strong>
          <span v-if="k.score != null" class="kb-score">{{ (k.score * 100).toFixed(0) }}%</span>
          <p>{{ k.snippet }}</p>
        </div>
      </el-collapse-item>

      <el-collapse-item name="static">
        <template #title>
          <span class="collapse-title">③ 静态环境感知（眼）</span>
          <el-tag size="small" effect="plain">8 维监听</el-tag>
        </template>
        <div v-if="eyeAxes.length" class="eye-axes">
          <el-tag v-for="ax in eyeAxes" :key="ax" size="small" effect="plain">{{ ax }}</el-tag>
        </div>
        <div v-if="snapshotSummary" class="static-grid">
          <div v-for="(v, key) in snapshotSummary" :key="key" class="static-cell">
            <span class="static-key">{{ key }}</span>
            <span class="static-val">{{ v }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">静态感知快照加载中或不可用</div>
      </el-collapse-item>
    </el-collapse>

    <div v-if="plan.tool_chain?.length" class="tool-chain">
      <span class="chain-label">L3 预计工具簇：</span>
      <el-tag v-for="t in plan.tool_chain" :key="t" size="small" effect="plain">{{ t }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { L1_TRIPLE_PERCEPTION } from '../../constants/agents'

const props = defineProps({
  plan: { type: Object, default: null },
  l2Verdict: { type: String, default: null },
})

const openPanels = ref(['boundary', 'knowledge', 'static'])

const tp = computed(() => props.plan?.triple_perception || {})
const boundaryBlock = computed(() => tp.value.adversarial_boundary || {})
const knowledgeBlock = computed(() => tp.value.sensitive_knowledge || {})
const staticBlock = computed(() => tp.value.static_environment_eye || {})

const privilegeProbes = computed(() => boundaryBlock.value.privilege_escalation_probes || [])
const knowledgeSensitivity = computed(() => knowledgeBlock.value.sensitivity)
const eyeAxes = computed(() => staticBlock.value.eye_axes || [])

const calibrationSummary = computed(() => {
  const cal = boundaryBlock.value.adversarial_calibration
  if (!cal || cal.error) return null
  return `对抗矩阵校准 ${cal.passed}/${cal.total}（${cal.pass_rate}%）· ${cal.resistance_training || '权限跃迁阻力'}`
})

const perceptionCards = computed(() => {
  const hits = props.plan?.boundary_hits?.length || 0
  const probes = privilegeProbes.value.length
  const refs = props.plan?.knowledge_refs?.length || 0
  const dims = Object.keys(staticBlock.value.dimensions || {}).length
  return L1_TRIPLE_PERCEPTION.map(m => {
    let stat = '已完成'
    if (m.id === 'adversarial_boundary') stat = `边界 ${hits} 条 · 跃迁探针 ${probes}`
    if (m.id === 'sensitive_knowledge') stat = `命中 ${refs} 条 · ${knowledgeSensitivity.value || '—'}`
    if (m.id === 'static_environment_eye') stat = `维度 ${dims || eyeAxes.value.length} · 只读`
    return { ...m, stat }
  })
})

const l2TagType = computed(() => {
  const v = props.l2Verdict
  if (v === 'pass') return 'success'
  if (v === 'deny') return 'danger'
  if (v === 'confirm') return 'warning'
  return 'info'
})

const l2Label = computed(() => {
  const map = { pass: '通过', deny: '拒绝', confirm: '需确认' }
  return map[props.l2Verdict] || props.l2Verdict
})

const snapshotSummary = computed(() => {
  const dims = staticBlock.value.dimensions
  if (dims && Object.keys(dims).length) {
    const out = {}
    if (dims.cpu != null) out['CPU'] = `${dims.cpu}%`
    if (dims.memory != null) out['内存'] = `${dims.memory}%`
    if (dims.disk != null) out['磁盘'] = `${dims.disk}%`
    if (dims.processes != null) out['进程'] = dims.processes
    if (dims.ports != null) out['端口'] = dims.ports
    if (dims.network != null) out['网络'] = dims.network
    if (dims.health != null) out['状态'] = dims.health ? '正常' : '异常'
    return Object.keys(out).length ? out : null
  }
  const snap = props.plan?.static_snapshot
  if (!snap || typeof snap !== 'object') return null
  const s = snap.summary || snap
  const out = {}
  if (s.cpu_percent != null) out['CPU'] = `${s.cpu_percent}%`
  if (s.memory_percent != null) out['内存'] = `${s.memory_percent}%`
  if (s.disk_percent != null) out['磁盘'] = `${s.disk_percent}%`
  return Object.keys(out).length ? out : null
})

function verdictType(v) {
  if (v === 'ALLOW') return 'success'
  if (v === 'NEED_CONFIRM') return 'warning'
  return 'danger'
}
</script>

<style scoped>
.plan-panel {
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--glass-border, var(--color-neutral-200));
  border-radius: var(--radius-lg);
  background: var(--glass-surface, #fff);
  box-shadow: var(--shadow-sm);
}

.triple-intro {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  margin: 0 0 var(--space-3);
}

.triple-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

@media (max-width: 768px) {
  .triple-cards { grid-template-columns: 1fr; }
}

.triple-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-neutral-200);
  background: var(--glass-chip, #f8fafc);
}

.triple-card.adversarial_boundary { border-color: var(--color-warning); }
.triple-card.sensitive_knowledge { border-color: var(--color-primary-300); }
.triple-card.static_environment_eye { border-color: var(--color-success); }

.triple-card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}

.triple-card-head strong { font-size: var(--text-xs); }
.triple-card-desc { font-size: 10px; color: var(--color-neutral-400); margin: 0 0 4px; line-height: 1.35; }
.triple-card-stat { font-size: 10px; font-weight: 600; color: var(--color-neutral-600); margin: 0; }

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.plan-meta { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.plan-id { font-size: 10px; color: var(--color-text-muted); }

.plan-steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.plan-step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  background: var(--color-neutral-100);
  border: 1px solid var(--color-neutral-200);
}

.plan-step.done { border-color: var(--color-success); background: var(--color-success-bg); }

.step-layer { font-weight: 700; color: var(--page-accent, var(--color-primary-600)); }
.step-icon.ok { color: var(--color-success); }

.collapse-title { margin-right: var(--space-2); font-weight: 600; font-size: var(--text-sm); }

.calibration-line, .probe-block { margin-bottom: var(--space-2); font-size: var(--text-xs); }
.probe-label { display: block; color: var(--color-neutral-400); margin-bottom: 4px; }

.hit-row, .kb-row {
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-neutral-100);
  font-size: var(--text-xs);
}

.kb-score { margin-left: 8px; font-size: 10px; color: var(--color-primary-500); }
.eye-axes { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: var(--space-2); }

.static-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: var(--space-2);
}

.static-cell {
  padding: var(--space-2);
  background: var(--color-neutral-50);
  border-radius: var(--radius-md);
  text-align: center;
}

.static-key { display: block; font-size: 10px; color: var(--color-text-muted); }
.static-val { font-weight: 700; font-size: var(--text-sm); }

.tool-chain {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  align-items: center;
  font-size: var(--text-xs);
  margin-top: var(--space-2);
}

.chain-label { color: var(--color-text-muted); margin-right: var(--space-1); }
.empty-hint { font-size: var(--text-xs); color: var(--color-text-muted); padding: var(--space-2) 0; }
</style>
