/**
 * L1 静态环境感知（眼）— 8 维态势轴
 * 对齐 l1_triple_perception.run_static_environment_eye · eye_axes
 */

export const STATIC_EYE_CONSTRAINT = '只读监听 · 零工具 · 零执行 · Read-only Eye'

export const STATIC_EYE_AXES = [
  {
    id: 'network',
    cn: '网络',
    en: 'Network',
    dimKey: 'network',
    icon: 'Connection',
    hint: '连接数 · 流量 IO',
    format: (ctx) => ctx.networkLabel || '—',
    alert: (ctx) => false,
  },
  {
    id: 'ports',
    cn: '端口',
    en: 'Ports',
    dimKey: 'ports',
    icon: 'Monitor',
    hint: '监听端口 Top',
    format: (ctx) => ctx.portsLabel ?? '—',
    alert: (ctx) => (ctx.openPorts || 0) > 200,
  },
  {
    id: 'cpu',
    cn: 'CPU',
    en: 'CPU',
    dimKey: 'cpu',
    icon: 'Cpu',
    hint: '处理器占用',
    format: (ctx) => (ctx.cpu != null ? `${ctx.cpu}%` : '—'),
    alert: (ctx) => (ctx.cpu || 0) > 85,
  },
  {
    id: 'memory',
    cn: '内存',
    en: 'Memory',
    dimKey: 'memory',
    icon: 'Coin',
    hint: 'RAM 使用率',
    format: (ctx) => (ctx.memory != null ? `${ctx.memory}%` : '—'),
    alert: (ctx) => (ctx.memory || 0) > 90,
  },
  {
    id: 'disk',
    cn: '磁盘',
    en: 'Disk',
    dimKey: 'disk',
    icon: 'FolderOpened',
    hint: '根分区占用',
    format: (ctx) => (ctx.disk != null ? `${ctx.disk}%` : '—'),
    alert: (ctx) => (ctx.disk || 0) > 85,
  },
  {
    id: 'link',
    cn: '链路',
    en: 'Link',
    dimKey: 'link',
    icon: 'Share',
    hint: 'Load · Uptime',
    format: (ctx) => ctx.linkLabel || '—',
    alert: (ctx) => (ctx.load1 || 0) > 8,
  },
  {
    id: 'permissions',
    cn: '权限',
    en: 'Permissions',
    dimKey: 'permissions',
    icon: 'Key',
    hint: '权限标志 · 探针',
    format: (ctx) => ctx.permissionsLabel || '—',
    alert: (ctx) => ctx.permissionRisk === true,
  },
  {
    id: 'health',
    cn: '状态',
    en: 'Status',
    dimKey: 'health',
    icon: 'CircleCheck',
    hint: '综合健康',
    format: (ctx) => ctx.healthLabel || '—',
    alert: (ctx) => ctx.healthOk === false,
  },
]

/** 从 metrics + context 快照合并为轴上下文 */
export function buildEyeContext(metrics = {}, snapshot = {}, extras = {}) {
  const summary = snapshot.summary || snapshot || {}
  const load = metrics.load_avg || summary.load_avg || []
  const net = metrics.network_io || summary.network_io || {}
  const sent = net.bytes_sent ?? net.sent
  const recv = net.bytes_recv ?? net.recv
  const openPorts = summary.open_ports ?? summary.port_count ?? extras.portCount
  const healthRaw = summary.system_health ?? summary.health ?? metrics.system_health
  const healthOk = healthRaw === true || healthRaw === 'healthy' || healthRaw === 'ok'

  let networkLabel = '—'
  if (summary.connections != null) networkLabel = `${summary.connections} conn`
  else if (sent != null && recv != null) {
    networkLabel = `↑${formatBytes(sent)} ↓${formatBytes(recv)}`
  } else if (summary.network) networkLabel = String(summary.network)

  const load1 = load[0] ?? summary.load_1
  const uptime = metrics.uptime_seconds ?? summary.uptime_seconds
  let linkLabel = load1 != null ? `Load ${Number(load1).toFixed(2)}` : '—'
  if (uptime != null) linkLabel += ` · ${formatUptime(uptime)}`

  const perm = summary.permission_flags ?? summary.permissions
  let permissionsLabel = '—'
  if (Array.isArray(perm)) permissionsLabel = perm.length ? perm.join(', ') : '正常 Normal'
  else if (typeof perm === 'string') permissionsLabel = perm
  else if (perm === false || perm === true) permissionsLabel = perm ? '受限 Restricted' : '正常 Normal'

  return {
    cpu: metrics.cpu_percent ?? summary.cpu_percent ?? snapshot.cpu_percent,
    memory: metrics.memory_percent ?? summary.memory_percent,
    disk: metrics.disk_percent ?? summary.disk_percent,
    openPorts,
    portsLabel: openPorts != null ? `${openPorts} 监听` : '—',
    networkLabel,
    load1,
    linkLabel,
    permissionsLabel,
    permissionRisk: perm === true || (Array.isArray(perm) && perm.length > 0),
    healthOk,
    healthLabel: healthOk ? '正常 OK' : '异常 Alert',
    processCount: metrics.process_count ?? summary.process_count,
  }
}

function formatBytes(n) {
  const v = Number(n)
  if (!v) return '0B'
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}G`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  return `${v}B`
}

function formatUptime(sec) {
  const s = Math.floor(Number(sec) || 0)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return `${h}h${m}m`
}
