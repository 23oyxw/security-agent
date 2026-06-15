/** 三方统一契约 — data/contracts/triple_unify.json */
import raw from '../../../data/contracts/triple_unify.json'

export const CONTRACT_VERSION = raw.version
export const CONTRACT_UPDATED = raw.updated
export const FORMULA = raw.formula
export const MAIN_LINE = raw.main_line
export const AUXILIARY = raw.auxiliary
export const LAYER_AGENT_MAP = raw.layer_agent_map
export const PIPELINE_STAGES = raw.pipeline_stages
export const STAGE_SPINE_MAP_RAW = raw.stage_spine_map
export const LAYER_MAIN_SPINE = raw.layer_main_spine

const ICONS = {
  core_dispatch: 'Cpu',
  safety_sandbox: 'Lock',
  audit_iteration: 'DataLine',
}
const COLORS = {
  core_dispatch: 'primary',
  safety_sandbox: 'warning',
  audit_iteration: 'info',
}
const CLUSTER_ICONS = {
  metrics: 'Odometer',
  logs: 'Document',
  repair: 'SetUp',
  dispatch: 'Grid',
}

export const ORCHESTRATOR = {
  id: raw.orchestrator.id,
  displayName: raw.orchestrator.display_name,
  description: raw.orchestrator.description,
  formula: raw.formula,
  modes: [
    { value: 'plan', label: '计划模式', layer: 'L1', hint: '只分析，不执行' },
    { value: 'execute', label: '执行模式', layer: 'L3', hint: '需 L2 通过 + plan_id' },
  ],
}

export const AGENTS = (raw.agents || []).map(a => ({
  agent: a.agent,
  displayName: a.display_name,
  layer: a.layer,
  layerNote: a.layer_note,
  description: a.description,
  phases: a.phases,
  icon: ICONS[a.agent] || 'Cpu',
  color: COLORS[a.agent] || 'primary',
}))

export const PIPELINE_LAYERS = (raw.pipeline_layers || []).map(row => ({ ...row }))

export const TOOL_CLUSTERS = (raw.tool_clusters || []).map(c => ({
  cluster: c.cluster,
  displayName: c.display_name,
  examples: c.examples,
  icon: CLUSTER_ICONS[c.cluster] || 'Grid',
}))

export const SPINE_ORDER = raw.main_line
