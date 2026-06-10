<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- 顶部装饰线 -->
    <div class="sidebar-accent"></div>

    <!-- 品牌头部 -->
    <div class="sidebar-header" @click="$emit('toggle')">
      <div class="brand-mark">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect width="28" height="28" rx="6" fill="url(#sg-brand)"/>
          <path d="M8 14L12 18L20 10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <defs>
            <linearGradient id="sg-brand" x1="0" y1="0" x2="28" y2="28">
              <stop offset="0%" stop-color="var(--color-primary-600, #2563eb)"/>
              <stop offset="100%" stop-color="var(--color-primary-500, #3b82f6)"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <transition name="fade">
        <span v-if="!collapsed" class="brand-text">安全运维控制台</span>
      </transition>
    </div>

    <!-- 导航 -->
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
          <span class="nav-icon">
            <el-icon :size="18"><component :is="item.icon" /></el-icon>
          </span>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          </transition>
          <transition name="fade">
            <span v-if="!collapsed && item.badge && item.badge() > 0" class="nav-badge">{{ item.badge() }}</span>
          </transition>
        </div>
      </template>
    </nav>

    <!-- 底部状态 -->
    <div v-if="!collapsed" class="sidebar-footer">
      <div class="status-row" :class="statusClass">
        <span class="status-dot"></span>
        <span class="status-label">{{ statusText }}</span>
      </div>
    </div>
    <div v-else class="sidebar-footer sidebar-footer--mini">
      <div class="status-row status-row--mini" :class="statusClass">
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

defineProps({ collapsed: Boolean })
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

/* 状态指示 */
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

/* 鼠标追踪光效 */
const mouseX = ref('50%')
const mouseY = ref('50%')
function trackMouse(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  e.currentTarget.style.setProperty('--mouse-x', `${x}%`)
  e.currentTarget.style.setProperty('--mouse-y', `${y}%`)
}
</script>

<style scoped>
/* ============================================================
   Sidebar — 侧边栏 (Professional Refinement)
   使用 design tokens，深色主题，专业 B2B 风格
   ============================================================ */

.sidebar {
  width: var(--sidebar-width);
  background: var(--gradient-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-lg);
  transition: width var(--duration-slow) var(--ease-out);
  position: relative;
}

.sidebar.collapsed { width: var(--sidebar-collapsed-width); }

/* ---- 自定义滚动条 ---- */
.sidebar-nav::-webkit-scrollbar { width: 3px; }
.sidebar-nav::-webkit-scrollbar-track { background: transparent; }
.sidebar-nav::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: var(--radius-full); }
.sidebar-nav::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

/* ---- 顶部装饰线 ---- */
.sidebar-accent {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--color-primary-600) 0%, var(--color-primary-500) 50%, var(--color-primary-400) 100%);
  opacity: 0.85;
  z-index: 1;
}

/* ---- Header ---- */
.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
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
  transition: transform var(--duration-normal) var(--ease-standard);
}

/* 移除过于活泼的旋转动画 — B2B 专业风格 */
.sidebar-header:hover .brand-mark {
  transform: scale(1.06);
}

.brand-text {
  color: var(--color-text-inverse);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
}

/* ---- 导航区 ---- */
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
  margin: 2px var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--text-sm);
  transition:
    color var(--duration-fast) var(--ease-out),
    background var(--duration-fast) var(--ease-out);
  position: relative;
  white-space: nowrap;
  overflow: hidden;
}

/* 鼠标追踪径向光效 */
.nav-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.07) 0%,
    transparent 60%
  );
  opacity: 0;
  transition: opacity 0.25s ease;
  border-radius: inherit;
  pointer-events: none;
}
.nav-item:hover::before { opacity: 1; }

.nav-item:hover {
  color: rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.05);
}

/* 激活状态 */
.nav-item.active {
  color: #fff;
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.22) 0%, transparent 100%);
}

/* 左侧激活指示条 — GPU 加速 scaleY */
.nav-item.active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 15%;
  bottom: 15%;
  width: 3px;
  background: linear-gradient(180deg, var(--color-primary-400) 0%, var(--color-primary-600) 100%);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  transform-origin: center;
  animation: nav-indicator-in 0.25s var(--ease-out);
}

/* 分组标签 — 使用 token */
.nav-group-label {
  font-size: var(--text-2xs);
  font-weight: var(--weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(255, 255, 255, 0.28);
  padding: var(--space-3) var(--space-5) var(--space-1);
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
}
.nav-label { flex: 1; }

/* 徽章 */
.nav-badge {
  background: var(--color-danger);
  color: #fff;
  font-size: 10px;
  font-weight: var(--weight-semibold);
  padding: 0 5px;
  height: 16px;
  line-height: 16px;
  border-radius: var(--radius-full);
  min-width: 16px;
  text-align: center;
}

/* ---- Footer 状态栏 ---- */
.sidebar-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.sidebar-footer--mini {
  padding: var(--space-2);
  display: flex;
  justify-content: center;
}

.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.45);
}
.status-row--mini { gap: 0; }

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

.status-label { line-height: 1; }

/* 健康态 */
.status-row.healthy .status-dot {
  background: var(--color-success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}
.status-row.healthy .status-dot::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: var(--color-success);
  opacity: 0;
  animation: pulse-ring 2s ease-in-out infinite;
}

/* 警告态 */
.status-row.warning .status-dot {
  background: var(--color-warning);
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}
.status-row.warning .status-dot::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: var(--color-warning);
  opacity: 0;
  animation: pulse-ring 1.2s ease-in-out infinite;
}

/* 危险态 */
.status-row.danger .status-dot {
  background: var(--color-danger);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}
.status-row.danger .status-dot::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: var(--color-danger);
  opacity: 0;
  animation: pulse-ring 0.8s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 0.35; }
  50% { transform: scale(1.7); opacity: 0; }
}

/* ---- 过渡动画 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to { opacity: 0; }
</style>
