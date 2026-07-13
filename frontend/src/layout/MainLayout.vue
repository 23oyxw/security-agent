<template>
  <div class="app-shell" :class="[pageThemeClass, { 'is-narrow': isNarrow }]">
    <div
      v-if="isNarrow && !collapsed"
      class="sidebar-backdrop"
      aria-hidden="true"
      @click="toggleCollapsed"
    />
    <!-- 环境光球（对话页关闭以减轻绘制） -->
    <div v-if="!isAgentRoute" class="ambient-orbs" aria-hidden="true">
      <div class="ambient-orb ambient-orb--1"></div>
      <div class="ambient-orb ambient-orb--2"></div>
      <div class="ambient-orb ambient-orb--3"></div>
    </div>

    <!-- 侧边栏（独立组件） -->
    <Sidebar
      :collapsed="collapsed"
      :overlay="isNarrow && !collapsed"
      @toggle="toggleCollapsed"
      @navigate="navigate"
      @resize-start="startResize"
    />

    <!-- 主区域 -->
    <div class="main-area">
      <el-alert
        v-if="!backendStore.online"
        type="error"
        :closable="false"
        show-icon
        class="backend-offline-banner"
        title="后端未连接"
        description="请先运行 START_WIN.bat 或 scripts/start_backend.ps1 启动 http://127.0.0.1:8900 ，勿单独打开 dist/index.html。"
      />
      <!-- 顶栏（独立组件） -->
      <Topbar :collapsed="collapsed" @toggle-sidebar="toggleCollapsed" @logout="logout" />

      <!-- 内容区（顶栏 PillarWorkflowRail 已移除，五层导航仅在侧栏） -->
      <main ref="contentRef" class="content" :class="{ 'content--agent': isAgentRoute }">
        <router-view v-slot="{ Component, route: viewRoute }">
          <transition :name="transitionName" mode="default" @after-enter="onPageEntered">
            <component :is="Component" :key="viewRoute.fullPath" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
/**
 * MainLayout — 应用外壳布局
 * 职责：仅负责布局编排，不承担数据获取
 *
 * 数据轮询 → useSystemPolling composable
 * 侧边栏 → Sidebar 独立组件
 * 顶栏   → Topbar 独立组件
 *
 * 布局策略：
 * - content 区提供微妙的径向渐变背景增加层次感
 * - 渐变使用 primary/accent 色系，透明度 6%（专业 B2B 克制风格）
 * - Dashboard 自身管理内部 max-width 和栅格，Layout 不做过度约束
 */
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useBackendStore } from '../stores/backend'
import { useSystemPolling } from '../composables/useSystemPolling'
import { useStaggerReveal } from '../composables/useStaggerReveal'
import Sidebar from '../components/layout/Sidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import { useSidebarResize } from '../composables/useSidebarResize'
import { useSidebarCollapse } from '../composables/useSidebarCollapse'
import { usePipelineBootstrap } from '../composables/usePipelineBootstrap'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const backendStore = useBackendStore()

// 全局监控 10s 轮询 — 供顶栏 / 仪表盘 / 态势总览共用
useSystemPolling(10000)
usePipelineBootstrap()

const { collapsed, isNarrow, toggle: toggleCollapsed } = useSidebarCollapse()
const { startResize } = useSidebarResize()
const contentRef = ref(null)
const { refresh: refreshReveal } = useStaggerReveal(contentRef)

const pageThemeClass = computed(() => {
  const theme = route.meta.theme || 'ops'
  return `page-theme-${theme}`
})

const isAgentRoute = computed(() => route.path === '/agent' || route.path.startsWith('/agent/'))

const THEME_CLASSES = [
  'page-theme-ops', 'page-theme-intel', 'page-theme-guard', 'page-theme-alert',
  'page-theme-mesh', 'page-theme-audit', 'page-theme-archive', 'page-theme-learn',
  'page-theme-canvas', 'page-theme-admin',
]

watch(
  pageThemeClass,
  (cls) => {
    document.documentElement.classList.remove(...THEME_CLASSES)
    document.documentElement.classList.add(cls)
  },
  { immediate: true }
)

// 路由层级动效
const transitionName = ref('slide-fade')

watch(
  () => route.path,
  () => {
    if (route.path !== '/agent') refreshReveal()
  },
)

function onPageEntered() {
  if (contentRef.value) contentRef.value.scrollTop = 0
  refreshReveal()
  window.setTimeout(() => window.dispatchEvent(new Event('resize')), 280)
}

watch(
  () => route.path,
  (newPath, oldPath) => {
    if (!oldPath) {
      transitionName.value = 'fade-scale'
      return
    }
    const newDepth = newPath.split('/').filter(Boolean).length
    const oldDepth = oldPath.split('/').filter(Boolean).length

    if (newDepth > oldDepth) {
      transitionName.value = 'slide-left'     // 进入子页面
    } else if (newDepth < oldDepth) {
      transitionName.value = 'slide-right'    // 返回上级
    } else {
      transitionName.value = 'fade-scale'     // 同级切换
    }
  },
  { immediate: true }
)

function navigate(path) {
  router.push(path)
}

function logout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
/* ============================================================
   APP SHELL — 应用外壳布局
   职责：仅布局编排，不承担数据获取
   ============================================================ */

.app-shell {
  display: flex;
  height: 100vh;
  /* 必须读 page-theme 变量；勿写死 gradient-content-bg */
  background: var(--gradient-page-bg, var(--gradient-content-bg));
  background-attachment: fixed;
  position: relative;
  isolation: isolate;
}

/* ---- 主区域 ---- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  position: relative;
}

/* 内容区底层纹理 + 影视顶光 */
.main-area::before {
  content: '';
  position: absolute;
  inset: var(--topbar-height) 0 0 0;
  pointer-events: none;
  background-image: var(--pattern-dot);
  background-size: var(--pattern-dot-size);
  opacity: 0.85;
  z-index: 0;
}

.main-area::after {
  content: '';
  position: absolute;
  inset: var(--topbar-height) 0 0 0;
  pointer-events: none;
  background: var(--gradient-page-light, var(--gradient-cinema-light));
  z-index: 0;
  mix-blend-mode: soft-light;
}

/* ---- 内容区 ---- */
.content {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
  position: relative;
  z-index: 1;
  background: transparent;
  min-height: 0;

  /* 统一滚动条样式（与 Dashboard 协同） */
  scrollbar-width: thin;
  scrollbar-color: var(--color-border-default) transparent;
}

.content::-webkit-scrollbar {
  width: 6px;
}
.content::-webkit-scrollbar-track {
  background: transparent;
}
.content::-webkit-scrollbar-thumb {
  background-color: var(--color-border-default);
  border-radius: 3px;
}

.content--agent {
  padding: var(--space-3) var(--space-4);
  overflow: hidden;
  height: calc(100dvh - var(--topbar-height, 56px) - 8px);
  box-sizing: border-box;
}

/* ============================================================
   路由层级动效系统

   slide-left:  进入子页面（深度增加）
   slide-right: 返回上级（深度减少）
   fade-scale:  同级切换

   所有过渡均限定 opacity + transform（GPU 合成层友好）
   ============================================================ */

/* 1. 滑入淡出（默认） */
.slide-fade-enter-active {
  transition:
    opacity var(--duration-normal) var(--ease-out),
    transform var(--duration-normal) var(--ease-out);
}
.slide-fade-leave-active {
  transition:
    opacity var(--duration-fast) var(--ease-in),
    transform var(--duration-fast) var(--ease-in);
}
.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 2. 左滑（进入子页面） */
.slide-left-enter-active {
  transition:
    opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-leave-active {
  transition:
    opacity 0.12s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.12s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-enter-from {
  opacity: 0;
  transform: translateX(24px);
}
.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

/* 3. 右滑（返回上级） */
.slide-right-enter-active {
  transition:
    opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-right-leave-active {
  transition:
    opacity 0.12s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.12s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-right-enter-from {
  opacity: 0;
  transform: translateX(-24px);
}
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

/* 4. 缩放淡出（同级切换） */
.fade-scale-enter-active {
  transition:
    opacity 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
    transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.fade-scale-leave-active {
  transition:
    opacity 0.2s var(--ease-out),
    transform 0.2s var(--ease-out);
}
.fade-scale-enter-from {
  opacity: 0;
  transform: scale(0.96);
}
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(1.02);
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 9;
  backdrop-filter: blur(2px);
}

@media (max-width: 900px) {
  .content {
    padding: var(--space-3);
  }
}

@media (max-width: 768px) {
  .content {
    padding: var(--space-2);
  }
}
</style>
