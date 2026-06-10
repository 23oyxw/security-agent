<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- 顶部装饰线 -->
    <div class="sidebar-accent-line"></div>

    <div class="sidebar-header" @click="$emit('toggle')">
      <div class="brand-mark">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect width="28" height="28" rx="6" fill="url(#brand-gradient)"/>
          <path d="M8 14L12 18L20 10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <defs>
            <linearGradient id="brand-gradient" x1="0" y1="0" x2="28" y2="28">
              <stop offset="0%" stop-color="#4f6ef7"/>
              <stop offset="100%" stop-color="#6366f1"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <transition name="fade">
        <span v-if="!collapsed" class="brand-text">安全运维控制台</span>
      </transition>
    </div>

    <nav class="sidebar-nav">
      <template v-for="group in menuGroups" :key="group.label">
        <div v-if="!collapsed" class="nav-group-label">{{ group.label }}</div>
        <div
          v-for="item in group.items"
          :key="item.path"
          class="nav-item"
          :class="{ active: current === item.path }"
          @click="$emit('navigate', item.path)"
          @mousemove="trackMouse"
        >
          <div class="nav-icon">
            <el-icon :size="18"><component :is="item.icon" /></el-icon>
          </div>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          </transition>
          <transition name="fade">
            <span v-if="!collapsed && item.badge && item.badge() > 0" class="nav-badge">{{ item.badge() }}</span>
          </transition>
        </div>
      </template>
    </nav>

    <!-- 简化的 Sidebar Footer：仅保留状态指示灯 -->
    <div v-if="!collapsed" class="sidebar-footer">
      <div class="status-indicator" :class="statusClass">
        <span class="status-dot"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>
    </div>
    <div v-else class="sidebar-footer-collapsed">
      <div class="status-indicator" :class="statusClass">
        <span class="status-dot"></span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMetricsStore } from '../../stores/metrics'
import { useAlertsStore } from '../../stores/alerts'

defineProps({
  collapsed: Boolean,
})

defineEmits(['toggle', 'navigate'])

const route = useRoute()
const metricsStore = useMetricsStore()
const alertsStore = useAlertsStore()

const menuGroups = [
  {
    label: '总览',
    items: [
      { path: '/', icon: 'Odometer', label: '仪表盘' },
      { path: '/agent', icon: 'ChatDotRound', label: '智能助手' },
      { path: '/canvas', icon: 'Grid', label: '无限画布' },
    ],
  },
  {
    label: '安全管控',
    items: [
      { path: '/safety', icon: 'Lock', label: '安全执行' },
      { path: '/alerts', icon: 'Bell', label: '告警管理', badge: () => alertsStore.unreadCount },
    ],
  },
  {
    label: '能力与审计',
    items: [
      { path: '/mcp', icon: 'Connection', label: 'MCP 能力中心' },
      { path: '/trace', icon: 'Share', label: 'Trace 溯源' },
    ],
  },
  {
    label: '知识',
    items: [
      { path: '/knowledge', icon: 'Reading', label: '知识库' },
      { path: '/guide', icon: 'Document', label: '技术导引' },
    ],
  },
]

const allItems = computed(() => menuGroups.flatMap(g => g.items))
const current = computed(() => (route.path === '/dashboard' ? '/' : route.path))

// 状态指示灯：仅显示健康/警告/危险，不重复具体数值
const statusClass = computed(() => {
  const cpu = metricsStore.cpuPercent || 0
  const mem = metricsStore.memoryPercent || 0
  const alerts = alertsStore.unreadCount || 0
  if (cpu > 90 || mem > 90 || alerts > 10) return 'danger'
  if (cpu > 70 || mem > 70 || alerts > 0) return 'warning'
  return 'healthy'
})

const statusText = computed(() => {
  if (statusClass.value === 'healthy') return '运行中'
  if (statusClass.value === 'warning') return '高负载'
  return '严重告警'
})

// Nav item 鼠标追踪（光效）
const mouseX = ref('50%')
const mouseY = ref('50%')

function trackMouse(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  mouseX.value = `${((e.clientX - rect.left) / rect.width) * 100}%`
  mouseY.value = `${((e.clientY - rect.top) / rect.height) * 100}%`
  e.currentTarget.style.setProperty('--mouse-x', mouseX.value)
  e.currentTarget.style.setProperty('--mouse-y', mouseY.value)
}
</script>

<style scoped>
/* ---- 侧边栏 ---- */
.sidebar {
  width: var(--sidebar-width);
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);
  transition: width var(--duration-slow) var(--ease-out);
  position: relative;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

/* 顶部装饰线 */
.sidebar-accent-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #4f6ef7 0%, #6366f1 50%, #818cf8 100%);
  opacity: 0.8;
  z-index: 1;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-4);
  height: 60px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  user-select: none;
  position: relative;
  z-index: 1;
}

.brand-mark {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--duration-normal) var(--ease-spring);
}

.sidebar-header:hover .brand-mark {
  transform: rotate(-5deg) scale(1.05);
}

.brand-text {
  color: #fff;
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
}

/* ---- 导航 ---- */
.sidebar-nav {
  flex: 1;
  padding: var(--space-2) 0;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  margin: 1px var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  color: rgba(255, 255, 255, 0.65);
  font-size: var(--text-sm);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  white-space: nowrap;
  overflow: hidden;
}

/* 悬浮光效 */
.nav-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.08) 0%,
    transparent 60%
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  border-radius: inherit;
  pointer-events: none;
}

.nav-item:hover::before {
  opacity: 1;
}

.nav-item:hover {
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  color: #fff;
  background: linear-gradient(90deg, rgba(79, 110, 247, 0.2) 0%, transparent 100%);
}

/* 激活指示器：左侧渐变条 */
.nav-item.active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: linear-gradient(180deg, #4f6ef7 0%, #6366f1 100%);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  animation: slide-in-left 0.3s ease-out;
}

@keyframes slide-in-left {
  from { height: 0; opacity: 0; }
  to { height: 60%; opacity: 1; }
}

.nav-group-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.25);
  padding: var(--space-3) var(--space-4) var(--space-1);
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  background: var(--color-danger);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 0 5px;
  height: 16px;
  line-height: 16px;
  border-radius: var(--radius-full);
  min-width: 16px;
  text-align: center;
}

/* ---- 侧边栏底部（简化版） ---- */
.sidebar-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-footer-collapsed {
  padding: var(--space-2);
  display: flex;
  justify-content: center;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.5);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

/* 健康状态：绿色 + 脉冲环 */
.status-indicator.healthy .status-dot {
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success);
}

.status-indicator.healthy .status-dot::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: var(--color-success);
  opacity: 0;
  animation: pulse-ring 2s ease-in-out infinite;
}

/* 警告状态：黄色 + 加速脉冲 */
.status-indicator.warning .status-dot {
  background: var(--color-warning);
  box-shadow: 0 0 6px var(--color-warning);
}

.status-indicator.warning .status-dot::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: var(--color-warning);
  opacity: 0;
  animation: pulse-ring 1.2s ease-in-out infinite;
}

/* 危险状态：红色 + 快速脉冲 */
.status-indicator.danger .status-dot {
  background: var(--color-danger);
  box-shadow: 0 0 8px var(--color-danger);
}

.status-indicator.danger .status-dot::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: var(--color-danger);
  opacity: 0;
  animation: pulse-ring 0.8s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 0.4; }
  50% { transform: scale(1.8); opacity: 0; }
}

/* ---- 过渡 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
