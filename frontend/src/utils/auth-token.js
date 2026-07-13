/** 读取登录 token — 与 user store / pinia persist 对齐 */
export function getAuthToken() {
  try {
    const raw = localStorage.getItem('security-agent-user')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.token) return parsed.token
    }
  } catch { /* ignore */ }
  return localStorage.getItem('token') || ''
}
