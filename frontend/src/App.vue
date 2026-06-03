<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from './stores/user'

const userStore = useUserStore()
onMounted(() => {
  if (userStore.isLoggedIn) userStore.fetchMe().catch(() => userStore.logout())
})
</script>

<style>
body { margin: 0; font-family: 'Helvetica Neue', Arial, sans-serif; }
</style>