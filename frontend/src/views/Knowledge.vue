<template>
  <div>
    <el-row :gutter="16">
      <!-- 左侧：安全知识库搜索 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>📚 安全知识库</span>
              <el-tag type="info">共 {{ playbooks.length }} 条处置剧本</el-tag>
            </div>
          </template>

          <!-- 搜索 -->
          <div style="margin-bottom:16px">
            <el-input v-model="query" placeholder="搜索安全处置知识，例如：SSH暴力破解、端口暴露、提权攻击、审计配置..." clearable @keydown.enter="search" size="large">
              <template #append>
                <el-button :loading="searching" @click="search" type="primary">
                  <el-icon><Search /></el-icon> 搜索
                </el-button>
              </template>
            </el-input>
          </div>

          <!-- 搜索结果 -->
          <div v-if="results.length" style="margin-bottom:16px">
            <h4 style="margin-bottom:8px">🔍 搜索结果 ({{ results.length }})</h4>
            <el-collapse v-model="activeResults">
              <el-collapse-item v-for="r in results" :key="r.title" :name="r.title">
                <template #title>
                  <div style="display:flex;align-items:center;gap:8px;width:100%">
                    <el-tag size="small" type="success">得分 {{ (r.score * 100).toFixed(0) }}%</el-tag>
                    <span style="font-weight:500">{{ r.title }}</span>
                    <span style="margin-left:auto;color:#999;font-size:12px">{{ r.source }}</span>
                  </div>
                </template>
                <div class="result-content">{{ r.content }}</div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 剧本列表 -->
          <h4 style="margin-bottom:8px">📋 安全处置剧本</h4>
          <el-table v-if="!loading" :data="paginatedPlaybooks" stripe size="small" empty-text="暂无剧本" max-height="400">
            <el-table-column prop="id" label="编号" width="140" show-overflow-tooltip />
            <el-table-column prop="title" label="标题" width="220" show-overflow-tooltip />
            <el-table-column prop="category" label="分类" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="categoryColor(row.category)">{{ categoryLabel(row.category) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="severity" label="严重度" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.severity" :type="sevColor(row.severity)" size="small">{{ row.severity }}</el-tag>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" show-overflow-tooltip />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="viewPlaybook(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else v-loading="loading" style="min-height:200px"></div>
          <div style="margin-top:12px;text-align:right">
            <el-pagination v-model:current-page="page" :page-size="pageSize" :total="playbooks.length" layout="prev, pager, next" small />
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：详情与统计 -->
      <el-col :span="8">
        <el-card header="知识库统计" style="margin-bottom:16px">
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="剧本总数">{{ playbooks.length }}</el-descriptions-item>
            <el-descriptions-item label="严重度分布">
              <span v-for="s in sevStats" :key="s.label" style="margin-right:8px">
                <el-tag :type="s.color" size="small">{{ s.label }}: {{ s.count }}</el-tag>
              </span>
              <span v-if="!sevStats.length" style="color:#999">加载中…</span>
            </el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:12px">
            <div v-for="cat in categories" :key="cat" class="cat-row" @click="filterByCategory(cat)">
              <el-tag size="small" :type="categoryColor(cat)">{{ categoryLabel(cat) }}</el-tag>
              <span class="cat-count">{{ playbooks.filter(p => (p.category || '通用') === cat).length }} 条</span>
            </div>
          </div>
        </el-card>

        <el-card header="选中剧本详情">
          <template v-if="selected">
            <h4 style="margin:0 0 8px">{{ selected.title }}</h4>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="编号">{{ selected.id }}</el-descriptions-item>
              <el-descriptions-item label="分类">{{ categoryLabel(selected.category) }}</el-descriptions-item>
              <el-descriptions-item v-if="selected.severity" label="严重度">{{ selected.severity }}</el-descriptions-item>
            </el-descriptions>
            <div style="margin-top:12px;font-size:13px;line-height:1.6;white-space:pre-wrap">{{ selected.content || selected.description || '暂无详细内容' }}</div>
            <div v-if="selected.steps" style="margin-top:10px;font-size:12px;color:#409eff;line-height:1.6">
              <strong>✓ 处置步骤：</strong>{{ selected.steps }}
            </div>
            <div v-if="selected.do_not?.length" style="margin-top:6px;font-size:12px;color:#e6a23c;line-height:1.6">
              <strong>⚠ 禁止操作：</strong>{{ selected.do_not.join('、') }}
            </div>
          </template>
          <el-empty v-else description="点击左侧剧本查看详情" :image-size="40" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const query = ref('')
const results = ref([])
const playbooks = ref([])
const searching = ref(false)
const loading = ref(true)
const activeResults = ref([])
const selected = ref(null)
const page = ref(1)
const pageSize = ref(10)

const categories = computed(() => [...new Set(playbooks.value.map(p => p.category || '通用'))])
const sevStats = computed(() => {
  const m = { '严重': { color: 'danger' }, '高': { color: 'warning' }, '中': { color: '' }, '低': { color: 'success' }, '信息': { color: 'info' } }
  const counts = {}
  playbooks.value.forEach(p => {
    if (p.severity) counts[p.severity] = (counts[p.severity] || 0) + 1
  })
  return Object.entries(counts).map(([label, count]) => ({ label, count, ...(m[label] || {color: 'info'}) })).sort((a, b) => b.count - a.count)
})
const paginatedPlaybooks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return playbooks.value.slice(start, start + pageSize.value)
})

// 标签英文 → 中文 + 颜色
const CATEGORY_META = {
  privilege:          { label: '权限管理', color: 'danger' },
  misdelete:          { label: '误删防护', color: 'danger' },
  exfiltration:       { label: '数据外泄', color: 'danger' },
  port_exposure:      { label: '端口暴露', color: 'warning' },
  impersonation:      { label: '进程伪装', color: 'warning' },
  monitoring_gap:     { label: '监控覆盖', color: '' },
  network:            { label: '网络安全', color: '' },
  daily_dev:          { label: '日常运维', color: 'success' },
  advisor:            { label: '处置建议', color: 'info' },
  blue_team:          { label: '入侵排查', color: '' },
  detection:          { label: '威胁检测', color: 'warning' },
  log_analysis:       { label: '日志分析', color: '' },
  audit:              { label: '审计合规', color: 'success' },
  webshell:           { label: 'WebShell', color: 'danger' },
  waf:                { label: 'WAF 防护', color: 'warning' },
  system:             { label: '系统加固', color: '' },
  ids:                { label: 'IDS 检测', color: 'info' },
  intrusion:          { label: '入侵响应', color: 'danger' },
  asset_scan:         { label: '资产扫描', color: '' },
  api_security:       { label: 'API 安全', color: 'info' },
  incident_response:  { label: '应急响应', color: 'danger' },
  knowledge_base:     { label: '知识沉淀', color: 'success' },
  resilience:         { label: '弹性防御', color: 'warning' },
  data:               { label: '数据安全', color: 'warning' },
  server:             { label: '服务安全', color: '' },
  false_positive:     { label: '误报校准', color: 'info' },
  process:            { label: '进程管理', color: '' },
  root:               { label: 'Root 操作', color: 'danger' },
  kylin:              { label: '麒麟适配', color: 'info' },
  sigma:              { label: 'Sigma规则', color: '' },
  ioc:                { label: 'IOC匹配', color: 'warning' },
  docker:             { label: '容器安全', color: 'warning' },
  backup:             { label: '备份恢复', color: 'success' },
}

function categoryLabel(cat) {
  return CATEGORY_META[cat]?.label || cat || '通用'
}
function categoryColor(cat) {
  return CATEGORY_META[cat]?.color || 'info'
}
function sevColor(s) { return { '严重':'danger','高':'warning','中':'','低':'success','信息':'info' }[s] || '' }

async function search() {
  if (!query.value.trim()) return
  searching.value = true
  try {
    const res = await api.post('/knowledge/search', { query: query.value.trim(), top_k: 10 }).catch(() => ({ results: [] }))
    results.value = res.results || res.items || []
  } catch { results.value = [] }
  finally { searching.value = false }
}

function viewPlaybook(row) { selected.value = row }
function filterByCategory(cat) { query.value = cat; search() }

onMounted(async () => {
  loading.value = true
  try {
    const res = await api.get('/knowledge/playbooks').catch(() => ({ playbooks: [] }))
    playbooks.value = res.playbooks || res.items || res || []
    if (!Array.isArray(playbooks.value)) playbooks.value = []
  } catch { playbooks.value = [] }
  finally { loading.value = false }
})
</script>

<style scoped>
.result-content { font-size: 13px; line-height: 1.6; color: #555; white-space: pre-wrap; padding: 8px; background: #f9f9f9; border-radius: 4px; }
.cat-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.cat-row:hover { background: #f5f7fa; }
.cat-count { font-size: 12px; color: #999; }
</style>
