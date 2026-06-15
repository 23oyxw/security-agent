import { TOOL_CLUSTERS, STAGE_SPINE_MAP_RAW, LAYER_MAIN_SPINE } from './from-contract'

const L3_CLUSTER_RAILS = TOOL_CLUSTERS.map(c => `rail-l3-${c.cluster}`)

export const STAGE_SPINE_MAP = {
  ...STAGE_SPINE_MAP_RAW,
  L3_execute_start: [
    'spine-l3-exec',
    'rail-l3-mcp',
    'rail-l3-flow',
    ...L3_CLUSTER_RAILS,
  ],
}

export { LAYER_MAIN_SPINE }

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
