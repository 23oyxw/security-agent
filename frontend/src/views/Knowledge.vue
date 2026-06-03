<template>
  <div>
    <el-row :gutter="16">
      <!-- 左侧：搜索与结果 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>📚 安全知识库</span>
              <el-tag type="info">共 {{ playbooks.length }} 条剧本</el-tag>
            </div>
          </template>

          <!-- 搜索 -->
          <div style="margin-bottom:16px">
            <el-input v-model="query" placeholder="搜索安全知识，例如：SSH暴力破解、端口暴露、提权攻击..." clearable @keydown.enter="search" size="large">
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
          <h4 style="margin-bottom:8px">📋 安全剧本</h4>
          <el-table :data="paginatedPlaybooks" stripe size="small" empty-text="暂无剧本">
            <el-table-column prop="id" label="编号" width="120" show-overflow-tooltip />
            <el-table-column prop="title" label="标题" width="200" show-overflow-tooltip />
            <el-table-column prop="category" label="分类" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="categoryColor(row.category)">{{ row.category || '通用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="severity" label="严重级别" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.severity" :type="sevColor(row.severity)" size="small">{{ row.severity }}</el-tag>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" show-overflow-tooltip />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="viewPlaybook(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
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
            <el-descriptions-item label="搜索结果">{{ results.length }}</el-descriptions-item>
            <el-descriptions-item label="分类数">{{ categories.length }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:12px">
            <div v-for="cat in categories" :key="cat" class="cat-row" @click="filterByCategory(cat)">
              <el-tag size="small" :type="categoryColor(cat)">{{ cat }}</el-tag>
              <span class="cat-count">{{ playbooks.filter(p => (p.category || '通用') === cat).length }} 条</span>
            </div>
          </div>
        </el-card>

        <el-card header="选中剧本详情">
          <template v-if="selected">
            <h4 style="margin:0 0 8px">{{ selected.title }}</h4>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="编号">{{ selected.id }}</el-descriptions-item>
              <el-descriptions-item label="分类">{{ selected.category || '通用' }}</el-descriptions-item>
              <el-descriptions-item v-if="selected.severity" label="严重级别">{{ selected.severity }}</el-descriptions-item>
            </el-descriptions>
            <div style="margin-top:12px;font-size:13px;line-height:1.6;white-space:pre-wrap">{{ selected.content || selected.description || '暂无详细内容' }}</div>
          </template>
          <el-empty v-else description="点击剧本查看详情" :image-size="40" />
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
const activeResults = ref([])
const selected = ref(null)
const page = ref(1)
const pageSize = ref(10)

const categories = computed(() => [...new Set(playbooks.value.map(p => p.category || '通用'))])
const paginatedPlaybooks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return playbooks.value.slice(start, start + pageSize.value)
})

function categoryColor(cat) {
  const map = { '网络': '', '系统': 'success', '认证': 'warning', '加固': 'danger', '通用': 'info' }
  return map[cat] || 'info'
}
function sevColor(s) { return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[s] || '' }

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
  try {
    const res = await api.get('/knowledge/playbooks').catch(() => ({ playbooks: [] }))
    playbooks.value = res.playbooks || res.items || res || []
    if (!Array.isArray(playbooks.value)) playbooks.value = []
  } catch { playbooks.value = [] }
})
</script>

<style scoped>
.result-content { font-size: 13px; line-height: 1.6; color: #555; white-space: pre-wrap; padding: 8px; background: #f9f9f9; border-radius: 4px; }
.cat-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.cat-row:hover { background: #f5f7fa; }
.cat-count { font-size: 12px; color: #999; }
</style>