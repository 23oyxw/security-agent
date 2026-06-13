/**
 * 侧栏五步流程 — 与 WORK_ACTIONS 一一对应
 * agentId 对齐三 Agent；extras 为层内辅助页（不重复顶栏旧导航）
 */

export const PIPELINE_FORMULA = '1 调度 + 1 安全 + 1 迭代'

export const LAYER_TRANSITION = {
  id: 'GATE',
  title: '层间门禁',
  desc: 'plan + L2 裁决 → 解锁 execute',
  checks: ['plan_id 有效', 'l2_verdict', 'requires_confirm'],
  agentId: 'core_dispatch',
}

export const SIDEBAR_LAYERS = [
  {
    id: 'L1',
    badge: 'L1',
    name: '分析计划',
    agentId: 'core_dispatch',
    agent: '核心调度 · analyze',
    accent: '#3b82f6',
    important: '最先启动、最易忽略。必须先完成分析计划，禁止跳过直执行。',
    constraint: '零工具 · 零执行',
    action: 'l1PlanMode',
    extras: [
      { label: '态势总览 · 静态之眼', path: '/perception', icon: 'View' },
      { label: 'L1 知识库', path: '/knowledge', icon: 'Reading' },
    ],
    nested: {
      label: '并行过程（同时进行）',
      items: [
        {
          key: 'overview',
          title: '态势总览',
          titleEn: 'Situation',
          desc: '静态之眼入口 · 8维仪表盘 · 只读',
          path: '/perception',
          primary: true,
          openLabel: '打开 Open →',
        },
        { key: 'boundary', title: '边界感知', titleEn: 'Boundary', desc: '对抗训练 · 权限跃迁阻力 · 101条校准', path: '/l1/boundary', openLabel: '打开 →' },
        {
          key: 'knowledge',
          title: '知识库 ∥ 意图',
          titleEn: 'Knowledge',
          desc: '灵敏 hybrid 检索 · 意图扩展 · Wiki/Playbook',
          path: '/knowledge',
          openLabel: '打开 →',
        },
        {
          key: 'static',
          title: '静态感知（眼）',
          desc: '8维：网络/端口 · CPU/内存/磁盘 · 链路 · 权限/状态 · 见态势总览',
        },
        { key: 'plan', title: '计划推理', desc: '意图检测 · 工具链草案 · 写入 plan 共享 · 对话内产出' },
      ],
    },
  },
  {
    id: 'L2',
    badge: 'L2',
    name: '安全防护栏',
    agentId: 'safety_sandbox',
    agent: '安全防护沙箱',
    accent: '#10b981',
    important: '唯一刚性闸门。只校验拦截，不参与执行决策。',
    constraint: '零执行 · 零决策',
    action: 'l2Safety',
    extras: [{ label: 'L2 告警中心', path: '/alerts', icon: 'Bell', badgeKey: 'alerts' }, { label: '环境修复', path: '/repair', icon: 'SetUp' }],
    items: [
      '沙箱隔离预演',
      '兜底回退机制',
      '刚性拦截 pass/confirm/deny',
      'MCP 热插拔',
      '指令超时熔断',
    ],
  },
  {
    id: 'L3',
    badge: 'L3',
    name: '推理分发调用',
    agentId: 'core_dispatch',
    agent: '核心调度 · execute',
    accent: '#f59e0b',
    important: '唯一允许 MCP/工具写操作。需 L2 通过后解锁。',
    action: 'l3ExecuteMode',
    extras: [{ label: 'L3 工具中心', path: '/mcp', icon: 'Connection' }],
    items: ['指标采集', '日志处理', '故障修复', '资源调度'],
  },
  {
    id: 'L4',
    badge: 'L4',
    name: 'Trace 卷宗',
    roleTag: '审计追溯',
    agentId: 'audit_iteration',
    agent: '审计迭代 · 只做卷宗',
    accent: '#8b5cf6',
    important: 'append-only 全链路 trace · 时序/拓扑绘图 · 案例打标 → Wiki 回流。',
    constraint: '不可篡改 · 不做量化',
    action: 'l4Trace',
    items: ['trace 卷宗导出', '链路 stage 时间线', '审计 JSONL', '知识回流'],
  },
  {
    id: 'L5',
    badge: 'L5',
    name: '链路量化分析',
    roleTag: '统计迭代',
    agentId: 'audit_iteration',
    agent: '审计迭代 · 只做分析',
    accent: '#0ea5e9',
    important: '散点/热力/溯源 · 六维指标 · 模块集成测试 · 策略反写 L1。',
    constraint: '只读分析 · 不替代 L4 卷宗',
    action: 'l5Dashboard',
    extras: [{ label: '五层架构画布', path: '/canvas', icon: 'Grid' }],
    items: ['3σ/IQR 离群', '时段热力矩阵', 'Span 根因', 'L1–L5 集成测试'],
  },
]

export const SIDEBAR_ACTIONS = {
  l1PlanMode: { label: '进入 · 计划模式对话', layer: 'L1', icon: 'ChatDotRound' },
  l2Safety: { label: '打开 · L2 防护沙箱', layer: 'L2', icon: 'Lock' },
  l3ExecuteMode: { label: '进入 · 执行模式对话', layer: 'L3', icon: 'Promotion' },
  l4Trace: { label: '打开 · L4 Trace 卷宗', layer: 'L4', icon: 'Share' },
  l5Dashboard: { label: '打开 · L5 链路量化', layer: 'L5', icon: 'TrendCharts' },
  gateExecute: { label: '切换执行模式', layer: 'GATE', icon: 'ArrowRight' },
}

/** 侧栏主线状态灯顺序（含 GATE） */
export const SPINE_ORDER = ['L1', 'L2', 'GATE', 'L3', 'L4', 'L5']

/** 定义封装 → 五层 → 数学模型（答辩导引） */
export const ENCAPSULATION_STACK = [
  {
    id: 'DEF',
    title: '定义封装',
    desc: 'MCP 原子工具 + Skill Flow + workflow_manifest.json',
    items: ['四工具簇 metrics/logs/repair/dispatch', 'L2 Skill 封装', 'HTN 0-1 路径'],
  },
  {
    id: 'PIPE',
    title: '五层流水线',
    desc: 'L1 分析 → L2 防护 → L3 执行 → L4 卷宗 → L5 量化',
    items: ['三 Agent 协同', '层间门禁', 'trace_id 全链路'],
  },
  {
    id: 'MATH',
    title: '数学模型',
    desc: 'L1 DBSCAN 边界 · L5 3σ/IQR/热力/聚类',
    items: ['纯 Python 无 sklearn', '策略反写 L1', '集成测试矩阵'],
  },
]

export const TOOL_CLUSTERS = {
  metrics: ['get_system_health', 'query_security_scan', 'list_processes', 'check_exposed_ports'],
  logs: ['get_audit_log', 'generate_security_report'],
  repair: ['run_full_security_check', 'run_terminal_command'],
  dispatch: ['run_autonomous_mission', 'start_monitor', 'stop_monitor'],
}

export const MATH_MODEL_CATALOG = [
  { id: 'l1_dbscan', layer: 'L1', name: '边界 DBSCAN-2D', tag: 'severity×confidence' },
  { id: 'l3_htn', layer: 'L3', name: 'HTN 0-1 路径', tag: 'metrics→logs→repair→dispatch' },
  { id: 'l5_3sigma', layer: 'L5', name: '散点 3σ+IQR', tag: '单点偶发离群' },
  { id: 'l5_heat', layer: 'L5', name: '热力 weighted_density', tag: '时段/集群故障' },
  { id: 'l5_dbscan', layer: 'L5', name: '链路 DBSCAN-2D', tag: '成片异常补充' },
]
