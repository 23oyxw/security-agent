<template>
  <div class="app-shell">
    <!-- 侧边栏（独立组件） -->
    <Sidebar :collapsed="collapsed" @toggle="collapsed = !collapsed" @navigate="navigate" />

    <!-- 主区域 -->
    <div class="main-area">
      <!-- 顶栏（独立组件） -->
      <Topbar :collapsed="collapsed" @toggle-sidebar="collapsed = !collapsed" @logout="logout" />

      <!-- 内容区 -->
      <main class="content">
        <router-view v-slot="{ Component, route: viewRoute }">
          <transition :name="transitionName" mode="out-in">
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
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useSystemPolling } from '../composables/useSystemPolling'
import Sidebar from '../components/layout/Sidebar.vue'
import Topbar from '../components/layout/Topbar.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 轮询逻辑由 composable 管理，Layout 不再直接操作 Store
useSystemPolling(30000)

const collapsed = ref(false)

// 路由层级动效
const transitionName = ref('slide-fade')

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
  background: var(--color-surface);
}

/* ---- 主区域 ---- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0; /* 防止 flex 子项溢出 */
}

/* ---- 内容区 ---- */
.content {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
  /*
   * 微妙的径向渐变 — 增加空间层次感而不喧宾夺主
   * 左下角：primary 蓝调   6%
   * 右上角：accent  青调   6%
   * 底色：surface 基础色
   */
  background:
    radial-gradient(circle at 15% 85%, rgba(37, 99, 235, 0.06) 0%, transparent 50%),
    radial-gradient(circle at 85% 15%, rgba(6, 182, 212, 0.06) 0%, transparent 50%),
    var(--color-surface);
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
    opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-leave-active {
  transition:
    opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
    opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-right-leave-active {
  transition:
    opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
</style>
