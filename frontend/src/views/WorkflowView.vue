<template>
  <el-card header="运维流程（只读）— 五大支柱 + 三层防御">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
      :title="workflow.description || '预置流程 JSON，答辩演示用'" />
    <el-steps :active="activeStep" finish-status="success" align-center style="margin-bottom: 24px">
      <el-step v-for="(s, i) in workflow.steps" :key="s.id" :title="s.title" :description="s.pillar" @click="activeStep = i" />
    </el-steps>
    <el-table :data="workflow.steps" stripe v-loading="loading">
      <el-table-column prop="id" label="步骤" width="100" />
      <el-table-column prop="title" label="名称" width="160" />
      <el-table-column prop="pillar" label="赛题支柱" width="160" />
      <el-table-column prop="api" label="对应 API" width="280" />
      <el-table-column prop="detail" label="说明" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const loading = ref(false)
const activeStep = ref(0)
const workflow = reactive({ title: '', description: '', steps: [] })

onMounted(async () => {
  loading.value = true
  try {
    const res = await api.get('/workflow/standard')
    Object.assign(workflow, res)
  } catch {} finally { loading.value = false }
})
</script>
