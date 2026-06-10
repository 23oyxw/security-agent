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
  background: var(--color-neutral-50);
}

/* ---- 主区域 ---- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ---- 内容区 ---- */
.content {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
  background: var(--color-neutral-50);
  min-height: 0;
}

/* ============================================================
   路由层级动效系统
   slide-left:  进入子页面（深度增加）
   slide-right: 返回上级（深度减少）
   fade-scale:  同级切换
   ============================================================ */

/* 1. 滑入淡出（默认） */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s ease-in;
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
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-right-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.fade-scale-leave-active {
  transition: all 0.2s ease-out;
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
