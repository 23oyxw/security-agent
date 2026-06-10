import { defineStore } from 'pinia'
import api from '../api'

let pollTimerId = null

export const useMetricsStore = defineStore('metrics', {
  state: () => ({
    cpuPercent: 0,
    memoryPercent: 0,
    diskPercent: 0,
    raw: {},
    loading: false,
    error: null,
  }),
  getters: {
    systemHealthy: (s) => s.cpuPercent < 80 && s.memoryPercent < 85,
  },
  actions: {
    async fetchMetrics() {
      this.loading = true
      this.error = null
      try {
        const res = await api.get('/perception/metrics')
        this.raw = res || {}
        this.cpuPercent = Math.round(res.cpu_percent || 0)
        this.memoryPercent = Math.round(res.memory_percent || 0)
        this.diskPercent = Math.round(res.disk_percent || 0)
      } catch (e) {
        this.error = e.response?.status || e.code || 'unknown'
        this.raw = {}
      } finally {
        this.loading = false
      }
    },
    startPolling(intervalMs = 5000) {
      this.stopPolling()
      this.fetchMetrics()
      pollTimerId = setInterval(() => this.fetchMetrics(), intervalMs)
    },
    stopPolling() {
      if (pollTimerId) {
        clearInterval(pollTimerId)
        pollTimerId = null
      }
    },
  },
})
