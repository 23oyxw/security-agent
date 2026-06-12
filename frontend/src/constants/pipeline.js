/** 流水线状态与三角色协调常量 — 对齐 MULTI_PERSONA_COORDINATION.md */

export const PIPELINE_PHASES = {
  analyze: { layer: 'L1', label: '分析', lock: 'L1_only' },
  precheck: { layer: 'L2', label: '防护', lock: null },
  execute: { layer: 'L3', label: '执行', lock: 'execute' },
  finalize: { layer: 'L4', label: '审计', lock: null },
  iterate: { layer: 'L5', label: '迭代', lock: null },
}

export const L2_VERDICTS = {
  pass: { label: '通过', type: 'success', canExecute: true },
  confirm: { label: '需确认', type: 'warning', canExecute: true },
  deny: { label: '拒绝', type: 'danger', canExecute: false },
}

export const DATA_ENTITIES = [
  { key: 'plan_id', desc: 'L1 分析产物，执行门禁', store: 'plans.db' },
  { key: 'trace_id', desc: 'L1–L5 全链路溯源', store: 'traces.db' },
  { key: 'batch_id', desc: '批量队列关联', store: 'plan.batch_id' },
  { key: 'session_id', desc: '对话上下文（非审计主键）', store: '前端/brain' },
]

/** 三角色：上下文提示与关联网页 */
export const PERSONAS = {
  user: {
    id: 'user',
    label: '用户',
    icon: 'User',
    routeIds: ['agent'],
    hints: {
      plan: '计划模式：输入指令后点「L1 分析」，审阅三感知卡片再切执行模式。',
      execute: '执行模式：需 L2 通过；高危操作会要求二次确认。',
      batch: '批量每条独立 trace，共享 batch_id，不会跳过 L1。',
      blocked: 'L2 拒绝：请修改指令或联系运维调整护栏策略。',
    },
  },
  ops: {
    id: 'ops',
    label: '运维',
    icon: 'Monitor',
    routeIds: ['dashboard', 'canvas', 'trace', 'alerts', 'workflow'],
    hints: {
      trace: '用 plan.trace_id 在 TraceView 查看 L1→L5 stage 时间线。',
      audit: 'audit.jsonl append-only；GET /api/audit/logs 查尾读。',
      incident: '导出：trace_id + boundary_hits + tools_used。',
      bypass: '生产禁用 POST /api/agent/chat（无 L2 闸门）。',
    },
  },
  dev: {
    id: 'dev',
    label: '开发',
    icon: 'EditPen',
    routeIds: ['agent', 'mcp', 'guide'],
    hints: {
      extend: '新工具注册 cluster_map + registry；L1/L2 禁止调工具。',
      api: '主编排 POST /orchestrate；单步 plan → l2 → execute。',
      persist: 'plans.db 双写内存；重启后 get_plan 可恢复。',
      wiki: 'Wiki reflux API 待建（P1）。',
    },
  },
}

/** 根据 store 快照生成当前角色下的动态提示 */
export function resolvePersonaHint(personaId, ctx = {}) {
  const p = PERSONAS[personaId]
  if (!p) return ''
  const { mode, l2Verdict, hasPlan, isBlocked, batchCount } = ctx
  if (personaId === 'user') {
    if (isBlocked) return p.hints.blocked
    if (batchCount > 0) return p.hints.batch
    if (mode === 'execute') return p.hints.execute
    return p.hints.plan
  }
  if (personaId === 'ops') {
    if (hasPlan && ctx.traceId) return `当前 trace: ${ctx.traceId} — ${p.hints.trace}`
    if (l2Verdict === 'deny') return p.hints.incident
    return p.hints.audit
  }
  if (personaId === 'dev') {
    if (hasPlan) return `plan_id=${ctx.planId} · ${p.hints.api}`
    return p.hints.extend
  }
  return ''
}
