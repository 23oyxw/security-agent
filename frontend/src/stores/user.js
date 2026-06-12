import { defineStore } from 'pinia'
import api from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '',
    username: '',
    role: '',
    isLoggedIn: false,
  }),
  persist: {
    key: 'security-agent-user',
    paths: ['token', 'username', 'role', 'isLoggedIn'],
  },
  getters: {
    isAdmin: (state) => state.role === 'admin',
  },
  actions: {
    async login(username, password) {
      const res = await api.post('/auth/login', { username, password })
      this.token = res.access_token || ''
      this.username = res.username || username
      this.role = res.role || 'user'
      this.isLoggedIn = Boolean(this.token)
      if (!this.token) throw new Error('登录响应缺少 token')
      return res
    },
    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      this.isLoggedIn = false
      try {
        sessionStorage.removeItem('security-agent-auth-init')
      } catch { /* ignore */ }
    },
    async fetchMe() {
      const res = await api.get('/auth/me')
      this.username = res.username
      this.role = res.role
    },
    hydrateFromStorage() {
      // pinia-plugin-persistedstate 已自动同步，此方法保留兼容
    },
  },
})
