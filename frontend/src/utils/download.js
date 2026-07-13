/** 触发浏览器下载本地文本/Blob */
export function downloadBlob(content, filename, mime = 'text/plain;charset=utf-8') {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mime })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

import { getAuthToken } from './auth-token'

export function authHeaders() {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** 带鉴权 GET，返回 Response（调用方检查 ok） */
export async function fetchWithAuth(url) {
  return fetch(url, { headers: authHeaders() })
}

export function basename(path) {
  if (!path) return ''
  return String(path).replace(/\\/g, '/').split('/').pop() || ''
}
