/** 终版 v1.0 — 1调度+1安全+1迭代 · 与 agent_registry.py 对齐 */

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

export const ORCHESTRATOR = {
  id: 'orchestrator',
  displayName: '编排助手',
  description: '前端双模式：计划(L1 analyze) / 执行(L3 execute)',
  formula: '1调度 + 1安全 + 1迭代',
  modes: [
    { value: 'plan', label: '计划模式', layer: 'L1', hint: '只分析，不执行' },
    { value: 'execute', label: '执行模式', layer: 'L3', hint: '需 L2 通过 + plan_id' },
  ],
}

export const AGENTS = [
  {
    agent: 'core_dispatch',
    displayName: '核心调度代理',
    layer: 'L1+L3',
    layerNote: '阶段锁',
    description: 'L1 三感知：抗性边界·灵敏知识·静态之眼 | L3 推理·MCP',
    phases: ['analyze', 'execute'],
    icon: 'Cpu',
    color: 'primary',
  },
  {
    agent: 'safety_sandbox',
    displayName: '安全防护沙箱',
    layer: 'L2',
    layerNote: '安全闸门',
    description: '护栏·熔断·沙箱预演·高危截断·二次确认',
    phases: ['precheck'],
    icon: 'Lock',
    color: 'warning',
  },
  {
    agent: 'audit_iteration',
    displayName: '审计迭代代理',
    layer: 'L4+L5',
    layerNote: '闭环',
    description: 'trace 卷宗·链路绘图·Wiki 回流·量化自进化',
    phases: ['finalize'],
    icon: 'DataLine',
    color: 'info',
  },
]

export const PIPELINE_LAYERS = [
  { id: 'L1', label: '分析', agent: 'core_dispatch', phase: 'analyze' },
  { id: 'L2', label: '防护', agent: 'safety_sandbox' },
  { id: 'L3', label: '执行', agent: 'core_dispatch', phase: 'execute' },
  { id: 'L4', label: '审计', agent: 'audit_iteration' },
  { id: 'L5', label: '迭代', agent: 'audit_iteration' },
]

export const TOOL_CLUSTERS = [
  { cluster: 'metrics', displayName: '指标采集', icon: 'Odometer' },
  { cluster: 'logs', displayName: '日志处理', icon: 'Document' },
  { cluster: 'repair', displayName: '故障修复', icon: 'SetUp' },
  { cluster: 'dispatch', displayName: '资源调度', icon: 'Grid' },
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
