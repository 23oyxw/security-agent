<template>
  <header class="topbar">
    <div class="topbar-left">
      <button class="icon-btn" @click="$emit('toggle-sidebar')" title="折叠侧栏">
        <el-icon :size="16"><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
      </button>
      <nav class="breadcrumb-nav" aria-label="面包屑导航">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ currentPageName }}</el-breadcrumb-item>
        </el-breadcrumb>
      </nav>
      <span v-if="themeLabel" class="theme-pill" :title="`当前页面主题：${themeLabel}`">
        <span class="theme-pill-dot" aria-hidden="true"></span>
        {{ themeLabel }}
      </span>
      <span v-if="backendStore.version" class="version-pill" title="后端版本">v{{ backendStore.version }}</span>
      <button
        v-if="pipelineCtx"
        type="button"
        class="pipeline-ctx"
        title="当前流水线任务（点击回到智能助手）"
        @click="goPipelineHome"
      >
        <span class="pipeline-ctx-phase">{{ pipelineCtx.phase }}</span>
        <span v-if="pipelineCtx.l2" class="pipeline-ctx-l2">L2 {{ pipelineCtx.l2 }}</span>
        <code>plan {{ pipelineCtx.planId }}</code>
        <code v-if="pipelineCtx.trace">trace {{ pipelineCtx.trace }}</code>
      </button>
    </div>

    <div class="topbar-right">
      <button class="chat-entry-btn" type="button" title="打开智能体对话" @click="goPipelineHome">
        <el-icon :size="15"><ChatDotRound /></el-icon>
        <span>智能体对话</span>
      </button>

      <!-- 胶囊指标栏 -->
      <div class="metrics-pill">
        <div class="pill-metric" title="CPU 使用率">
          <el-icon :size="13"><Cpu /></el-icon>
          <span class="pill-value" :class="cpuStatus">{{ metricsStore.cpuPercent }}%</span>
        </div>
        <span class="pill-sep"></span>
        <div class="pill-metric" title="内存使用率">
          <el-icon :size="13"><Coin /></el-icon>
          <span class="pill-value" :class="memStatus">{{ metricsStore.memoryPercent }}%</span>
        </div>
      </div>

      <!-- 告警通知 -->
      <el-dropdown trigger="click" @command="handleAlert" class="alert-dropdown">
        <button class="icon-btn" title="告警通知">
          <el-badge :value="alertsStore.unreadCount" :hidden="alertsStore.unreadCount === 0" :max="99">
            <el-icon :size="17"><Bell /></el-icon>
          </el-badge>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="a in alertsStore.recent" :key="a.id" :command="a.id">
              <div class="alert-row">
                <el-tag :type="sevColor(a.level || a.severity)" size="small" effect="plain">{{ a.level || a.severity }}</el-tag>
                <span class="alert-msg">{{ a.title || a.message }}</span>
              </div>
            </el-dropdown-item>
            <el-dropdown-item v-if="!alertsStore.recent.length" disabled>暂无告警</el-dropdown-item>
            <el-dropdown-item divided command="view-all">
              <span class="view-all-link" @click="$router.push('/alerts')">查看全部 →</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 用户菜单 -->
      <el-dropdown trigger="click" class="user-dropdown">
        <button class="user-trigger">
          <span class="user-avatar">{{ (userStore.username || 'U')[0].toUpperCase() }}</span>
          <span v-if="!isNarrow" class="user-info">
            <span class="user-name">{{ userStore.username }}</span>
            <span class="user-role-badge" :class="userStore.role">{{ userStore.role }}</span>
          </span>
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
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { useAlertsStore } from '../../stores/alerts'
import { useMetricsStore } from '../../stores/metrics'
import { useBackendStore } from '../../stores/backend'
import { useAgentStore } from '../../stores/agent'
import { getPageLabel, getThemeLabel, normalizePath } from '../../constants/navigation'
import { activePlanId, activeTraceId, buildAgentQuery } from '../../utils/pipeline-context'

defineProps({ collapsed: Boolean })
defineEmits(['toggle-sidebar', 'logout'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const alertsStore = useAlertsStore()
const metricsStore = useMetricsStore()
const backendStore = useBackendStore()
const agentStore = useAgentStore()

const pipelineCtx = computed(() => {
  const planId = activePlanId(agentStore)
  if (!planId) return null
  const phaseMap = {
    idle: '待命',
    analyze: 'L1 分析',
    analyzed: 'L1/L2',
    execute: 'L3 执行',
    executed: '全流程',
  }
  return {
    planId: planId.slice(0, 8),
    trace: activeTraceId(agentStore)?.slice(0, 8) || '',
    phase: phaseMap[agentStore.dispatchPhase] || agentStore.dispatchPhase,
    l2: agentStore.l2Result?.verdict || agentStore.currentPlan?.l2_verdict || '',
  }
})

function goPipelineHome() {
  router.push({ path: '/agent', query: buildAgentQuery(agentStore, { tab: 'pipeline' }) })
}

const currentPageName = computed(() => getPageLabel(route.path))
const themeLabel = computed(() => getThemeLabel(route.meta.theme))

const isNarrow = ref(false)
let narrowMq = null
let onNarrowChange = null

onMounted(() => {
  narrowMq = window.matchMedia('(max-width: 1100px)')
  onNarrowChange = () => { isNarrow.value = narrowMq.matches }
  onNarrowChange()
  narrowMq.addEventListener('change', onNarrowChange)
})

onUnmounted(() => {
  if (narrowMq && onNarrowChange) narrowMq.removeEventListener('change', onNarrowChange)
})

/* 指标状态 */
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

/* 告警跳转 */
function handleAlert(cmd) {
  if (cmd === 'view-all') { router.push('/alerts'); return }
  const a = alertsStore.recent.find(x => x.id === cmd)
  if (a) {
    router.push({ path: '/alerts', query: { highlight: a.id } })
    if (!a.acknowledged) alertsStore.acknowledge(a.id).catch(() => {})
  }
}
</script>

<style scoped>
/* ============================================================
   Topbar — 顶栏 (Professional Refinement)
   毛玻璃效果 + 专业 B2B 风格，去除活泼动画
   ============================================================ */

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: var(--topbar-height);
  padding: 0 var(--space-6);
  /* 毛玻璃顶栏 — 跟随页面主题色，非白底 */
  background: var(--glass-topbar, rgba(255, 255, 255, 0.78));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border-subtle);
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

@supports not (backdrop-filter: blur(12px)) {
  .topbar {
    background: var(--glass-topbar, rgba(255, 255, 255, 0.92));
  }
}

/* ---- 左区 ---- */
.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.breadcrumb-nav {
  display: flex;
  align-items: center;
}
.breadcrumb-nav :deep(.el-breadcrumb__inner) {
  color: var(--color-text-secondary) !important;
  font-size: var(--text-sm);
}
.breadcrumb-nav :deep(.el-breadcrumb__inner.is-link) {
  color: var(--color-primary-500) !important;
  font-weight: var(--weight-medium);
}

.version-pill {
  font-size: 10px;
  font-weight: var(--weight-semibold);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-neutral-100);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border-subtle);
  font-variant-numeric: tabular-nums;
}

.pipeline-ctx {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: min(360px, 42vw);
  overflow: hidden;
  border: 1px solid rgba(14, 165, 233, 0.25);
  background: rgba(14, 165, 233, 0.08);
  border-radius: var(--radius-full);
  padding: 2px 10px;
  font-size: 10px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.pipeline-ctx-phase {
  font-weight: 700;
  color: #0369a1;
  white-space: nowrap;
}

.pipeline-ctx-l2 {
  text-transform: lowercase;
  white-space: nowrap;
}

.pipeline-ctx code {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-muted);
  white-space: nowrap;
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
  color: var(--color-text-muted);
  transition:
    background var(--duration-fast) var(--ease-out),
    color var(--duration-fast) var(--ease-out);
}
.icon-btn:hover {
  background: var(--color-neutral-100);
  color: var(--color-primary-500);
}

.icon-btn:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}

.chat-entry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary-600), var(--color-primary-500));
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
  transition: transform var(--duration-fast), box-shadow var(--duration-fast);
}

.chat-entry-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.45);
}

/* ---- 右区 ---- */
.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* ---- 胶囊指标 ---- */
.metrics-pill {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-4);
  background: var(--glass-chip, var(--color-surface));
  border: 1px solid var(--glass-border, var(--color-border-default));
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-normal) var(--ease-out);
  animation: fade-in var(--duration-slow) var(--ease-out);
}

.pill-metric {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--color-text-muted);
}

.pill-value {
  font-weight: var(--weight-semibold);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-secondary);
  line-height: 1;
}
.pill-value.warning { color: var(--color-warning); }
.pill-value.danger { color: var(--color-danger); }

.pill-sep {
  width: 1px;
  height: 14px;
  background: var(--color-border-default);
}

/* ---- 告警项 ---- */
.alert-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 280px;
}
.alert-msg {
  font-size: var(--text-xs);
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.view-all-link {
  cursor: pointer;
  color: var(--color-primary-500);
  font-weight: var(--weight-medium);
  font-size: var(--text-xs);
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
.user-trigger:hover { background: var(--color-neutral-100); }

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--gradient-brand-mark);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  transition: box-shadow var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}
.user-trigger:hover .user-avatar {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.1;
}
.user-name {
  font-size: var(--text-sm);
  color: var(--color-text-primary);
  font-weight: var(--weight-medium);
}
.user-role-badge {
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  display: inline-block;
  text-align: center;
}
.user-role-badge.admin {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
.user-role-badge.user {
  background: var(--color-info-bg);
  color: var(--color-info);
}

/* ---- 过渡 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to { opacity: 0; }

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .breadcrumb-nav { display: none; }
  .metrics-pill .pill-metric span:not(.pill-value) { display: none; }
  .user-info { display: none; }
}
</style>
