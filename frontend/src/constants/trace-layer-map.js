/**
 * Trace 阶段/工具 → 五层映射 · 中英文状态标签
 * 供 TraceView / L5 溯源共用
 */

import { CANVAS_LAYER_META } from './canvas-topology'

export const TRACE_LAYER_ORDER = ['L1', 'L2', 'GATE', 'L3', 'L4', 'L5']

export const TRACE_STATUS = {
  success: { cn: '成功', en: 'OK', type: 'success' },
  ok: { cn: '成功', en: 'OK', type: 'success' },
  pass: { cn: '通过', en: 'Pass', type: 'success' },
  confirm: { cn: '需确认', en: 'Confirm', type: 'warning' },
  deny: { cn: '拒绝', en: 'Deny', type: 'danger' },
  failed: { cn: '失败', en: 'Failed', type: 'danger' },
  error: { cn: '错误', en: 'Error', type: 'danger' },
  running: { cn: '进行中', en: 'Running', type: 'info' },
  idle: { cn: '等待', en: 'Idle', type: 'info' },
}

const LAYER_RULES = [
  { layer: 'L1', patterns: [/l1/i, /analyze/i, /plan/i, /perception/i, /boundary/i, /knowledge/i, /static/i, /triple/i, /intent_detect/i] },
  { layer: 'L2', patterns: [/l2/i, /safety/i, /precheck/i, /sandbox/i, /guard/i, /verdict/i, /defense/i] },
  { layer: 'GATE', patterns: [/gate/i, /层间/i, /mode.?switch/i] },
  { layer: 'L3', patterns: [/l3/i, /execute/i, /dispatch/i, /mcp/i, /tool/i, /skill/i, /flow/i, /repair/i, /metric/i, /log/i, /schedule/i, /executor/i] },
  { layer: 'L4', patterns: [/l4/i, /audit/i, /finalize/i, /wiki/i, /reflux/i, /卷宗/i, /jsonl/i] },
  { layer: 'L5', patterns: [/l5/i, /analytics/i, /scatter/i, /heatmap/i, /eval/i, /迭代/i, /quant/i] },
]

const TOOL_CLUSTER_RULES = [
  { cluster: 'metrics', cn: '指标采集', en: 'Metrics', patterns: [/metric/i, /health/i, /cpu/i, /memory/i, /disk/i] },
  { cluster: 'logs', cn: '日志处理', en: 'Logs', patterns: [/log/i, /journal/i, /syslog/i] },
  { cluster: 'repair', cn: '故障修复', en: 'Repair', patterns: [/repair/i, /fix/i, /rollback/i, /restore/i] },
  { cluster: 'dispatch', cn: '资源调度', en: 'Dispatch', patterns: [/dispatch/i, /sched/i, /quota/i, /autonomous/i, /monitor/i] },
  { cluster: 'flow', cn: '封装流程', en: 'Skill Flow', patterns: [/skill_flow/i, /flow/i] },
  { cluster: 'mcp', cn: 'MCP 工具', en: 'MCP Tool', patterns: [/mcp/i] },
]

export function resolveTraceLayer(name = '', data = {}) {
  const hay = `${name} ${JSON.stringify(data || {}).slice(0, 200)}`
  for (const r of LAYER_RULES) {
    if (r.patterns.some(p => p.test(hay))) return r.layer
  }
  return 'L3'
}

export function resolveToolCluster(name = '', data = {}) {
  const hay = `${name} ${data?.tool || data?.tool_name || ''}`
  for (const c of TOOL_CLUSTER_RULES) {
    if (c.patterns.some(p => p.test(hay))) return c
  }
  return null
}

export function formatTraceStatus(status) {
  const key = String(status || 'success').toLowerCase()
  return TRACE_STATUS[key] || { cn: status || '完成', en: status || 'Done', type: 'info' }
}

export function layerDisplay(layer) {
  const meta = CANVAS_LAYER_META[layer] || CANVAS_LAYER_META.L3
  const en = {
    L1: 'Analyze', L2: 'Safety', GATE: 'Gate', L3: 'Execute', L4: 'Audit', L5: 'Analytics',
  }[layer] || layer
  return {
    layer,
    cn: meta.label,
    en,
    accent: meta.accent,
    agent: meta.agent,
  }
}

/**  enrich raw trace stage / viz node */
export function enrichTraceNode(raw, index = 0) {
  const name = raw.name || raw.stage || raw.node_id || `Step ${index + 1}`
  const data = raw.details || raw.data || {}
  const layer = raw.layer || data.layer || resolveTraceLayer(name, data)
  const toolCluster = data.cluster
    ? TOOL_CLUSTER_RULES.find(c => c.cluster === data.cluster) || { cluster: data.cluster, cn: data.cluster, en: data.cluster }
    : resolveToolCluster(name, data)
  const toolName = raw.tool || data.tool || data.tool_name || (toolCluster ? toolCluster.en : '')
  const st = formatTraceStatus(raw.status || (raw.error ? 'failed' : 'success'))
  const ld = layerDisplay(layer)

  return {
    ...raw,
    node_id: raw.node_id || `node-${index}`,
    name,
    layer,
    layerCn: ld.cn,
    layerEn: ld.en,
    layerAccent: ld.accent,
    agent: ld.agent,
    isTool: Boolean(toolName || toolCluster),
    toolCluster: toolCluster?.cluster || null,
    toolName,
    toolLabel: toolCluster ? `${toolCluster.cn} · ${toolCluster.en}` : (toolName || ''),
    statusCn: st.cn,
    statusEn: st.en,
    statusType: st.type,
    displayTitle: toolName ? `${toolName}` : name,
    displaySub: toolCluster
      ? `${layer} · ${toolCluster.cn} (${toolCluster.en})`
      : `${layer} · ${ld.cn.split(' ')[0]} (${ld.en})`,
  }
}

export function enrichTraceNodes(nodes) {
  return (nodes || []).map((n, i) => enrichTraceNode(n, i))
}

export function groupTraceNodesByLayer(nodes) {
  const enriched = enrichTraceNodes(nodes)
  const groups = TRACE_LAYER_ORDER.map(layer => ({
    ...layerDisplay(layer),
    nodes: enriched.filter(n => n.layer === layer),
  })).filter(g => g.nodes.length)

  const other = enriched.filter(n => !TRACE_LAYER_ORDER.includes(n.layer))
  if (other.length) {
    groups.push({ layer: '?', cn: '其他 Other', en: 'Other', accent: '#64748b', agent: '—', nodes: other })
  }
  return groups
}
