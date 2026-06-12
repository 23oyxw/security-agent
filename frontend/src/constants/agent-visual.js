/**
 * 三 Agent 视觉规范 — 侧栏色带 / 状态灯 / 括号标注
 * 对齐 FINAL_ARCHITECTURE §二
 */

export const AGENT_VISUAL = {
  core_dispatch: {
    id: 'core_dispatch',
    shortLabel: '核心调度',
    bracket: '（核心调度 · L1+L3）',
    color: '#3b82f6',
    glow: 'rgba(59, 130, 246, 0.45)',
    layers: ['L1', 'L3', 'GATE'],
  },
  safety_sandbox: {
    id: 'safety_sandbox',
    shortLabel: '安全沙箱',
    bracket: '（安全沙箱 · L2）',
    color: '#10b981',
    glow: 'rgba(16, 185, 129, 0.45)',
    layers: ['L2'],
  },
  audit_iteration: {
    id: 'audit_iteration',
    shortLabel: '审计迭代',
    bracket: '（审计迭代 · L4+L5）',
    color: '#8b5cf6',
    glow: 'rgba(139, 92, 246, 0.45)',
    layers: ['L4', 'L5'],
  },
}

export function agentVisual(agentId) {
  return AGENT_VISUAL[agentId] || AGENT_VISUAL.core_dispatch
}

export function agentColor(agentId) {
  return agentVisual(agentId).color
}
