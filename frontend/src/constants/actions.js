/** 流水线操作按钮 — 层语义 · 文案 · 图标统一 */

export const LAYER_BTN_TYPES = {
  L1: 'primary',
  L2: 'warning',
  L3: 'success',
  L4: 'info',
  L5: '',
  neutral: 'default',
}

export const PIPELINE_ACTIONS = {
  l1Analyze: {
    id: 'l1Analyze',
    layer: 'L1',
    label: 'L1 三感知分析',
    icon: 'Search',
    type: 'primary',
    hint: 'analyze 阶段锁 · 零工具零执行',
  },
  l2Precheck: {
    id: 'l2Precheck',
    layer: 'L2',
    label: 'L2 安全预检',
    icon: 'Lock',
    type: 'warning',
    hint: '安全防护沙箱 · 只校验不执行',
  },
  l3Execute: {
    id: 'l3Execute',
    layer: 'L3',
    label: 'L3 执行',
    icon: 'Promotion',
    type: 'success',
    hint: '需 plan_id + L2 通过',
  },
  l3ConfirmExecute: {
    id: 'l3ConfirmExecute',
    layer: 'L3',
    label: '确认并 L3 执行',
    icon: 'WarningFilled',
    type: 'warning',
    hint: '高危操作二次确认',
  },
  batchEnqueue: {
    id: 'batchEnqueue',
    layer: 'L1',
    label: '批量 L1 分析',
    icon: 'List',
    type: 'primary',
    hint: '每条独立 trace · 共享 batch_id',
  },
  traceView: {
    id: 'traceView',
    layer: 'L4',
    label: '查看 Trace',
    icon: 'Share',
    type: 'info',
    plain: true,
  },
  clear: {
    id: 'clear',
    layer: null,
    label: '清空',
    icon: 'Delete',
    type: 'default',
    plain: true,
  },
  goAgent: {
    id: 'goAgent',
    layer: 'L1',
    label: '前往智能体编排',
    icon: 'Cpu',
    type: 'primary',
    plain: true,
  },
  refresh: {
    id: 'refresh',
    layer: null,
    label: '立即刷新',
    icon: 'Refresh',
    type: 'primary',
    plain: true,
  },
}

export function getAction(id) {
  return PIPELINE_ACTIONS[id] || null
}
