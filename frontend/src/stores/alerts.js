import { defineStore } from 'pinia'
import api from '../api'

let pollTimerId = null

export const useAlertsStore = defineStore('alerts', {
  state: () => ({
    items: [],
    recent: [],
    unreadCount: 0,
    total: 0,
    loading: false,
    lastFetchedAt: 0,
    error: null,
  }),
  getters: {
    unacknowledged: (s) => s.items.filter(a => !a.acknowledged),
  },
  actions: {
    async fetchAlerts(params = {}) {
      this.loading = true
      this.error = null
      try {
        const res = await api.get('/alerts/', { params })
        this.items = res.alerts || []
        this.total = res.total ?? this.items.length
        this.lastFetchedAt = Date.now()
      } catch (e) {
        this.error = e.response?.status || e.code || 'unknown'
      } finally {
        this.loading = false
      }
    },
    async fetchRecent(limit = 5) {
      try {
        const res = await api.get('/alerts/', { params: { limit } })
        this.recent = res.alerts || []
        await this.fetchUnreadCount()
      } catch {
        this.recent = []
        this.unreadCount = 0
      }
    },
    async fetchUnreadCount() {
      try {
        const res = await api.get('/alerts/unread-count')
        this.unreadCount = res.count || 0
      } catch {
        this.unreadCount = 0
      }
    },
    async acknowledge(alertId) {
      await api.post(`/alerts/${alertId}/acknowledge`)
      // 使用 immutable 更新代替手动 patch
      this.items = this.items.map(a =>
        (a.id || a.alert_id) === alertId ? { ...a, acknowledged: true } : a
      )
      this.recent = this.recent.map(a =>
        (a.id || a.alert_id) === alertId ? { ...a, acknowledged: true } : a
      )
      await this.fetchUnreadCount()
    },
    startPolling(intervalMs = 10000) {
      this.stopPolling()
      this.fetchRecent()
      pollTimerId = setInterval(() => this.fetchRecent(), intervalMs)
    },
    stopPolling() {
      if (pollTimerId) {
        clearInterval(pollTimerId)
        pollTimerId = null
      }
    },
  },
})
