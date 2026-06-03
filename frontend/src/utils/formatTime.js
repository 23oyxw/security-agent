/**
 * 统一北京时间展示（与后端 timeutil 一致）
 */

export function formatBeijingTime(value, { withLabel = false, fallback = '—', assumeUtcNaive = false } = {}) {
  if (value == null || value === '') return fallback
  let s = String(value).trim()
  // 已是展示格式则直接返回
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s) && !s.includes('T')) {
    return withLabel ? `${s} (北京时间)` : s
  }
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s) && assumeUtcNaive) {
    s = s.replace(' ', 'T') + 'Z'
  } else if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s)) {
    s = s.replace(' ', 'T') + '+08:00'
  }
  if (/^\d{4}-\d{2}-\d{2}T/.test(s) && !/[+-]\d{2}:?\d{2}$/.test(s) && !s.endsWith('Z')) {
    s = assumeUtcNaive ? s + 'Z' : s + '+08:00'
  }
  if (s.endsWith('Z')) s = s.slice(0, -1) + '+00:00'
  // +08:00 → +0800 兼容旧浏览器
  s = s.replace(/([+-]\d{2}):(\d{2})$/, '$1$2')
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 19) || fallback
  const text = d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  return withLabel ? `${text} (北京时间)` : text
}

export function formatRelativeBeijing(value, { assumeUtcNaive = false } = {}) {
  const base = formatBeijingTime(value, { fallback: '', assumeUtcNaive })
  if (!base) return '—'
  let s = String(value).trim()
  if (s.endsWith('Z')) s = s.slice(0, -1) + '+00:00'
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s)) {
    s = s.replace(' ', 'T') + (assumeUtcNaive ? 'Z' : '+08:00')
  }
  s = s.replace(/([+-]\d{2}):(\d{2})$/, '$1$2')
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return base
  const diff = Date.now() - d.getTime()
  if (diff < 120000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return base
}
