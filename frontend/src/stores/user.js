import { defineStore } from 'pinia'
import api from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: '',
    role: '',
    isLoggedIn: !!localStorage.getItem('token'),
  }),
  actions: {
    async login(username, password) {
      const res = await api.post('/auth/login', { username, password })
      this.token = res.access_token
      this.username = res.username
      this.role = res.role
      this.isLoggedIn = true
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('user', JSON.stringify({ username: res.username, role: res.role }))
      return res
    },
    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      this.isLoggedIn = false
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    async fetchMe() {
      const res = await api.get('/auth/me')
      this.username = res.username
      this.role = res.role
      localStorage.setItem('user', JSON.stringify({ username: res.username, role: res.role }))
    },
    hydrateFromStorage() {
      const u = localStorage.getItem('user')
      if (u) {
        try {
          const parsed = JSON.parse(u)
          this.username = parsed.username || ''
          this.role = parsed.role || ''
        } catch { /* ignore */ }
      }
    },
  },
})