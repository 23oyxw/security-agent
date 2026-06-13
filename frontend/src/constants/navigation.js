/**
 * 全站导航与页面编排 — 单一数据源
 * 对齐 FINAL_ARCHITECTURE · MULTI_PERSONA_COORDINATION
 */

export const NAV_GROUPS = []

/** 侧栏底部辅助入口（非五层主按钮，避免与 PipelineRail 重复） */
export const SIDEBAR_FOOTER_LINKS = [
  { id: 'guide', path: '/guide', label: '架构导引', icon: 'Document' },
  { id: 'users', path: '/users', label: '用户管理', icon: 'User', admin: true },
]

/** @type {Record<string, NavPage>} */
export const NAV_PAGES = {
  dashboard: {
    id: 'dashboard',
    path: '/',
    name: 'Dashboard',
    label: '运维概览',
    shortLabel: '概览',
    icon: 'Odometer',
    theme: 'ops',
    layer: null,
    layerLabel: '运维总览',
    subtitle: '系统健康 · 资源 · 快捷入口',
    agent: null,
  },
  l5: {
    id: 'l5',
    path: '/l5',
    name: 'L5Analytics',
    label: 'L5 链路量化',
    shortLabel: 'L5 量化',
    icon: 'TrendCharts',
    theme: 'ops',
    layer: 'L5',
    layerLabel: 'L5 统计迭代',
    subtitle: '散点/热力/溯源 · 六维指标 · 集成测试（不做卷宗）',
    agent: 'audit_iteration',
  },
  agent: {
    id: 'agent',
    path: '/agent',
    name: 'Agent',
    label: '智能体对话',
    shortLabel: '智能体对话',
    icon: 'ChatDotRound',
    theme: 'intel',
    layer: 'L1+L3',
    layerLabel: 'L1 分析 · L3 执行',
    subtitle: '在这里输入运维指令 · 计划模式先分析 · 执行模式再操作',
    agent: 'core_dispatch',
    primary: true,
    entryLabel: '入口',
  },
  canvas: {
    id: 'canvas',
    path: '/canvas',
    name: 'Canvas',
    label: '五层架构画布',
    shortLabel: '架构画布',
    icon: 'Grid',
    theme: 'canvas',
    layer: 'L1-L5',
    layerLabel: '五层刚性流程',
    subtitle: '三 Agent 协同 · L1→L5 · 静态/链路/指标三类绘图',
    agent: null,
  },
  safety: {
    id: 'safety',
    path: '/safety',
    name: 'Safety',
    label: 'L2 安全防护沙箱',
    shortLabel: 'L2 防护',
    icon: 'Lock',
    theme: 'guard',
    layer: 'L2',
    layerLabel: 'L2 安全防护',
    subtitle: '护栏 · 熔断 · 沙箱预演 · 零执行零决策',
    agent: 'safety_sandbox',
  },
  alerts: {
    id: 'alerts',
    path: '/alerts',
    name: 'Alerts',
    label: '告警中心',
    shortLabel: '告警',
    icon: 'Bell',
    theme: 'alert',
    layer: 'L2',
    layerLabel: 'L2 告警联动',
    subtitle: '规则命中 · 关联 trace 下钻',
  },
  workflow: {
    id: 'workflow',
    path: '/workflow',
    name: 'Workflow',
    label: '流水线观测',
    shortLabel: '流水线',
    icon: 'SetUp',
    theme: 'audit',
    layer: 'L1-L5',
    layerLabel: '五层实时观测',
    subtitle: '主线泳道 · 工作流定义 · MCP/Skill 分层 · 三 Agent 协同',
  },
  reports: {
    id: 'reports',
    path: '/reports',
    name: 'Reports',
    label: '任务分析报表',
    shortLabel: '分析报表',
    icon: 'Document',
    theme: 'intel',
    layer: 'L1',
    layerLabel: '任务分层分析',
    subtitle: 'Prompt/命令分析 · 上传 · 工作流匹配 · 学术参照',
    agent: 'core_dispatch',
  },
  mcp: {
    id: 'mcp',
    path: '/mcp',
    name: 'MCP',
    label: 'L3 工具能力中心',
    shortLabel: 'MCP',
    icon: 'Connection',
    theme: 'mesh',
    layer: 'L3',
    layerLabel: 'L3 四工具簇',
    subtitle: '指标 · 日志 · 修复 · 调度 — 单工具单职责',
  },
  trace: {
    id: 'trace',
    path: '/trace',
    name: 'Trace',
    label: 'L4 Trace 卷宗',
    shortLabel: 'L4 卷宗',
    icon: 'Share',
    theme: 'audit',
    layer: 'L4',
    layerLabel: 'L4 审计追溯',
    subtitle: 'append-only 卷宗 · stage 时间线 · Wiki 回流（不做量化）',
    agent: 'audit_iteration',
  },
  knowledge: {
    id: 'knowledge',
    path: '/knowledge',
    name: 'Knowledge',
    label: 'L1 知识库检索',
    shortLabel: '知识库',
    icon: 'Reading',
    theme: 'archive',
    layer: 'L1',
    layerLabel: 'L1 灵敏检索',
    subtitle: '规范 · 流程 · 故障 · Gitee Wiki 索引',
  },
  perception: {
    id: 'perception',
    path: '/perception',
    name: 'Perception',
    label: 'L1 态势总览',
    shortLabel: '态势总览',
    icon: 'View',
    theme: 'intel',
    layer: 'L1',
    layerLabel: 'L1 静态感知（眼）',
    subtitle: '8维只读仪表盘 · 网络/端口/CPU/内存/磁盘/链路/权限/状态',
    agent: 'core_dispatch',
  },
  l1Boundary: {
    id: 'l1Boundary',
    path: '/l1/boundary',
    name: 'L1Boundary',
    label: 'L1 边界对抗感知',
    shortLabel: '边界对抗',
    icon: 'WarningFilled',
    theme: 'intel',
    layer: 'L1',
    layerLabel: 'L1 抗性边界',
    subtitle: '对抗训练矩阵 · 权限跃迁阻力 · 101条校准',
    agent: 'core_dispatch',
  },
  guide: {
    id: 'guide',
    path: '/guide',
    name: 'Guide',
    label: '架构导引',
    shortLabel: '导引',
    icon: 'Document',
    theme: 'learn',
    layer: null,
    subtitle: '五层流水线 · 三 Agent · 使用说明',
  },
  users: {
    id: 'users',
    path: '/users',
    name: 'Users',
    label: '用户管理',
    shortLabel: '用户',
    icon: 'User',
    theme: 'admin',
    layer: null,
    admin: true,
  },
}

/** 五层快捷轨 — PillarWorkflowRail */
export const PILLAR_STEPS = [
  {
    pageId: 'agent',
    layer: 'L1',
    label: 'L1 三感知',
    desc: '抗性边界 · 灵敏知识 · 静态之眼（并行 · 零工具）',
  },
  {
    pageId: 'safety',
    layer: 'L2',
    label: 'L2 防护',
    desc: '安全防护沙箱 · 护栏/熔断/二次确认',
  },
  {
    pageId: 'agent',
    layer: 'L3',
    label: 'L3 执行',
    desc: '智能体对话 · 执行模式 · MCP 四工具簇',
  },
  {
    pageId: 'trace',
    layer: 'L4',
    label: 'L4 卷宗',
    desc: 'Trace 卷宗 · 审计追溯 · Wiki 回流',
  },
  {
    pageId: 'l5',
    layer: 'L5',
    label: 'L5 量化',
    desc: '散点/热力/溯源 · 六维指标 · 集成测试',
  },
]

export const THEME_LABELS = {
  ops: 'L5 运维蓝',
  intel: 'L1/L3 编排紫',
  guard: 'L2 安全绿',
  alert: 'L2 告警橙',
  mesh: 'L3 MCP 靛',
  audit: 'L4 审计灰',
  archive: 'L1 知识青',
  learn: '导引黄蓝',
  canvas: '画布',
  admin: '管理玫',
}

const LAYER_ACTIVE_MAP = {
  L1: ['/agent', '/knowledge', '/perception', '/l1/boundary', '/reports'],
  L2: ['/safety', '/alerts', '/executor', '/blue-team'],
  L3: ['/agent', '/mcp', '/flows'],
  L4: ['/trace'],
  L5: ['/l5'],
  'L1-L5': ['/canvas', '/workflow'],
}

export function normalizePath(path) {
  if (!path || path === '/dashboard') return '/'
  return path
}

export function getPageByPath(path) {
  const p = normalizePath(path)
  return Object.values(NAV_PAGES).find(page => page.path === p) || null
}

export function getPageLabel(path) {
  return getPageByPath(path)?.label || '页面'
}

export function getThemeLabel(theme) {
  return THEME_LABELS[theme] || ''
}

/** Sidebar 菜单项 — 已合并至 PipelineArchitectureRail，此处仅保留底部链接 */
export function buildSidebarGroups(badgeFns = {}) {
  return []
}

export function buildSidebarFooterLinks(userRole = '') {
  return SIDEBAR_FOOTER_LINKS.filter(link => !link.admin || userRole === 'admin')
}

export function isPillarStepActive(step, currentPath) {
  const p = normalizePath(currentPath)
  const paths = LAYER_ACTIVE_MAP[step.layer] || [NAV_PAGES[step.pageId]?.path]
  return paths.some(prefix => p === prefix || p.startsWith(prefix + '/'))
}

export function getPillarStepPath(step) {
  return NAV_PAGES[step.pageId]?.path || '/'
}
