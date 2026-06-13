<template>
  <div class="repair-page page-theme-guard">
    <PageHeader title="Environment Repair" subtitle="L3 repair via L2 sandbox" layer="L3" />
    <section class="repair-grid">
      <article v-for="item in catalog" :key="item.id" class="repair-card">
        <h3>{{ item.title }}</h3>
        <p>{{ item.message }}</p>
        <el-button type="primary" size="small" :loading="triggering === item.id" @click="onTrigger(item)">Repair</el-button>
      </article>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import { fetchRepairCatalog, triggerRepair } from '../api/repair'
const catalog = ref([])
const triggering = ref(null)
async function onTrigger(item) {
  triggering.value = item.id
  try {
    const res = await triggerRepair(item.id, true)
    if (res.ok) ElMessage.success('ok ' + res.plan_id)
    else ElMessage.error(res.error || 'fail')
  } finally { triggering.value = null }
}
onMounted(async () => { catalog.value = (await fetchRepairCatalog()).catalog || [] })
</script>
<style scoped>
.repair-page { padding: 16px; }
.repair-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(220px,1fr)); gap: 12px; }
.repair-card { padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; }
</style>