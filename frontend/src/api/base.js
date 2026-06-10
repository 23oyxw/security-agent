/**
 * @module api/base
 * API 基址与 WebSocket URL 配置
 */

/**
 * 获取 API 基址
 * 优先级: window.__SECURITY_AGENT_API__ > VITE_API_BASE > /api
 * @returns {string} API 基址 (无末尾斜杠)
 */
export function getApiBase() {
  if (typeof window !== 'undefined' && window.__SECURITY_AGENT_API__) {
    return String(window.__SECURITY_AGENT_API__).replace(/\/$/, '')
  }
  const env = import.meta.env.VITE_API_BASE
  if (env) return String(env).replace(/\/$/, '')
  return '/api'
}

/**
 * 获取 Agent WebSocket 对话 URL
 * 自动检测 http/https 并切换 ws/wss
 * @returns {string} WebSocket URL (ws:// 或 wss://)
 */
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
