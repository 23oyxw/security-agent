import axios from 'axios'
import { getApiBase } from './base'
import router from '../router'
import { useUserStore } from '../stores/user'

const api = axios.create({ baseURL: getApiBase(), timeout: 120000 })

api.interceptors.request.use(config => {
  // 从 Pinia store 读取 token（与持久化插件同步）
  const store = useUserStore()
  const token = store.token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res.data,
  async err => {
    const { config, response } = err

    const status = response?.status

    // 401/403 → 清除认证状态，跳转登录
    if (status === 401 || status === 403) {
      const store = useUserStore()
      store.logout()
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
      return Promise.reject(err)
    }

    // 4xx 客户端错误不重试
    if (status !== undefined && status < 500) {
      return Promise.reject(err)
    }

    // 无 config 则无法重试
    if (!config) return Promise.reject(err)

    // 5xx / 网络错误 → 最多重试 2 次（指数退避）
    const retryCount = config._retryCount || 0
    if (retryCount < 2 && config.method !== 'post') {
      config._retryCount = retryCount + 1
      const delay = Math.pow(2, retryCount) * 500
      await new Promise(r => setTimeout(r, delay))
      return api(config)
    }

    return Promise.reject(err)
  }
)

export default api
