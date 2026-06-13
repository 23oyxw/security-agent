/**
 * 五层分割画布 — 主线简化（中右）· 能力辅线左侧竖排 · 分层跳转
 */

import { PIPELINE_FORMULA } from './pipeline-architecture'
import { L1_TRIPLE_PERCEPTION, TOOL_CLUSTERS } from './agents'

export const CANVAS_META = {
  title: '五层分割 · 主线 + 辅线',
  formula: PIPELINE_FORMULA,
  subtitle: 'Main Spine 主线 · Left Rail 辅线 · 点击层标签跳转 · Trace 对齐 L1–L5',
}

/** 五层水平分割带（背景 + 跳转） */
export const CANVAS_LAYER_BANDS = [
  { layer: 'L1', y: 0, h: 250, accent: '#3b82f6', label: 'L1 分析计划', labelEn: 'Analyze', route: '/agent' },
  { layer: 'L2', y: 250, h: 170, accent: '#10b981', label: 'L2 安全防护', labelEn: 'Safety', route: '/safety' },
  { layer: 'GATE', y: 420, h: 70, accent: '#f59e0b', label: '层间门禁', labelEn: 'Gate', route: '/agent' },
  { layer: 'L3', y: 490, h: 230, accent: '#f59e0b', label: 'L3 推理执行', labelEn: 'Execute', route: '/agent' },
  { layer: 'L4', y: 720, h: 190, accent: '#8b5cf6', label: 'L4 Trace 卷宗', labelEn: 'Audit', route: '/trace' },
  { layer: 'L5', y: 910, h: 260, accent: '#0ea5e9', label: 'L5 链路量化', labelEn: 'Analytics', route: '/l5' },
]

export const CANVAS_LAYERS = ['L1', 'L2', 'L3', 'L4', 'L5']

export const CANVAS_LAYER_META = {
  L1: { label: 'L1 分析计划', labelEn: 'Analyze', agent: 'core_dispatch', accent: '#3b82f6' },
  L2: { label: 'L2 安全防护', labelEn: 'Safety', agent: 'safety_sandbox', accent: '#10b981' },
  GATE: { label: '层间门禁', labelEn: 'Gate', agent: 'core_dispatch', accent: '#f59e0b' },
  L3: { label: 'L3 推理执行', labelEn: 'Execute', agent: 'core_dispatch', accent: '#f59e0b' },
  L4: { label: 'L4 Trace 卷宗', labelEn: 'Audit', agent: 'audit_iteration', accent: '#8b5cf6' },
  L5: { label: 'L5 链路量化', labelEn: 'Analytics', agent: 'audit_iteration', accent: '#0ea5e9' },
}

const SPINE_X = 520
const RAIL_X = 72
const RAIL_W = 168

/** tier: spine 主线 | rail 左侧辅线 */
const NODES = [
  // ═══ L1 带 ═══
  { id: 'rail-l1-boundary', type: 'snapshot', x: RAIL_X, y: 36, tier: 'rail', layer: 'L1',
    data: { label: '边界对抗', labelEn: 'Boundary', time: 'Adversarial · PE Probes', risk: 'L1', route: '/l1/boundary' } },
  { id: 'rail-l1-knowledge', type: 'skill', x: RAIL_X, y: 96, tier: 'rail', layer: 'L1',
    data: { label: '知识检索', labelEn: 'Knowledge', toolsLabel: 'Wiki RAG · Intent', route: '/knowledge' } },
  { id: 'rail-l1-static', type: 'monitor', x: RAIL_X, y: 156, tier: 'rail', layer: 'L1',
    data: { label: '态势总览', labelEn: 'Situation', value: '—%', sub: 'Static Eye · 8维', percent: 0, alert: false, route: '/perception', encapsulation: 'T1' } },
  { id: 'rail-l1-reports', type: 'skill', x: RAIL_X, y: 216, tier: 'rail', layer: 'L1',
    data: { label: '任务分析', labelEn: 'Task Analyze', toolsLabel: 'Prompt · Upload', route: '/reports', encapsulation: 'T3' } },

  { id: 'spine-l1-input', type: 'executor', x: SPINE_X, y: 40, tier: 'spine', layer: 'L1',
    data: { label: '用户输入', labelEn: 'User Input', command: 'Plan Mode · 计划模式', status: 'entry', statusText: 'Start', route: '/agent', agent: 'core_dispatch', role: 'main' } },
  { id: 'spine-l1-plan', type: 'trace', x: SPINE_X, y: 160, tier: 'spine', layer: 'L1',
    data: { label: '计划产出', labelEn: 'Plan Output', stages: 'plan_id · trace_id', ok: true, stageCount: 4, okStages: 4, route: '/agent', agent: 'core_dispatch', role: 'main' } },

  // ═══ L2 带 ═══
  { id: 'rail-l2-intent', type: 'snapshot', x: RAIL_X, y: 270, tier: 'rail', layer: 'L2',
    data: { label: '安全意图', labelEn: 'Safety Intent', time: 'Risk Classify', risk: 'L2', route: '/safety' } },
  { id: 'rail-l2-sandbox', type: 'executor', x: RAIL_X, y: 320, tier: 'rail', layer: 'L2',
    data: { label: '沙箱预演', labelEn: 'Sandbox', command: 'Dry-run · 零执行', status: 'active', statusText: 'Trial', route: '/safety' } },
  { id: 'rail-l2-guard', type: 'skill', x: RAIL_X, y: 370, tier: 'rail', layer: 'L2',
    data: { label: '全局护栏', labelEn: 'Guardrails', toolsLabel: 'Fuse · Confirm', route: '/safety' } },

  { id: 'spine-l2-verdict', type: 'executor', x: SPINE_X, y: 300, tier: 'spine', layer: 'L2',
    data: { label: 'L2 裁决', labelEn: 'Verdict', command: 'pass / confirm / deny', status: 'gate', statusText: 'Gate', route: '/safety', agent: 'safety_sandbox', role: 'main' } },

  // ═══ GATE ═══
  { id: 'spine-gate', type: 'executor', x: SPINE_X, y: 430, tier: 'spine', layer: 'GATE',
    data: { label: '层间门禁', labelEn: 'Mode Gate', command: 'plan + L2 → execute', status: 'locked', statusText: 'GATE', route: '/agent', agent: 'core_dispatch', role: 'main' } },

  // ═══ L3 带 ═══
  { id: 'rail-l3-mcp', type: 'skill', x: RAIL_X, y: 510, tier: 'rail', layer: 'L3',
    data: { label: 'MCP 热插拔', labelEn: 'MCP Hub', toolsLabel: 'Hot-swap Tools', route: '/mcp', encapsulation: 'T0', role: 'auxiliary' } },
  { id: 'rail-l3-flow', type: 'executor', x: RAIL_X, y: 560, tier: 'rail', layer: 'L3',
    data: { label: '封装流程', labelEn: 'Skill Flow', command: 'L2 Flow → L3 Run', status: 'active', statusText: 'Flow', route: '/flows', encapsulation: 'T3', role: 'auxiliary' } },
  ...TOOL_CLUSTERS.map((c, i) => ({
    id: `rail-l3-${c.cluster}`,
    type: 'skill',
    x: RAIL_X,
    y: 610 + i * 48,
    tier: 'rail',
    layer: 'L3',
    data: {
      label: c.displayName,
      labelEn: c.cluster,
      toolsLabel: `${c.cluster} cluster`,
      route: '/mcp',
      role: 'auxiliary',
      encapsulation: 'T0',
    },
  })),

  { id: 'spine-l3-exec', type: 'executor', x: SPINE_X, y: 560, tier: 'spine', layer: 'L3',
    data: { label: 'L3 执行', labelEn: 'Dispatch', command: 'MCP + Tools · 唯一写操作', status: 'ready', statusText: 'Execute', route: '/agent', agent: 'core_dispatch', role: 'main' } },

  // ═══ L4 带 ═══
  { id: 'rail-l4-chart', type: 'snapshot', x: RAIL_X, y: 740, tier: 'rail', layer: 'L4',
    data: { label: '链路绘图', labelEn: 'Link Chart', time: 'Timeline / DAG', risk: 'L4', route: '/trace' } },
  { id: 'rail-l4-audit', type: 'trace', x: RAIL_X, y: 800, tier: 'rail', layer: 'L4',
    data: { label: '审计 JSONL', labelEn: 'Audit Log', stages: 'append-only', ok: true, stageCount: 6, okStages: 6, route: '/trace' } },
  { id: 'rail-l4-wiki', type: 'executor', x: RAIL_X, y: 860, tier: 'rail', layer: 'L4',
    data: { label: 'Wiki 回流', labelEn: 'Wiki Reflux', command: 'Case → Gitee', status: 'cycle', statusText: 'Reflux', route: '/knowledge' } },

  { id: 'spine-l4-trace', type: 'trace', x: SPINE_X, y: 780, tier: 'spine', layer: 'L4',
    data: { label: 'Trace 卷宗', labelEn: 'Trace Record', stages: 'Full chain · 全链路', ok: true, stageCount: 6, okStages: 6, route: '/trace', agent: 'audit_iteration', role: 'auxiliary' } },

  // ═══ L5 带 ═══
  { id: 'rail-l5-scatter', type: 'monitor', x: RAIL_X, y: 930, tier: 'rail', layer: 'L5',
    data: { label: '散点离群', labelEn: 'Scatter', value: '3σ', sub: 'Outlier', percent: 0, route: '/l5' } },
  { id: 'rail-l5-heatmap', type: 'snapshot', x: RAIL_X, y: 990, tier: 'rail', layer: 'L5',
    data: { label: '热力矩阵', labelEn: 'Heatmap', time: 'Time × Service', risk: 'Batch', route: '/l5' } },
  { id: 'rail-l5-root', type: 'trace', x: RAIL_X, y: 1050, tier: 'rail', layer: 'L5',
    data: { label: '链路溯源', labelEn: 'Root Cause', stages: 'Span → RCA', ok: true, stageCount: 5, okStages: 5, route: '/l5' } },
  { id: 'rail-l5-test', type: 'executor', x: RAIL_X, y: 1110, tier: 'rail', layer: 'L5',
    data: { label: '集成测试', labelEn: 'Integration', command: 'L1–L5 Matrix', status: 'active', statusText: 'Test', route: '/l5' } },

  { id: 'spine-l5-analytics', type: 'monitor', x: SPINE_X, y: 980, tier: 'spine', layer: 'L5',
    data: { label: 'L5 量化', labelEn: 'Analytics Hub', value: '6 KPIs', sub: 'Scatter · Heat · RCA', percent: 78, route: '/l5', agent: 'audit_iteration', role: 'auxiliary' } },
]

// 兼容旧导出
export const CANVAS_SNAKE_ZONES = CANVAS_LAYER_BANDS

export function buildCanvasNodes() {
  return NODES.map(n => ({
    id: n.id,
    type: n.type,
    position: { x: n.x, y: n.y },
    data: {
      ...n.data,
      layer: n.layer,
      tier: n.tier,
      accent: CANVAS_LAYER_META[n.layer]?.accent,
    },
  }))
}

export function getLayerNodeIds(layer) {
  return NODES.filter(n => n.layer === layer).map(n => n.id)
}

export function buildCanvasEdges() {
  const edge = (id, source, target, label, color, extra = {}) => ({
    id,
    source,
    target,
    type: 'smoothstep',
    animated: Boolean(extra.animated ?? (extra.kind === 'spine')),
    label,
    data: { kind: extra.kind || 'spine' },
    style: { stroke: color, strokeWidth: extra.strokeWidth || 2, ...extra.style },
    ...extra,
  })

  const feed = (id, source, target, spineId, color) =>
    edge(id, source, target, '馈入 Feed', color, {
      kind: 'feed',
      animated: false,
      strokeWidth: 1.2,
      style: { strokeDasharray: '5 4', opacity: 0.65 },
    })

  return [
    // ── 主线 Main Spine ──
    edge('s-e1', 'spine-l1-input', 'spine-l1-plan', 'Analyze', '#3b82f6', { kind: 'spine', strokeWidth: 3 }),
    edge('s-e2', 'spine-l1-plan', 'spine-l2-verdict', 'Safety', '#10b981', { kind: 'spine', strokeWidth: 3 }),
    edge('s-e3', 'spine-l2-verdict', 'spine-gate', 'Gate', '#f59e0b', { kind: 'spine', strokeWidth: 3 }),
    edge('s-e4', 'spine-gate', 'spine-l3-exec', 'Execute', '#f59e0b', { kind: 'spine', strokeWidth: 3 }),
    edge('s-e5', 'spine-l3-exec', 'spine-l4-trace', 'Audit', '#8b5cf6', { kind: 'spine', strokeWidth: 3 }),
    edge('s-e6', 'spine-l4-trace', 'spine-l5-analytics', 'Analytics', '#0ea5e9', { kind: 'spine', strokeWidth: 3 }),

    // ── L1 辅线 → 计划 ──
    feed('f-l1-b', 'rail-l1-boundary', 'spine-l1-plan', 'spine-l1-plan', '#3b82f6'),
    feed('f-l1-k', 'rail-l1-knowledge', 'spine-l1-plan', 'spine-l1-plan', '#3b82f6'),
    feed('f-l1-s', 'rail-l1-static', 'spine-l1-plan', 'spine-l1-plan', '#3b82f6'),
    feed('f-l1-r', 'rail-l1-reports', 'spine-l1-plan', 'spine-l1-plan', '#3b82f6'),

    // ── L2 辅线 → 裁决 ──
    feed('f-l2-i', 'rail-l2-intent', 'spine-l2-verdict', 'spine-l2-verdict', '#10b981'),
    feed('f-l2-sb', 'rail-l2-sandbox', 'spine-l2-verdict', 'spine-l2-verdict', '#10b981'),
    feed('f-l2-g', 'rail-l2-guard', 'spine-l2-verdict', 'spine-l2-verdict', '#10b981'),

    // ── L3 辅线 → 执行 ──
    feed('f-l3-mcp', 'rail-l3-mcp', 'spine-l3-exec', 'spine-l3-exec', '#f59e0b'),
    feed('f-l3-fl', 'rail-l3-flow', 'spine-l3-exec', 'spine-l3-exec', '#f59e0b'),
    ...TOOL_CLUSTERS.map(c =>
      feed(`f-l3-${c.cluster}`, `rail-l3-${c.cluster}`, 'spine-l3-exec', 'spine-l3-exec', '#f59e0b'),
    ),

    // ── L4 辅线 → 卷宗 ──
    feed('f-l4-c', 'rail-l4-chart', 'spine-l4-trace', 'spine-l4-trace', '#8b5cf6'),
    feed('f-l4-a', 'rail-l4-audit', 'spine-l4-trace', 'spine-l4-trace', '#8b5cf6'),
    feed('f-l4-w', 'rail-l4-wiki', 'spine-l4-trace', 'spine-l4-trace', '#8b5cf6'),

    // ── L5 辅线 → 量化中枢 ──
    feed('f-l5-sc', 'rail-l5-scatter', 'spine-l5-analytics', 'spine-l5-analytics', '#0ea5e9'),
    feed('f-l5-hm', 'rail-l5-heatmap', 'spine-l5-analytics', 'spine-l5-analytics', '#0ea5e9'),
    feed('f-l5-rc', 'rail-l5-root', 'spine-l5-analytics', 'spine-l5-analytics', '#0ea5e9'),
    feed('f-l5-t', 'rail-l5-test', 'spine-l5-analytics', 'spine-l5-analytics', '#0ea5e9'),

    // 闭环 Evolve → L1 boundary
    edge('s-loop', 'spine-l5-analytics', 'rail-l1-boundary', 'Evolve 反写', '#0ea5e9', {
      kind: 'loop',
      animated: false,
      strokeWidth: 1.5,
      style: { strokeDasharray: '8 6', opacity: 0.5 },
    }),
  ]
}

export { RAIL_X, RAIL_W, SPINE_X, L1_TRIPLE_PERCEPTION }
