/** API 基址：生产与同源用 /api；开发由 vite proxy 转发 */
export function getApiBase() {
  if (typeof window !== 'undefined' && window.__SECURITY_AGENT_API__) {
    return String(window.__SECURITY_AGENT_API__).replace(/\/$/, '')
  }
  const env = import.meta.env.VITE_API_BASE
  if (env) return String(env).replace(/\/$/, '')
  return '/api'
}

export function getWsChatUrl() {
  const base = getApiBase()
  if (base.startsWith('http')) {
    const u = new URL(base)
    const proto = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${u.host}${u.pathname.replace(/\/$/, '')}/agent/ws/chat`
  }
  const proto = typeof location !== 'undefined' && location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = typeof location !== 'undefined' ? location.host : '127.0.0.1:8900'
  return `${proto}//${host}/api/agent/ws/chat`
}
