<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <template #header>
        <div class="login-header">
          <h2>🛡️ 安全运维控制台</h2>
          <p class="sub">银河麒麟智能安全运维 Agent v0.7</p>
          <el-alert type="info" :closable="false" show-icon class="demo-hint">
            <template #title>演示账号</template>
            用户名 <strong>admin</strong> · 密码 <strong>admin123</strong>
            <br />登录后 Token 会保留；要重新登录请在控制台右上角「退出登录」。
          </el-alert>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" prefix-icon="User" placeholder="admin" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            prefix-icon="Lock"
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
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

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
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '登录失败，请确认 API 已启动 (bash boot_start.sh)')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #304156 0%, #1a2332 100%);
}
.login-card { width: 420px; max-width: 96vw; }
.login-header { text-align: center; }
.login-header h2 { margin: 0 0 8px; }
.sub { color: #999; font-size: 13px; margin: 0 0 12px; }
.demo-hint { text-align: left; font-size: 12px; }
.demo-hint :deep(.el-alert__title) { font-size: 13px; }
</style>
