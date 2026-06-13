<template>
  <div class="repair-page page-theme-guard">
    <PageHeader title="环境修复" subtitle="L3 修复簇 · 经 L2 沙箱预演" layer="L3" />
    <section class="repair-grid">
      <article v-for="item in catalog" :key="item.id" class="repair-card">
        <h3>{{ item.title }}</h3>
        <p>{{ item.message }}</p>
        <el-tag v-if="item.sandbox_required" size="small" type="warning">需沙箱</el-tag>
        <el-button type="primary" size="small" :loading="triggering === item.id" @click="onTrigger(item)">执行修复</el-button>
      </article>
    </section>
    <section v-if="history.length" class="repair-history">
      <h3>最近修复记录</h3>
      <el-table :data="history" size="small" stripe>
        <el-table-column prop="plan_id" label="Plan ID" width="180" />
        <el-table-column prop="intent" label="意图" width="120" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="l2_verdict" label="L2" width="100" />
      </el-table>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import { fetchRepairCatalog, fetchRepairHistory, triggerRepair } from '../api/repair'
const catalog = ref([])
const history = ref([])
const triggering = ref(null)
async function onTrigger(item) {
  if (item.sandbox_required) {
    try {
      await ElMessageBox.confirm(`确认执行「${item.title}」？写操作将经 L2 沙箱预演。`, '确认修复', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
    } catch { return }
  }
  triggering.value = item.id
  try {
    const res = await triggerRepair(item.id, true)
    if (res.ok) {
      ElMessage.success(`修复已启动计划 ${res.plan_id}`)
      history.value = (await fetchRepairHistory()).repairs || []
    } else if (res.needs_confirm) {
      ElMessage.warning('L2 需要二次确认')
    } else {
      ElMessage.error(res.error || '修复失败')
    }
  } finally { triggering.value = null }
}
onMounted(async () => {
  catalog.value = (await fetchRepairCatalog()).catalog || []
  history.value = (await fetchRepairHistory()).repairs || []
})
</script>
<style scoped>
.repair-page { padding: 16px; }
.repair-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(220px,1fr)); gap: 12px; margin-bottom: 24px; }
.repair-card { padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
.repair-history h3 { margin: 0 0 12px; font-size: 15px; }
</style>