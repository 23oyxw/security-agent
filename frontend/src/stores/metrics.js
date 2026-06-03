import { defineStore } from 'pinia'
import api from '../api'

export const useMetricsStore = defineStore('metrics', {
  state: () => ({
    cpuPercent: 0,
    memoryPercent: 0,
    diskPercent: 0,
    raw: {},
    loading: false,
  }),
  getters: {
    systemHealthy: (s) => s.cpuPercent < 80 && s.memoryPercent < 85,
  },
  actions: {
    async fetchMetrics() {
      this.loading = true
      try {
        const res = await api.get('/perception/metrics')
        this.raw = res || {}
        this.cpuPercent = Math.round(res.cpu_percent || 0)
        this.memoryPercent = Math.round(res.memory_percent || 0)
        this.diskPercent = Math.round(res.disk_percent || 0)
      } catch {
        this.raw = {}
      } finally {
        this.loading = false
      }
    },
  },
})
