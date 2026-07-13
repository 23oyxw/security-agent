/**
 * Agent WebSocket — 优先实时通道，失败时由调用方回退 REST。
 */
import { ref, onUnmounted } from 'vue'
import { getWsChatUrl } from '../api/base'
import { getAuthToken } from '../utils/auth-token'

export function useAgentWs() {
  const transport = ref('rest')
  const wsReady = ref(false)
  let socket = null
  let pendingChat = null

  function connect() {
    const token = getAuthToken()
    if (!token || socket) return

    try {
      socket = new WebSocket(getWsChatUrl())
    } catch {
      return
    }

    socket.onopen = () => {
      transport.value = 'ws'
    }

    socket.onmessage = (ev) => {
      let data
      try {
        data = JSON.parse(ev.data)
      } catch {
        return
      }
      const type = data.type

      if (type === 'system' && data.session_id) {
        return
      }
      if (type === 'ping') {
        socket?.send(JSON.stringify({ type: 'pong' }))
        return
      }
      if (type === 'auth_ok') {
        wsReady.value = true
        return
      }
      if (type === 'auth_error') {
        wsReady.value = false
        return
      }
      if (type === 'typing') return

      const waiter = pendingChat
      if (!waiter) return

      if (type === 'response') {
        pendingChat = null
        waiter.resolve({
          reply: data.content || '',
          tools_used: data.tools_used || [],
          risk_level: data.risk_level || 'low',
          trace_id: data.trace_id,
          degradation_level: data.degradation_level || 'S0',
          fallback_used: Boolean(data.fallback_used),
          token_usage: data.token_usage || {},
          cost_tokens: data.cost_tokens ?? (data.token_usage?.total_tokens || 0),
          cost_estimate: data.cost_estimate || {},
          context_usage: data.context_usage || {},
          execution_meta: data.execution_meta || {},
          plan_summary: data.plan_summary || {},
          model_used: data.model_used || '',
          skill_flow: data.skill_flow || '',
        })
      } else if (type === 'error') {
        pendingChat = null
        waiter.reject(new Error(data.content || 'WebSocket 错误'))
      }
    }

    socket.onclose = () => {
      transport.value = 'rest'
      wsReady.value = false
      socket = null
      if (pendingChat) {
        pendingChat.reject(new Error('WebSocket 已断开'))
        pendingChat = null
      }
    }

    socket.onerror = () => {
      wsReady.value = false
    }

    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'auth', token }))
    }, { once: true })
  }

  function disconnect() {
    if (socket) {
      socket.close()
      socket = null
    }
    wsReady.value = false
    transport.value = 'rest'
  }

  async function waitReady(maxMs = 4000) {
    const deadline = Date.now() + maxMs
    while (Date.now() < deadline) {
      if (socket?.readyState === WebSocket.OPEN && wsReady.value) return true
      await new Promise((r) => setTimeout(r, 80))
    }
    return false
  }

  async function chatViaWs(message, timeoutMs = 120000) {
    if (!(await waitReady())) {
      throw new Error('WebSocket 未就绪')
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (pendingChat?.resolve === resolve) pendingChat = null
        reject(new Error('WebSocket 超时'))
      }, timeoutMs)
      pendingChat = {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      }
      socket.send(JSON.stringify({ type: 'chat', message }))
    })
  }

  onUnmounted(disconnect)

  return { transport, wsReady, connect, disconnect, chatViaWs }
}
