import { TOOL_CLUSTERS } from './agents'

const L3_CLUSTER_RAILS = TOOL_CLUSTERS.map(c => `rail-l3-${c.cluster}`)

export const STAGE_SPINE_MAP = {
  L1_triple_perception: ['spine-l1-input', 'spine-l1-plan', 'rail-l1-boundary', 'rail-l1-knowledge', 'rail-l1-static'],
  L1_intent: ['spine-l1-plan'],
  L1_analyze_task: ['spine-l1-plan', 'rail-l1-reports'],
  L2_safety_sandbox: ['spine-l2-verdict', 'rail-l2-intent', 'rail-l2-sandbox', 'rail-l2-guard'],
  GATE_layer_pass: ['spine-gate'],
  L3_execute_start: ['spine-l3-exec', 'rail-l3-mcp', 'rail-l3-flow', ...L3_CLUSTER_RAILS],
  L4_audit_finalize: ['spine-l4-trace', 'rail-l4-chart', 'rail-l4-audit', 'rail-l4-wiki'],
  L5_analytics_snapshot: ['spine-l5-analytics', 'rail-l5-scatter', 'rail-l5-heatmap', 'rail-l5-root', 'rail-l5-test'],
  receive_request: ['spine-l1-input'],
  approved_plan_dispatch: ['spine-gate'],
  skill_flow_start: ['rail-l3-flow', 'spine-l3-exec'],
  skill_flow_end: ['rail-l3-flow', 'spine-l3-exec'],
  safety_check: ['spine-l2-verdict', 'rail-l2-sandbox'],
  harness_verify: ['rail-l2-sandbox'],
  execution: ['spine-l3-exec'],
  inference_decision: ['spine-l1-plan', 'spine-l3-exec'],
  environment_probe: ['rail-l1-static'],
  environment_probe_result: ['rail-l1-static'],
  post_verify: ['spine-l4-trace'],
}

export const LAYER_MAIN_SPINE = {
  L1: ['spine-l1-input', 'spine-l1-plan'],
  L2: ['spine-l2-verdict'],
  GATE: ['spine-gate'],
  L3: ['spine-l3-exec'],
  L4: ['spine-l4-trace'],
  L5: ['spine-l5-analytics'],
}

export const CLUSTER_RAIL_IDS = Object.fromEntries(TOOL_CLUSTERS.map(c => [c.cluster, `rail-l3-${c.cluster}`]))

export function extractStageKeys(traceNodes = []) {
  return traceNodes.map(n => {
    const d = n.details || n.data || {}
    return n.stage_key || d.stage_key || n.name || ''
  }).filter(Boolean)
}

export function resolveLiveNodeIds(traceNodes = []) {
  const ids = new Set()
  for (const key of extractStageKeys(traceNodes)) {
    for (const id of STAGE_SPINE_MAP[key] || []) ids.add(id)
  }
  for (const n of traceNodes) {
    const d = n.details || n.data || {}
    const layer = n.layer || d.layer
    for (const id of LAYER_MAIN_SPINE[layer] || []) ids.add(id)
    const railId = CLUSTER_RAIL_IDS[n.cluster || d.cluster]
    if (railId) ids.add(railId)
  }
  return ids
}

export function resolveActiveAgents(traceNodes = []) {
  const keys = new Set(extractStageKeys(traceNodes))
  const layers = new Set(traceNodes.map(n => n.layer || (n.details || n.data || {}).layer).filter(Boolean))
  const active = new Set()
  if (keys.has('L1_triple_perception') || keys.has('L1_intent') || layers.has('L1')) active.add('core_dispatch')
  if (keys.has('L2_safety_sandbox') || layers.has('L2')) active.add('safety_sandbox')
  if (keys.has('GATE_layer_pass') || layers.has('GATE') || keys.has('L3_execute_start') || layers.has('L3')) active.add('core_dispatch')
  if (keys.has('L4_audit_finalize') || keys.has('L5_analytics_snapshot') || layers.has('L4') || layers.has('L5')) active.add('audit_iteration')
  return [...active]
}
