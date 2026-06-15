/** 三方统一 — 真源 data/contracts/triple_unify.json */
import {
  CONTRACT_VERSION,
  FORMULA,
  MAIN_LINE,
  ORCHESTRATOR,
  AGENTS,
  PIPELINE_LAYERS,
  TOOL_CLUSTERS,
  SPINE_ORDER,
  LAYER_AGENT_MAP,
  STAGE_SPINE_MAP_RAW,
  LAYER_MAIN_SPINE,
} from './from-contract'

export {
  CONTRACT_VERSION,
  FORMULA,
  MAIN_LINE,
  ORCHESTRATOR,
  AGENTS,
  PIPELINE_LAYERS,
  TOOL_CLUSTERS,
  SPINE_ORDER,
  LAYER_AGENT_MAP,
  STAGE_SPINE_MAP_RAW,
  LAYER_MAIN_SPINE,
}

export const L1_TRIPLE_PERCEPTION = [
  {
    id: 'adversarial_boundary',
    title: '抗性边界感知',
    desc: '对抗训练边界校验 · 权限跃迁阻力 · 越界识别',
    icon: 'WarningFilled',
  },
  {
    id: 'sensitive_knowledge',
    title: '灵敏知识库检索',
    desc: '规范 · 流程 · 故障 · 调度 · 工具说明',
    icon: 'Reading',
  },
  {
    id: 'static_environment_eye',
    title: '静态环境感知（眼）',
    desc: '网络 · 端口 · CPU · 内存 · 磁盘 · 链路 · 权限 · 状态',
    icon: 'View',
  },
]

export const BATCH_STATUS = {
  queued: '排队',
  analyzing: 'L1 分析中',
  awaiting_approval: '待 L2/确认',
  executing: 'L3 执行中',
  auditing: 'L4/L5 审计',
  done: '完成',
  blocked: 'L2 拒绝',
  failed: '失败',
}

export function defaultAgentStages() {
  return AGENTS.map(a => ({ ...a, status: 'idle', detail: '' }))
}

export function mergeAgentStages(apiStages) {
  if (!apiStages?.length) return defaultAgentStages()
  return AGENTS.map(meta => {
    const hit = apiStages.find(s => s.agent === meta.agent)
    return hit
      ? { ...meta, status: hit.status || 'idle', detail: hit.detail || '' }
      : { ...meta, status: 'idle', detail: '' }
  })
}
