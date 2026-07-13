<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <template #header>
        <div class="login-header">
          <h2><span aria-hidden="true" class="login-icon">&#x1F6E1;</span> 安全运维控制台 <span style="font-size:0.6em;color:#10b981;font-weight:400">v0.9.0 · Zoom 1.25x</span></h2>
          <p class="sub">银河麒麟智能安全运维 Agent v{{ APP_VERSION }}</p>
          <el-alert v-if="sessionExpired" type="warning" :closable="false" show-icon class="demo-hint" role="alert">
            <template #title>登录已过期</template>
            后端重启或 Token 失效，请重新登录（admin / admin123）。
          </el-alert>
          <el-alert v-else type="info" :closable="false" show-icon class="demo-hint" role="status">
            <template #title>演示账号</template>
            用户名 <strong>admin</strong> · 密码 <strong>admin123</strong>
            <br />登录后 Token 会保留；要重新登录请在控制台右上角「退出登录」。
          </el-alert>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :prefix-icon="User" placeholder="admin" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            :prefix-icon="Lock"
            placeholder="admin123"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%">登 录</el-button>
        <el-button text type="primary" style="width:100%;margin-top:8px" @click="fillDemo">填入演示账号</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import { buildAgentRoute } from '../constants/navigation'
import { APP_VERSION } from '../constants/app-version'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const sessionExpired = computed(() => route.query.expired === '1')

function fillDemo() {
  form.username = 'admin'
  form.password = 'admin123'
}

async function handleLogin() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(buildAgentRoute('pipeline'))
  } catch (e) {
    ElMessage.error(
      e.response?.data?.detail
      || e.message
      || '登录失败：请用 admin / admin123，并重启前端 (npm run dev 或 npm run dev:mock)'
    )
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (import.meta.env.DEV && !form.username) fillDemo()
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #304156 0%, #1a2332 50%, #2a3a52 100%);
  background-size: 200% 200%;
  animation: gradient-shift 12s ease infinite;
  position: relative;
  overflow: hidden;
}

/* 点阵装饰背景 */
.login-page::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
}

/* 浮动光斑 */
.login-page::after {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 110, 247, 0.12), transparent 70%);
  top: 20%;
  right: 10%;
  animation: pulse-ring 6s ease-in-out infinite;
  pointer-events: none;
}

.login-card {
  width: 420px;
  max-width: 96vw;
  position: relative;
  z-index: 1;
  animation: slide-up 600ms var(--ease-out) 200ms both;
  overflow: hidden;
}

/* 微光扫过效果 */
.login-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 200%;
  height: 100%;
  background: linear-gradient(90deg, transparent 30%, rgba(255, 255, 255, 0.06) 50%, transparent 70%);
  background-size: 200% 100%;
  animation: shimmer 4s ease-in-out infinite;
  pointer-events: none;
  z-index: 1;
}

.login-header { text-align: center; }
.login-header h2 { margin: 0 0 8px; }
.sub { color: #999; font-size: 13px; margin: 0 0 12px; }
.demo-hint {
  text-align: left;
  font-size: 12px;
  animation: fade-in var(--duration-slow) var(--ease-out) 600ms both;
}
.demo-hint :deep(.el-alert__title) { font-size: 13px; }

/* 登录按钮增强 */
.login-card :deep(.el-button--primary) {
  transition: all var(--duration-normal) var(--ease-out);
}

.login-card :deep(.el-button--primary):hover {
  box-shadow: var(--shadow-glow-primary);
  transform: translateY(-1px);
}
</style>
