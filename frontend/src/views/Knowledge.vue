<template>
  <div>
    <el-row :gutter="16">
      <!-- 左侧：搜索与结果 + 蓝队方案 -->
      <el-col :span="16">
        <!-- 蓝队方案面板 -->
        <el-card style="margin-bottom:16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🛡️ 蓝队方案学习</span>
              <div style="display:flex;gap:8px;align-items:center">
                <el-tag v-if="blueTeamReport" type="success">已分析 {{ blueTeamReport.total_projects }} 个项目</el-tag>
                <el-button type="primary" size="small" :loading="blueScanning" @click="scanBlueTeam">
                  {{ blueTeamReport ? '重新扫描' : '开始扫描' }}
                </el-button>
              </div>
            </div>
          </template>

          <!-- 蓝队项目清单 -->
          <el-collapse v-model="activeBlueRepos">
            <el-collapse-item name="repos">
              <template #title>
                <span style="font-weight:500">📋 蓝队开源项目清单 ({{ blueRepos.length }})</span>
              </template>
              <el-table :data="blueRepos" size="small" stripe empty-text="加载中...">
                <el-table-column prop="name" label="项目" width="130" />
                <el-table-column prop="category" label="分类" width="110">
                  <template #default="{ row }">
                    <el-tag size="small" :type="blueCategoryColor(row.category)">{{ row.category }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="说明" show-overflow-tooltip />
                <el-table-column label="链接" width="80">
                  <template #default="{ row }">
                    <el-button text type="primary" size="small" @click="openUrl(row.github || row.url)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>

          <!-- 扫描结果 -->
          <div v-if="blueTeamReport" style="margin-top:12px">
            <el-row :gutter="12">
              <el-col :span="8">
                <el-statistic title="蓝队技能" :value="blueTeamReport.total_skills">
                  <template #prefix><el-icon color="#409eff"><Key /></el-icon></template>
                </el-statistic>
              </el-col>
              <el-col :span="8">
                <el-statistic title="优化建议" :value="blueTeamReport.total_patches">
                  <template #prefix><el-icon color="#e6a23c"><MagicStick /></el-icon></template>
                </el-statistic>
              </el-col>
              <el-col :span="8">
                <el-statistic title="训练场景" :value="blueTeamReport.total_scenarios">
                  <template #prefix><el-icon color="#67c23a"><Reading /></el-icon></template>
                </el-statistic>
              </el-col>
            </el-row>

            <!-- 项目技能详情 -->
            <el-collapse v-model="activeBlueSkills" style="margin-top:12px">
              <el-collapse-item v-for="p in blueTeamReport.projects" :key="p.name" :name="p.name">
                <template #title>
                  <div style="display:flex;align-items:center;gap:8px">
                    <el-tag size="small" :type="blueCategoryColor(p.category)">{{ p.category }}</el-tag>
                    <span style="font-weight:500">{{ p.name }}</span>
                    <el-tag size="small" type="info">{{ p.skills?.length || 0 }} 技能</el-tag>
                  </div>
                </template>
                <div style="padding:4px 0">
                  <h5 style="margin:8px 0 4px;color:#409eff">🔍 蓝队技能</h5>
                  <div v-for="(skill, si) in p.skills" :key="si" class="blue-skill-item">{{ skill }}</div>
                  <div v-if="!p.skills?.length" style="color:#999;font-size:12px">暂无技能数据</div>

                  <h5 style="margin:12px 0 4px;color:#e6a23c">💡 优化建议</h5>
                  <div v-for="(patch, pi) in p.patches" :key="pi" class="blue-patch-item">{{ patch }}</div>
                  <div v-if="!p.patches?.length" style="color:#999;font-size:12px">暂无优化建议</div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <el-empty v-else-if="!blueScanning" description="点击「开始扫描」让 LLM 分析蓝队开源项目" :image-size="40" />
        </el-card>

        <!-- 今日训练场景 -->
        <el-card v-if="todayTraining?.today" style="margin-bottom:16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🎯 今日蓝队训练</span>
              <el-tag type="info">第 {{ todayTraining.day_index + 1 }}/{{ todayTraining.total_scenarios }} 场景</el-tag>
            </div>
          </template>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="场景名">{{ todayTraining.today.title }}</el-descriptions-item>
            <el-descriptions-item label="难度">
              <el-tag size="small" :type="difficultyColor(todayTraining.today.difficulty)">{{ todayTraining.today.difficulty }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="来源项目">{{ todayTraining.today.source_project }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ todayTraining.today.category }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:12px;font-size:13px;line-height:1.6;white-space:pre-wrap;background:#f9f9f9;padding:12px;border-radius:4px">{{ todayTraining.today.description }}</div>
        </el-card>

        <!-- 安全知识库搜索 -->
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
            <el-divider style="margin:8px 0" />
            <el-descriptions-item label="蓝队项目">{{ blueRepos.length }}</el-descriptions-item>
            <el-descriptions-item label="蓝队技能">{{ blueTeamReport?.total_skills || 0 }}</el-descriptions-item>
            <el-descriptions-item label="训练场景">{{ blueTeamReport?.total_scenarios || 0 }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:12px">
            <div v-for="cat in categories" :key="cat" class="cat-row" @click="filterByCategory(cat)">
              <el-tag size="small" :type="categoryColor(cat)">{{ cat }}</el-tag>
              <span class="cat-count">{{ playbooks.filter(p => (p.category || '通用') === cat).length }} 条</span>
            </div>
          </div>
        </el-card>

        <!-- 蓝队分类统计 -->
        <el-card header="蓝队项目分类" style="margin-bottom:16px">
          <div v-for="cat in blueCategories" :key="cat" class="cat-row">
            <el-tag size="small" :type="blueCategoryColor(cat)">{{ cat }}</el-tag>
            <span class="cat-count">{{ blueRepos.filter(r => r.category === cat).length }} 个</span>
          </div>
          <el-empty v-if="!blueRepos.length" description="暂无蓝队项目" :image-size="30" />
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

// 蓝队方案状态
const blueRepos = ref([])
const blueTeamReport = ref(null)
const blueScanning = ref(false)
const activeBlueRepos = ref([])
const activeBlueSkills = ref([])
const todayTraining = ref(null)

const categories = computed(() => [...new Set(playbooks.value.map(p => p.category || '通用'))])
const blueCategories = computed(() => [...new Set(blueRepos.value.map(r => r.category))])
const paginatedPlaybooks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return playbooks.value.slice(start, start + pageSize.value)
})

function categoryColor(cat) {
  const map = { '网络': '', '系统': 'success', '认证': 'warning', '加固': 'danger', '通用': 'info' }
  return map[cat] || 'info'
}
function sevColor(s) { return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[s] || '' }
function difficultyColor(d) {
  if (!d) return 'info'
  if (d.includes('高')) return 'danger'
  if (d.includes('中')) return 'warning'
  return 'success'
}
function blueCategoryColor(cat) {
  const map = {
    '入侵排查': 'danger',
    '威胁检测规则': 'warning',
    '资产扫描': '',
    '蓝队知识库': 'success',
    'API限流': 'info',
    '熔断机制': 'warning',
    '日志分析': '',
  }
  return map[cat] || 'info'
}

function openUrl(url) {
  if (url) window.open(url, '_blank')
}

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

// 蓝队：加载项目清单
async function loadBlueRepos() {
  try {
    const res = await api.get('/knowledge/blue-team/repos').catch(() => ({ repos: [] }))
    blueRepos.value = res.repos || []
  } catch { blueRepos.value = [] }
}

// 蓝队：扫描分析
async function scanBlueTeam() {
  blueScanning.value = true
  try {
    const res = await api.post('/knowledge/blue-team/scan').catch(() => null)
    if (res) {
      blueTeamReport.value = res
      // 重新加载训练场景
      await loadTraining()
    }
  } catch { /* ignore */ }
  finally { blueScanning.value = false }
}

// 蓝队：加载训练场景
async function loadTraining() {
  try {
    const res = await api.get('/knowledge/blue-team/training').catch(() => null)
    if (res && !res.error) {
      todayTraining.value = res
    }
  } catch { /* ignore */ }
}

onMounted(async () => {
  // 并行加载
  await Promise.all([
    (async () => {
      try {
        const res = await api.get('/knowledge/playbooks').catch(() => ({ playbooks: [] }))
        playbooks.value = res.playbooks || res.items || res || []
        if (!Array.isArray(playbooks.value)) playbooks.value = []
      } catch { playbooks.value = [] }
    })(),
    loadBlueRepos(),
    loadTraining(),
  ])
})
</script>

<style scoped>
.result-content { font-size: 13px; line-height: 1.6; color: #555; white-space: pre-wrap; padding: 8px; background: #f9f9f9; border-radius: 4px; }
.cat-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.cat-row:hover { background: #f5f7fa; }
.cat-count { font-size: 12px; color: #999; }
.blue-skill-item { font-size: 13px; padding: 4px 0 4px 12px; border-left: 3px solid #409eff; margin-bottom: 4px; line-height: 1.5; }
.blue-patch-item { font-size: 13px; padding: 4px 0 4px 12px; border-left: 3px solid #e6a23c; margin-bottom: 4px; line-height: 1.5; }
</style>