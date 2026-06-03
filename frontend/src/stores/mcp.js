import { defineStore } from 'pinia'
import api from '../api'

export const useMcpStore = defineStore('mcp', {
  state: () => ({
    servers: [],
    tools: [],
    loading: false,
    lastReloadAt: 0,
  }),
  getters: {
    runningCount: (s) => s.servers.filter(x => x.status === 'running').length,
  },
  actions: {
    async fetchServers() {
      this.loading = true
      try {
        const res = await api.get('/mcp/servers')
        this.servers = res.servers || []
      } finally {
        this.loading = false
      }
    },
    async fetchTools() {
      const res = await api.get('/mcp/tools')
      this.tools = (res.tools || []).map(t => ({
        name: t.name,
        description: t.description || '',
        server_name: t.server_name || t.server || '—',
      }))
    },
    async refresh() {
      await Promise.all([this.fetchServers(), this.fetchTools()])
    },
    async reload() {
      this.loading = true
      try {
        const res = await api.post('/mcp/reload')
        this.lastReloadAt = Date.now()
        await this.refresh()
        return res
      } finally {
        this.loading = false
      }
    },
  },
})
