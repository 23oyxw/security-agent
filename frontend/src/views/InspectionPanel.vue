<template>
  <div class="inspection-page page-theme-guard panel-page">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
      :layer-label="pageMeta.layerLabel"
      :agent="pageMeta.agent"
    />
    <section class="toolbar">
      <el-select v-model="suiteId" style="width:220px">
        <el-option v-for="s in suites" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-button type="primary" :loading="running" @click="onRun">执行巡检</el-button>
      <el-button :loading="riskLoading" @click="onRisk">风险窗口</el-button>
    </section>
    <section v-if="report" class="report">
      <h3>{{ report.suite_name }} {{ report.summary?.ok ? '通过' : '未通过' }}</h3>
      <el-table :data="report.cases" size="small" stripe>
        <el-table-column prop="id" label="ID" width="140" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="grade" label="等级" width="70" />
      </el-table>
    </section>
    <section v-else class="report-empty">
      <el-empty description="尚未执行巡检" :image-size="72">
        <template #default>
          <p class="empty-hint">选择用例集后点击「执行巡检」，报告将显示在此区域。</p>
          <el-button type="primary" :loading="running" @click="onRun">立即执行</el-button>
        </template>
      </el-empty>
      <el-table v-if="suites.length" :data="suites" size="small" stripe class="catalog-table">
        <el-table-column prop="id" label="用例集 ID" width="160" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="case_count" label="用例数" width="90" />
      </el-table>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import { usePageMeta } from '../composables/usePageMeta'
import { fetchInspectionCatalog, runInspection, fetchInspectionRisk, fetchLatestInspectionReport } from '../api/inspection'

const { pageMeta } = usePageMeta('inspection')
const suites = ref([])
const suiteId = ref('kylin_baseline')
const running = ref(false)
const riskLoading = ref(false)
const report = ref(null)
async function onRun() {
  running.value = true
  try {
    report.value = await runInspection(suiteId.value)
    ElMessage.success('巡检完成')
  } finally { running.value = false }
}
async function onRisk() {
  riskLoading.value = true
  try { await fetchInspectionRisk(); ElMessage.info('已请求风险推演') } finally { riskLoading.value = false }
}
onMounted(async () => {
  const cat = await fetchInspectionCatalog()
  suites.value = cat.suites || []
  try { report.value = await fetchLatestInspectionReport(suiteId.value) } catch {}
})
</script>
<style scoped>
.inspection-page { padding: var(--space-4, 16px); }
.panel-page :deep(.el-empty) { padding: 24px 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; }
.report { padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; }
.report-empty { padding: 8px 0 24px; }
.empty-hint { margin: 0 0 12px; font-size: 13px; color: var(--color-text-muted); }
.catalog-table { margin-top: 20px; }
</style>
