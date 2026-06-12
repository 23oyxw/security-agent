<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from './stores/user'

const userStore = useUserStore()
onMounted(() => {
  if (!userStore.token) return
  userStore.fetchMe().catch(err => {
    // 仅 401/403 清会话；网络抖动或 Mock 未就绪时不强制登出
    const status = err.response?.status
    if (status === 401 || status === 403) userStore.logout()
  })
})
</script>

<style>
body { margin: 0; }
</style>
