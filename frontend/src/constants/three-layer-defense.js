/**
 * 三层安全防御 — 与 security_agent/safety_gate/three_layer_defense.py 对齐
 */

export const DEFENSE_FORMULA = '静态 30% + 意图 35% + 受限执行 35%'

export const DEFENSE_LAYERS = [
  {
    id: 'static_risk',
    name: '第1层 · 静态风险评估',
    short: '静态规则',
    weightPct: 30,
    color: '#3b82f6',
    desc: '规则引擎 + 注入扫描 · 高危命令四级判定',
    backend: 'security_agent/safety_gate/risk.py',
  },
  {
    id: 'dynamic_intent',
    name: '第2层 · 动态意图审计',
    short: '意图一致',
    weightPct: 35,
    color: '#10b981',
    desc: '用户运维意图 vs 拟执行命令交叉校验',
    backend: 'security_agent/safety_gate/intent.py',
  },
  {
    id: 'restricted_exec',
    name: '第3层 · 受限执行环境',
    short: '沙箱/权限',
    weightPct: 35,
    color: '#f59e0b',
    desc: '最小权限 · 沙箱隔离 · 备份回滚 · 本机执行可行性',
    backend: 'security_agent/terminal/sandbox.py',
  },
]

const LAYER_BY_ID = Object.fromEntries(DEFENSE_LAYERS.map(l => [l.id, l]))

export function normalizeDefenseLayer(raw, index = 0) {
  const id = raw?.layer || DEFENSE_LAYERS[index]?.id || ''
  const meta = LAYER_BY_ID[id] || {}
  return {
    id,
    name: raw?.name_zh || raw?.name || meta.name || `第${index + 1}层`,
    short: raw?.short_zh || meta.short || '',
    weightPct: raw?.weight_pct ?? meta.weightPct ?? Math.round((raw?.weight || 0) * 100),
    color: meta.color || '#64748b',
    desc: raw?.desc || meta.desc || '',
    score: raw?.score ?? 0,
    passed: raw?.passed ?? raw?.verdict === 'pass',
    verdict: raw?.verdict || raw?.status || '-',
    detail: raw?.detail || '',
    durationMs: raw?.duration_ms,
  }
}

export function verdictLabel(verdict) {
  const v = String(verdict || '').toLowerCase()
  const map = {
    allow: '安全 · 通过',
    pass: '通过',
    confirm: '需用户确认',
    deny: '已拦截',
    block: '阻断',
    warn: '需关注',
    quarantine: '沙箱隔离',
    approve: '需人工审批',
    escalate: '升级处理',
  }
  return map[v] || verdict || '-'
}

export function verdictTagType(verdict) {
  const v = String(verdict || '').toLowerCase()
  if (v === 'allow' || v === 'pass') return 'success'
  if (v === 'deny' || v === 'block') return 'danger'
  if (v === 'confirm' || v === 'warn' || v === 'quarantine') return 'warning'
  return 'info'
}

export function layerVerdictTag(verdict) {
  const v = String(verdict || '').toLowerCase()
  if (v === 'pass') return 'success'
  if (v === 'block') return 'danger'
  if (v === 'warn') return 'warning'
  return 'info'
}
