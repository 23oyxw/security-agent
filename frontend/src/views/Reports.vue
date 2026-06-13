<template>
  <div class="reports-view">
    <PageHeader title="任务分析报表" subtitle="Prompt/命令分层分析 · 工作流匹配 · 学术参照 · 支持上传" layer="L1" />
    <el-row :gutter="16">
      <el-col :span="14">
        <div class="section-card">
          <h3>任务输入</h3>
          <el-input v-model="prompt" type="textarea" :rows="6" placeholder="输入运维指令或 Prompt" />
          <div class="upload-row">
            <el-upload :auto-upload="false" :limit="1" :on-change="onFile"><el-button size="small">上传文件</el-button></el-upload>
            <el-button type="primary" :loading="analyzing" @click="runAnalyze">分析</el-button>
          </div>
        </div>
        <div v-if="result" class="section-card">
          <h3>结果 {{ result.analysis_id }}</h3>
          <p>意图: {{ result.intent }} · 层级: {{ (result.layers_detected||[]).join(' → ') }}</p>
          <p>风险: {{ result.risk?.level }} · Skill: {{ result.skill_flow || '—' }}</p>
          <el-button type="primary" @click="$router.push({path:'/agent',query:{q:prompt}})">走主线编排</el-button>
          <el-button @click="$router.push('/l5')">L5 性能可视化</el-button>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="section-card">
          <h3>历史分析</h3>
          <el-table :data="analyses" size="small" @row-click="loadHistory">
            <el-table-column prop="analysis_id" label="ID" width="110" />
            <el-table-column prop="intent" label="意图" />
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import { analyzeTask, getAnalysis, listReports } from '../api/reports'
const prompt = ref('')
const uploadFile = ref(null)
const analyzing = ref(false)
const result = ref(null)
const analyses = ref([])
function onFile(f) { uploadFile.value = f?.raw || null }
async function runAnalyze() {
  if (!prompt.value.trim() && !uploadFile.value) return ElMessage.warning('请输入或上传')
  analyzing.value = true
  try { result.value = await analyzeTask(prompt.value, uploadFile.value); await refresh() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '失败') }
  finally { analyzing.value = false }
}
async function loadHistory(row) { if (row?.analysis_id) result.value = await getAnalysis(row.analysis_id) }
async function refresh() { const d = await listReports().catch(()=>({})); analyses.value = d.analyses || [] }
onMounted(refresh)
</script>
<style scoped>.upload-row{display:flex;gap:12px;margin-top:12px}</style>
