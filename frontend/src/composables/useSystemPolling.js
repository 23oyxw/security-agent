/**
 * useSystemPolling — 系统状态轮询 Composable
 *
 * 职责：定时拉取 metrics + alerts 数据，自动管理生命周期
 * 解耦：从 MainLayout 中提取，Layout 组件不再承担数据获取职责
 *
 * @param {number} intervalMs - 轮询间隔（毫秒），默认 30000
 * @returns {{ poll: () => Promise<void> }} 手动触发轮询的方法
 */
import { onMounted, onUnmounted } from 'vue'
import { useMetricsStore } from '../stores/metrics'
import { useAlertsStore } from '../stores/alerts'

export function useSystemPolling(intervalMs = 30000) {
  const metricsStore = useMetricsStore()
  const alertsStore = useAlertsStore()
  let timer = null

  const poll = async () => {
    await Promise.allSettled([
      metricsStore.fetchMetrics(),
      alertsStore.fetchRecent(5),
      alertsStore.fetchUnreadCount(),
    ])
  }

  onMounted(async () => {
    await poll()
    timer = setInterval(poll, intervalMs)
  })

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })

  return { poll }
}
