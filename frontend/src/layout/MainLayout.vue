<template>
  <div class="app-shell">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed }">
      <div class="sidebar-header" @click="collapsed = !collapsed">
        <div class="brand-mark">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#4f6ef7"/>
            <path d="M8 14L12 18L20 10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
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
            @click="navigate(item.path)"
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

      <div v-if="!collapsed" class="sidebar-footer">
        <div class="status-indicator" :class="metricsStore.systemHealthy ? 'healthy' : 'warning'">
          <span class="status-dot"></span>
          <span class="status-text">{{ metricsStore.systemHealthy ? '系统正常' : '需要关注' }}</span>
        </div>
        <div class="sys-info">
          <div class="sys-info-row">
            <span class="sys-info-label">CPU</span>
            <span class="sys-info-value" :class="cpuStatus">{{ metricsStore.cpuPercent || 0 }}%</span>
          </div>
          <div class="sys-info-row">
            <span class="sys-info-label">内存</span>
            <span class="sys-info-value" :class="memStatus">{{ metricsStore.memoryPercent || 0 }}%</span>
          </div>
          <div class="sys-info-row">
            <span class="sys-info-label">告警</span>
            <span class="sys-info-value" :class="alertsStore.unreadCount > 0 ? 'warning' : ''">{{ alertsStore.unreadCount || 0 }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="main-area">
      <!-- 顶栏 -->
      <header class="topbar">
        <div class="topbar-left">
          <button class="collapse-trigger" @click="collapsed = !collapsed">
            <el-icon :size="18"><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageName }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="topbar-right">
          <div class="metrics-bar">
            <div class="metric" title="CPU 使用率">
              <el-icon :size="14"><Cpu /></el-icon>
              <span class="metric-value" :class="cpuStatus">{{ metricsStore.cpuPercent }}%</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric" title="内存使用率">
              <el-icon :size="14"><Coin /></el-icon>
              <span class="metric-value" :class="memStatus">{{ metricsStore.memoryPercent }}%</span>
            </div>
          </div>

          <el-dropdown trigger="click" @command="handleAlert" class="alert-dropdown">
            <button class="icon-btn">
              <el-badge :value="alertsStore.unreadCount" :hidden="alertsStore.unreadCount === 0" :max="99">
                <el-icon :size="18"><Bell /></el-icon>
              </el-badge>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="a in alertsStore.recent" :key="a.id" :command="a.id">
                  <div class="alert-item">
                    <el-tag :type="sevColor(a.level || a.severity)" size="small" effect="plain">{{ a.level || a.severity }}</el-tag>
                    <span class="alert-title">{{ a.title || a.message }}</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item v-if="!alertsStore.recent.length" disabled>暂无告警</el-dropdown-item>
                <el-dropdown-item divided command="view-all">
                  <el-button text type="primary" size="small" @click="$router.push('/alerts')">查看全部</el-button>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown trigger="click" class="user-dropdown">
            <button class="user-trigger">
              <div class="user-avatar">{{ (userStore.username || 'U')[0].toUpperCase() }}</div>
              <span class="user-name">{{ userStore.username }}</span>
              <span class="user-role" :class="userStore.role">{{ userStore.role }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>
                  <el-icon><User /></el-icon> {{ userStore.username }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 内容区 -->
      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="slide-up" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useAlertsStore } from '../stores/alerts'
import { useMetricsStore } from '../stores/metrics'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const alertsStore = useAlertsStore()
const metricsStore = useMetricsStore()
const collapsed = ref(false)
let pollTimer = null

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
      { path: '/safety', icon: 'Lock', label: '安全执行', badge: null },
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
const currentPageName = computed(() => allItems.value.find(m => m.path === current.value)?.label || '页面')

const cpuStatus = computed(() => {
  const v = metricsStore.cpuPercent
  return v > 90 ? 'danger' : v > 70 ? 'warning' : ''
})

const memStatus = computed(() => {
  const v = metricsStore.memoryPercent
  return v > 90 ? 'danger' : v > 70 ? 'warning' : ''
})

function navigate(path) {
  router.push(path)
}

function sevColor(s) {
  const lvl = String(s || '').toLowerCase()
  return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[lvl] || 'info'
}

function handleAlert(cmd) {
  if (cmd === 'view-all') {
    router.push('/alerts')
    return
  }
  const a = alertsStore.recent.find(x => x.id === cmd)
  if (a) {
    router.push({
      path: '/flows',
      query: {
        flow: 'alert_response',
        message: a.message || a.title || '',
        severity: a.severity || a.level || '',
      },
    })
  }
}

function logout() {
  userStore.logout()
  router.push('/login')
}

async function pollStatus() {
  await Promise.all([
    metricsStore.fetchMetrics(),
    alertsStore.fetchRecent(5),
    alertsStore.fetchUnreadCount(),
  ])
}

onMounted(() => {
  userStore.hydrateFromStorage()
  pollStatus()
  pollTimer = setInterval(pollStatus, 30000)
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
/* ============================================================
   APP SHELL — 应用外壳布局
   taste-skill: VARIANCE: 4 | MOTION: 3 | DENSITY: 6
   impeccable: 无纯黑/纯灰，tinted 阴影，克制动效
   ============================================================ */

.app-shell {
  display: flex;
  height: 100vh;
  background: var(--color-neutral-50);
}

/* ---- 侧边栏 ---- */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-neutral-900);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  transition: width var(--duration-slow) var(--ease-out);
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
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
}

.nav-item:hover {
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  color: #fff;
  background: rgba(79, 110, 247, 0.2);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary-500);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  animation: scale-in var(--duration-normal) var(--ease-spring);
}

.nav-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: var(--color-primary-500);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform var(--duration-fast) var(--ease-out);
}

.nav-item:hover::after {
  transform: scaleX(0.4);
}

.nav-item.active::after {
  transform: scaleX(0.6);
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

/* ---- 侧边栏底部 ---- */
.sidebar-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: var(--space-2);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator.healthy .status-dot {
  background: var(--color-success);
  box-shadow: 0 0 4px var(--color-success);
  animation: pulse-dot var(--duration-pulse) ease-in-out infinite;
}

.status-indicator.warning .status-dot {
  background: var(--color-warning);
  box-shadow: 0 0 4px var(--color-warning);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.sys-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sys-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
}

.sys-info-label {
  color: rgba(255, 255, 255, 0.35);
}

.sys-info-value {
  color: rgba(255, 255, 255, 0.6);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.sys-info-value.warning { color: var(--color-warning); }
.sys-info-value.danger { color: var(--color-danger); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ---- 主区域 ---- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ---- 顶栏 ---- */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: var(--topbar-height);
  padding: 0 var(--space-6);
  background: #fff;
  border-bottom: 1px solid var(--color-neutral-200);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.collapse-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-neutral-500);
  transition: all var(--duration-fast) var(--ease-out);
}

.collapse-trigger:hover {
  background: var(--color-neutral-100);
  color: var(--color-primary-500);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

/* ---- 指标栏 ---- */
.metrics-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-1) var(--space-3);
  background: var(--color-neutral-50);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  animation: fade-in var(--duration-slow) var(--ease-out);
}

.metric {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--color-neutral-500);
}

.metric-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--color-neutral-700);
  transition: color var(--duration-fast) var(--ease-out);
}

.metric-value.warning { color: var(--color-warning); }
.metric-value.danger { color: var(--color-danger); }

.metric-divider {
  width: 1px;
  height: 12px;
  background: var(--color-neutral-200);
}

/* ---- 图标按钮 ---- */
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-neutral-500);
  transition: all var(--duration-fast) var(--ease-out);
}

.icon-btn:hover {
  background: var(--color-neutral-100);
  color: var(--color-primary-500);
}

/* 铃铛摇晃动画 */
.icon-btn:hover .el-icon {
  animation: swing var(--duration-normal) var(--ease-out);
}

/* ---- 用户触发器 ---- */
.user-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}

.user-trigger:hover {
  background: var(--color-neutral-100);
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary-500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: 600;
  transition: box-shadow var(--duration-fast) var(--ease-out);
}

.user-trigger:hover .user-avatar {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.user-name {
  font-size: var(--text-sm);
  color: var(--color-neutral-700);
  font-weight: 500;
}

.user-role {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.user-role.admin {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.user-role.user {
  background: var(--color-info-bg);
  color: var(--color-info);
}

/* ---- 告警下拉项 ---- */
.alert-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 280px;
}

.alert-title {
  font-size: var(--text-xs);
  color: var(--color-neutral-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 内容区 ---- */
.content {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
  background: var(--color-neutral-50);
}

/* ---- 过渡动画 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active {
  transition: all 350ms var(--ease-out);
}
.slide-up-leave-active {
  transition: all 200ms var(--ease-out);
}
.slide-up-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* 侧边栏 footer 入场 */
.sidebar-footer {
  animation: slide-up var(--duration-slow) var(--ease-out);
}
</style>
