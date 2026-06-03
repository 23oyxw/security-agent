import { defineStore } from 'pinia'
import api from '../api'

export const useAlertsStore = defineStore('alerts', {
  state: () => ({
    items: [],
    recent: [],
    unreadCount: 0,
    total: 0,
    loading: false,
    lastFetchedAt: 0,
  }),
  getters: {
    unacknowledged: (s) => s.items.filter(a => !a.acknowledged),
  },
  actions: {
    async fetchAlerts(params = {}) {
      this.loading = true
      try {
        const res = await api.get('/alerts/', { params })
        this.items = res.alerts || []
        this.total = res.total ?? this.items.length
        this.lastFetchedAt = Date.now()
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
      const patch = (a) => {
        if ((a.id || a.alert_id) === alertId) a.acknowledged = true
      }
      this.items.forEach(patch)
      this.recent.forEach(patch)
      await this.fetchUnreadCount()
    },
  },
})
