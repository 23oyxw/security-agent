<template>
  <el-container class="main-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo" @click="collapsed = !collapsed">
        <el-icon :size="28" color="#409EFF"><Monitor /></el-icon>
        <span v-if="!collapsed" class="logo-text">安全运维控制台</span>
      </div>
      <el-menu
        :default-active="current"
        :collapse="collapsed"
        router
        background-color="#001529"
        text-color="#ffffffb3"
        active-text-color="#409EFF"
        class="side-menu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>
            <span>{{ item.label }}</span>
            <el-badge v-if="item.badge && item.badge() > 0" :value="item.badge()" :max="99" class="menu-badge" />
          </template>
        </el-menu-item>
      </el-menu>

      <div v-if="!collapsed" class="sidebar-footer">
        <div class="system-status-mini">
          <div class="status-dot" :class="metricsStore.systemHealthy ? 'healthy' : 'warning'"></div>
          <span>{{ metricsStore.systemHealthy ? '系统正常' : '需要关注' }}</span>
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div style="display:flex;align-items:center;gap:16px">
          <el-icon class="collapse-btn" @click="collapsed = !collapsed" :size="20">
            <component :is="collapsed ? 'Expand' : 'Fold'" />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageName }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div style="display:flex;align-items:center;gap:16px">
          <div class="topbar-metrics">
            <span class="metric-item">
              <el-icon><Cpu /></el-icon> {{ metricsStore.cpuPercent }}%
            </span>
            <span class="metric-item">
              <el-icon><Coin /></el-icon> {{ metricsStore.memoryPercent }}%
            </span>
          </div>

          <el-dropdown trigger="click" @command="handleAlert">
            <el-badge :value="alertsStore.unreadCount" :hidden="alertsStore.unreadCount === 0" :max="99">
              <el-icon :size="20" style="cursor:pointer"><Bell /></el-icon>
            </el-badge>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="a in alertsStore.recent" :key="a.id" :command="a.id" divided>
                  <div style="max-width:300px">
                    <el-tag :type="sevColor(a.level || a.severity)" size="small">{{ a.level || a.severity }}</el-tag>
                    <span style="margin-left:6px;font-size:12px">{{ a.title || a.message }}</span>
                    <div v-if="a.occurred_at || a.timestamp" style="font-size:11px;color:#999;margin-top:2px">
                      {{ a.occurred_at || a.timestamp }}
                    </div>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item v-if="!alertsStore.recent.length" disabled>暂无告警</el-dropdown-item>
                <el-dropdown-item divided command="view-all">
                  <el-button text type="primary" size="small" @click="$router.push('/alerts')">查看全部</el-button>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown trigger="click">
            <div style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <el-avatar :size="28" style="background:#409EFF">{{ (userStore.username || 'U')[0].toUpperCase() }}</el-avatar>
              <span style="font-size:13px">{{ userStore.username }}</span>
              <el-tag size="small" :type="userStore.role === 'admin' ? 'danger' : 'info'">{{ userStore.role }}</el-tag>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <el-icon><User /></el-icon> {{ userStore.username }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
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

const menuItems = [
  { path: '/', icon: 'Odometer', label: '仪表盘', badge: null },
  { path: '/agent', icon: 'ChatDotRound', label: '智能助手 (L3)', badge: null },
  { path: '/flows', icon: 'SetUp', label: 'Skill 流程 (L2)', badge: null },
  { path: '/workflow', icon: 'Guide', label: '运维流程', badge: null },
  { path: '/safety', icon: 'Lock', label: '安全门禁', badge: null },
  { path: '/executor', icon: 'CaretRight', label: '安全执行器', badge: null },
  { path: '/alerts', icon: 'Bell', label: '告警管理', badge: () => alertsStore.unreadCount },
  { path: '/mcp', icon: 'Connection', label: 'MCP / L1 能力', badge: null },
  { path: '/trace', icon: 'Share', label: 'Trace 溯源', badge: null },
  { path: '/knowledge', icon: 'Reading', label: '知识库', badge: null },
]

const current = computed(() => (route.path === '/dashboard' ? '/' : route.path))
const currentPageName = computed(() => menuItems.find(m => m.path === current.value)?.label || '页面')

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
.main-layout { height: 100vh; }
.sidebar { background: #001529; display: flex; flex-direction: column; transition: width 0.3s; overflow: hidden; }
.logo { display: flex; align-items: center; gap: 10px; padding: 16px; cursor: pointer; height: 60px; }
.logo-text { color: #fff; font-size: 16px; font-weight: bold; white-space: nowrap; }
.side-menu { flex: 1; border-right: none; }
.side-menu:not(.el-menu--collapse) { width: 220px; }
.menu-badge { margin-left: 8px; }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid #ffffff1a; }
.system-status-mini { display: flex; align-items: center; gap: 8px; color: #ffffffb3; font-size: 12px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.healthy { background: #67C23A; box-shadow: 0 0 4px #67C23A; }
.status-dot.warning { background: #E6A23C; box-shadow: 0 0 4px #E6A23C; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.topbar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e8e8e8; background: #fff; padding: 0 16px; height: 56px; }
.collapse-btn { cursor: pointer; color: #666; }
.collapse-btn:hover { color: #409EFF; }
.topbar-metrics { display: flex; gap: 16px; }
.metric-item { display: flex; align-items: center; gap: 4px; font-size: 13px; color: #666; }
.main-content { background: #f5f5f5; padding: 16px; overflow-y: auto; }
</style>
