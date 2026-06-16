import { defineStore } from 'pinia'
import api from '../api'

export const useBackendStore = defineStore('backend', {
  state: () => ({
    online: true,
    version: '',
    lastCheck: 0,
    error: '',
  }),
  actions: {
    async ping() {
      try {
        const res = await api.get('health')
        this.online = res?.status === 'ok'
        this.version = res?.version || ''
        this.error = ''
      } catch (e) {
        this.online = false
        this.version = ''
        this.error = e.code === 'ERR_NETWORK' ? 'network' : String(e.response?.status || 'error')
      }
      this.lastCheck = Date.now()
    },
  },
})
