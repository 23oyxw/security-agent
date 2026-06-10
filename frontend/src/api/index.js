import axios from 'axios'
import { getApiBase } from './base'
import router from '../router'

const api = axios.create({ baseURL: getApiBase(), timeout: 120000 })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res.data,
  async err => {
    const { config, response } = err
    // 401 → SPA 软跳转登录（避免全页刷新丢失状态）
    if (response?.status === 401) {
      localStorage.removeItem('token')
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
      return Promise.reject(err)
    }
    // 5xx / 网络错误 → 最多重试 2 次（指数退避）
    const shouldRetry = !response || response.status >= 500
    const retryCount = config._retryCount || 0
    if (shouldRetry && retryCount < 2 && config.method !== 'post') {
      config._retryCount = retryCount + 1
      const delay = Math.pow(2, retryCount) * 500
      await new Promise(r => setTimeout(r, delay))
      return api(config)
    }
    return Promise.reject(err)
  }
)

export default api