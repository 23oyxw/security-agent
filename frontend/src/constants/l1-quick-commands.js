/** L1 运维快捷指令 — 智能助手计划模式 SSOT */
export const L1_CMD_CATEGORIES = [
  { id: 'situation', label: '态势感知', icon: 'Monitor' },
  { id: 'security', label: '安全巡检', icon: 'Lock' },
  { id: 'diagnose', label: '故障诊断', icon: 'Warning' },
  { id: 'capacity', label: '资源容量', icon: 'Coin' },
  { id: 'network', label: '网络链路', icon: 'Connection' },
]

export const L1_QUICK_COMMANDS = [
  {
    id: 'health',
    category: 'situation',
    label: '系统健康总览',
    hint: 'L1 三感知 · 静态之眼 8 维',
    prompt: '查看当前系统健康状态，汇总 CPU/内存/磁盘/进程/端口关键指标',
    cluster: 'metrics',
  },
  {
    id: 'ports',
    category: 'situation',
    label: '开放端口审计',
    hint: '边界感知 · 只读分析',
    prompt: '列出异常开放端口与监听进程，标注高危服务',
    cluster: 'logs',
  },
  {
    id: 'scan',
    category: 'security',
    label: '安全扫描报告',
    hint: '抗性边界 + 知识库 Playbook',
    prompt: '执行安全扫描并生成结构化报告，标注高危项与修复建议',
    cluster: 'repair',
  },
  {
    id: 'suid',
    category: 'security',
    label: 'SUID 异常排查',
    hint: '边界命中预检',
    prompt: '排查系统中可疑 SUID 文件与权限跃迁风险',
    cluster: 'repair',
  },
  {
    id: 'disk-mem',
    category: 'diagnose',
    label: '磁盘内存告警',
    hint: '静态感知 + 趋势',
    prompt: '分析磁盘与内存告警根因，给出可执行处置步骤（先 L1 计划）',
    cluster: 'metrics',
  },
  {
    id: 'proc',
    category: 'diagnose',
    label: '异常进程分析',
    hint: '进程簇 + 日志关联',
    prompt: '列出 CPU/内存占用异常的进程并关联最近系统日志',
    cluster: 'logs',
  },
  {
    id: 'load',
    category: 'capacity',
    label: '负载与调度',
    hint: 'HTN 调度簇',
    prompt: '评估当前负载与调度利用率，识别瓶颈资源',
    cluster: 'schedule',
  },
  {
    id: 'net',
    category: 'network',
    label: '网络链路诊断',
    hint: '静态之眼 · 网络维',
    prompt: '诊断网络连接异常、丢包与高延迟链路',
    cluster: 'logs',
  },
]

export function groupL1Commands(commands = L1_QUICK_COMMANDS) {
  const map = Object.fromEntries(L1_CMD_CATEGORIES.map(c => [c.id, { ...c, items: [] }]))
  for (const cmd of commands) {
    if (map[cmd.category]) map[cmd.category].items.push(cmd)
  }
  return L1_CMD_CATEGORIES.map(c => map[c.id]).filter(g => g.items.length)
}
