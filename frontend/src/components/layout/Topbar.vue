<template>
  <header class="topbar">
    <div class="topbar-left">
      <button class="collapse-trigger" @click="$emit('toggle-sidebar')">
        <el-icon :size="18"><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
      </button>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>{{ currentPageName }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="topbar-right">
      <!-- 胶囊化 Metrics Bar -->
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

      <!-- 告警下拉 -->
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

      <!-- 用户下拉 -->
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
            <el-dropdown-item divided @click="$emit('logout')">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { useAlertsStore } from '../../stores/alerts'
import { useMetricsStore } from '../../stores/metrics'

defineProps({
  collapsed: Boolean,
})

defineEmits(['toggle-sidebar', 'logout'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const alertsStore = useAlertsStore()
const metricsStore = useMetricsStore()

const menuGroups = [
  {
    label: '总览',
    items: [
      { path: '/', label: '仪表盘' },
      { path: '/agent', label: '智能助手' },
      { path: '/canvas', label: '无限画布' },
    ],
  },
  {
    label: '安全管控',
    items: [
      { path: '/safety', label: '安全执行' },
      { path: '/alerts', label: '告警管理' },
    ],
  },
  {
    label: '能力与审计',
    items: [
      { path: '/mcp', label: 'MCP 能力中心' },
      { path: '/trace', label: 'Trace 溯源' },
    ],
  },
  {
    label: '知识',
    items: [
      { path: '/knowledge', label: '知识库' },
      { path: '/guide', label: '技术导引' },
    ],
  },
]

const allItems = computed(() => menuGroups.flatMap(g => g.items))
const currentPath = computed(() => (route.path === '/dashboard' ? '/' : route.path))
const currentPageName = computed(() => allItems.value.find(m => m.path === currentPath.value)?.label || '页面')

const cpuStatus = computed(() => {
  const v = metricsStore.cpuPercent
  return v > 90 ? 'danger' : v > 70 ? 'warning' : ''
})

const memStatus = computed(() => {
  const v = metricsStore.memoryPercent
  return v > 90 ? 'danger' : v > 70 ? 'warning' : ''
})

function sevColor(s) {
  const lvl = String(s || '').toLowerCase()
  return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[lvl] || 'info'
}

// P1 修复：告警跳转使用命名路由，跳转到 /alerts 页面（而非 /flows）
function handleAlert(cmd) {
  if (cmd === 'view-all') {
    router.push('/alerts')
    return
  }
  const a = alertsStore.recent.find(x => x.id === cmd)
  if (a) {
    // 跳转到告警管理页面，携带 ID 以高亮定位
    router.push({ path: '/alerts', query: { highlight: a.id } })
    // 标记为已读
    if (!a.acknowledged) {
      alertsStore.acknowledge(a.id).catch(() => {})
    }
  }
}
</script>

<style scoped>
/* ---- 顶栏（毛玻璃效果） ---- */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: var(--topbar-height);
  padding: 0 var(--space-6);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
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

/* ---- 胶囊化指标栏 ---- */
.metrics-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 4px 14px;
  background: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  box-shadow: var(--shadow-sm);
  transition: all 0.3s ease;
  animation: fade-in var(--duration-slow) var(--ease-out);
}

.metrics-bar:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary-300);
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
  background: linear-gradient(135deg, #4f6ef7 0%, #6366f1 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: 600;
  transition: box-shadow var(--duration-fast) var(--ease-out);
}

.user-trigger:hover .user-avatar {
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.2);
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

/* ---- fade 过渡 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
