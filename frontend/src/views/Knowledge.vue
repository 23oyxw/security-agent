<template>
  <div class="knowledge">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
    >
      <template #actions>
        <PipelineBtn action="refresh" size="small" @click="refreshKnowledge" />
      </template>
    </PageHeader>

    <div class="l1-knowledge-banner reveal-item">
      <div class="l1-banner-head">
        <div>
          <span class="l1-badge">L1 · 灵敏检索 Sensitive RAG</span>
          <p class="l1-desc">规范 · 流程 · 故障 · 调度 · 工具 — 意图扩展 + hybrid 检索 · 零执行</p>
        </div>
        <div v-if="l1Meta.sensitivity" class="l1-sensitivity" :class="'sens-' + l1Meta.sensitivity">
          灵敏度 {{ l1Meta.sensitivity }}
        </div>
      </div>
      <div v-if="l1Meta.intent_tags?.length" class="intent-row">
        <span class="intent-label">意图 Intent:</span>
        <el-tag v-for="t in l1Meta.intent_tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
      </div>
    </div>

    <div class="wiki-sync-panel reveal-item">
      <div class="wiki-sync-head">
        <div>
          <h3>Wiki 知识同步</h3>
          <p class="wiki-sync-desc">边界对抗集 + 架构文档 + 蓝队种子 → 本地索引；有 Gitee Token 时优先远程 Wiki</p>
        </div>
        <el-button type="primary" size="small" :loading="wikiSyncing" @click="refreshKnowledge">
          同步 Wiki 索引
        </el-button>
      </div>
      <div class="wiki-sync-stats">
        <el-tag :type="wikiStatus === '已同步' ? 'success' : 'warning'" effect="plain">
          {{ wikiStatus }}
        </el-tag>
        <span v-if="wikiMeta.doc_count">文档 {{ wikiMeta.doc_count }} 篇</span>
        <span v-if="wikiMeta.synced_at">上次 {{ wikiMeta.synced_at }}</span>
        <span v-if="wikiMeta.source">来源 {{ wikiMeta.source }}</span>
        <span v-if="wikiBoundary.matrix_cases">边界矩阵 {{ wikiBoundary.matrix_cases }} + PE {{ wikiBoundary.probe_count || 0 }}</span>
      </div>
      <p v-if="wikiMeta.fallback" class="wiki-sync-hint">{{ wikiMeta.fallback }}</p>
    </div>

    <div class="search-section">
      <div class="search-bar">
        <el-input
          v-model="query"
          placeholder="搜索安全知识，如：后门排查、日志分析、SSH 加固..."
          size="large"
          clearable
          @keydown.enter="doSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" :loading="searching" @click="doSearch">
          <el-icon style="margin-right:4px"><Search /></el-icon> 搜索
        </el-button>
      </div>
        <div class="search-tags">
        <span class="search-tag-label">热门搜索:</span>
        <span v-for="tag in hotTags" :key="tag" class="search-tag" @click="query = tag; doSearch()">{{ tag }}</span>
        <span v-for="t in intentFilters" :key="'intent-' + t" class="search-tag intent-tag" @click="query = t; doSearch()">{{ t }}</span>
      </div>
      <div class="blue-team-tags">
        <span class="blue-team-tag-label">蓝队知识:</span>
        <span v-for="bt in blueTeamTags" :key="bt.key" class="blue-team-tag" :style="{ background: bt.color + '15', color: bt.color, borderColor: bt.color + '30' }" @click="query = bt.key; doSearch()">
          <el-icon :size="12"><component :is="bt.icon" /></el-icon>
          {{ bt.label }}
        </span>
      </div>
    </div>

    <div v-if="results.length" class="results-section" v-loading="searching">
      <div class="results-meta">
        <span class="results-count">共 {{ results.length }} 条结果</span>
        <span class="results-time">{{ searchTime }}ms</span>
      </div>
      <div class="results-list">
        <div v-for="(r, i) in results" :key="i" class="result-card" @click="openDetail(r)">
          <div class="result-header">
            <span class="result-source" :class="r.source">{{ r.source }}</span>
            <span class="result-score" v-if="r.score">相关度 {{ (r.score * 100).toFixed(0) }}%</span>
          </div>
          <h3 class="result-title">{{ r.title }}</h3>
          <p class="result-snippet">{{ r.content?.slice(0, 200) }}{{ r.content?.length > 200 ? '...' : '' }}</p>
          <div v-if="r.tags?.length" class="result-tags">
            <span v-for="tag in r.tags.slice(0, 5)" :key="tag" class="result-tag">{{ tag }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!searching && !initial" class="empty-state">
      <el-icon :size="48" color="var(--color-neutral-200)"><Reading /></el-icon>
      <p>输入关键词搜索安全知识库</p>
    </div>

    <div v-if="initial && !results.length && !searching" class="browse-section">
      <div class="section-card">
        <div class="section-card-header">
          <div style="display:flex;align-items:center;gap:12px">
            <h3>知识分类</h3>
            <el-tag v-if="wikiStatus === '已同步'" type="success" size="small">Wiki ✅</el-tag>
            <el-tag v-else type="warning" size="small">仅 Playbooks · Wiki 待同步</el-tag>
          </div>
        </div>
        <div class="category-grid">
          <div v-for="cat in categories" :key="cat.key" class="category-card" @click="query = cat.key; doSearch()">
            <div class="category-icon" :style="{ background: cat.color + '15', color: cat.color }">
              <el-icon :size="20"><component :is="cat.icon" /></el-icon>
            </div>
            <span class="category-name">{{ cat.label }}</span>
            <span class="category-count">{{ cat.count }} 篇</span>
          </div>
        </div>
      </div>

      <!-- 蓝队知识推荐 -->
      <div class="section-card">
        <div class="section-card-header">
          <h3>🔥 蓝队知识推荐</h3>
          <el-button size="small" type="primary" plain @click="$router.push('/blue-team')">蓝队安全 →</el-button>
        </div>
        <div class="recommend-grid">
          <div v-for="rec in blueTeamRecommend" :key="rec.key" class="recommend-card" @click="query = rec.key; doSearch()">
            <div class="recommend-icon" :style="{ background: rec.color + '15', color: rec.color }">
              <el-icon :size="18"><component :is="rec.icon" /></el-icon>
            </div>
            <div class="recommend-body">
              <span class="recommend-title">{{ rec.label }}</span>
              <span class="recommend-desc">{{ rec.desc }}</span>
            </div>
            <div class="recommend-heat">
              <span class="heat-bar" :style="{ width: rec.heat + '%' }"></span>
              <span class="heat-value">{{ rec.heat }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 知识热度排行 -->
      <div class="section-card">
        <div class="section-card-header">
          <h3>📊 知识热度排行</h3>
        </div>
        <div class="hot-list">
          <div v-for="(item, i) in hotKnowledge" :key="item.key" class="hot-item" @click="query = item.key; doSearch()">
            <span class="hot-rank" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
            <span class="hot-label">{{ item.label }}</span>
            <div class="hot-bar-wrap">
              <div class="hot-bar" :style="{ width: item.heat + '%' }"></div>
            </div>
            <span class="hot-count">{{ item.count }}次</span>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="detailVisible" :title="detailItem?.title" width="720px" class="knowledge-detail-dialog">
      <div v-if="detailItem" class="detail-body">
        <div class="detail-meta">
          <span class="detail-source" :class="detailItem.source">{{ detailItem.source }}</span>
          <span v-if="detailItem.score" class="detail-score">相关度 {{ (detailItem.score * 100).toFixed(0) }}%</span>
        </div>
        <div v-if="detailItem.tags?.length" class="detail-tags">
          <span v-for="tag in detailItem.tags" :key="tag" class="detail-tag">{{ tag }}</span>
        </div>
        <div class="detail-content" v-if="detailItem.content" v-html="renderMarkdown(detailItem.content || '')"></div>
        <div v-else class="detail-content" style="color:var(--color-neutral-400)">暂无正文</div>
        <div v-if="detailItem.do_not?.length" class="detail-do-not" style="margin-top:12px;padding:8px 12px;background:var(--color-danger-bg);border-radius:6px;font-size:13px">
          ⚠️ 禁止: {{ detailItem.do_not.join(' · ') }}
        </div>
        <div v-if="detailItem.suggested_actions?.length" class="detail-suggest" style="margin-top:8px;padding:8px 12px;background:var(--color-success-bg);border-radius:6px;font-size:13px">
          ✅ 建议: {{ detailItem.suggested_actions.join(' · ') }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'
import PageHeader from '../components/common/PageHeader.vue'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { NAV_PAGES } from '../constants/navigation'

const pageMeta = NAV_PAGES.knowledge

const query = ref('')
const results = ref([])
const searching = ref(false)
const initial = ref(true)
const searchTime = ref(0)
const detailVisible = ref(false)
const detailItem = ref(null)
const l1Meta = ref({ sensitivity: '', intent_tags: [], expanded_query: '' })

const intentFilters = ['规范', '流程', '故障', '调度', '工具', '边界', '入侵', '加固']

const hotTags = ['后门排查', '日志分析', 'SSH 加固', '入侵检测', '应急响应', '文件完整性', '网络监控', '权限提升']

const blueTeamTags = [
  { key: 'webshell', label: 'Webshell 检测', icon: 'WarningFilled', color: '#ef4444' },
  { key: 'sigma', label: 'Sigma 规则', icon: 'List', color: '#f59e0b' },
  { key: 'ioc', label: 'IOC 匹配', icon: 'Search', color: '#8b5cf6' },
  { key: 'auditd', label: 'Auditd 规则', icon: 'Monitor', color: '#10b981' },
  { key: 'file_integrity', label: '文件完整性', icon: 'CircleCheck', color: '#06b6d4' },
  { key: 'kernel_hardening', label: '内核加固', icon: 'Lock', color: '#3b82f6' },
]

const categories = ref([
  { key: '入侵排查', label: '入侵排查', icon: 'Search', color: '#ef4444', count: 0 },
  { key: '日志分析', label: '日志分析', icon: 'Document', color: '#f59e0b', count: 0 },
  { key: '系统加固', label: '系统加固', icon: 'Lock', color: '#10b981', count: 0 },
  { key: '网络监控', label: '网络监控', icon: 'Connection', color: '#4f6ef7', count: 0 },
  { key: '应急响应', label: '应急响应', icon: 'AlarmClock', color: '#8b5cf6', count: 0 },
  { key: '合规检查', label: '合规检查', icon: 'CircleCheck', color: '#06b6d4', count: 0 },
])
const wikiStatus = ref('未同步')
const wikiSyncing = ref(false)
const wikiMeta = ref({})
const wikiBoundary = ref({})

const blueTeamRecommend = [
  { key: 'webshell', label: 'Webshell 检测', desc: '检测 PHP/JSP/ASP 一句话木马、大马', icon: 'WarningFilled', color: '#ef4444', heat: 95 },
  { key: 'sigma', label: 'Sigma 规则', desc: 'SIEM 通用检测规则转换与匹配', icon: 'List', color: '#f59e0b', heat: 88 },
  { key: 'ioc', label: 'IOC 威胁情报', desc: 'IP/域名/Hash 恶意指标匹配', icon: 'Search', color: '#8b5cf6', heat: 82 },
  { key: 'auditd', label: 'Auditd 审计', desc: 'Linux 内核级审计规则配置', icon: 'Monitor', color: '#10b981', heat: 76 },
  { key: 'file_integrity', label: '文件完整性', desc: '关键文件变更监控与告警', icon: 'CircleCheck', color: '#06b6d4', heat: 70 },
  { key: 'kernel_hardening', label: '内核加固', desc: 'sysctl 内核参数安全加固', icon: 'Lock', color: '#3b82f6', heat: 65 },
]

const hotKnowledge = [
  { key: 'Webshell 检测', label: 'Webshell 检测与清除', heat: 100, count: 156 },
  { key: '日志分析', label: 'Linux 日志分析技巧', heat: 92, count: 143 },
  { key: 'SSH 加固', label: 'SSH 安全加固指南', heat: 85, count: 128 },
  { key: '后门排查', label: '服务器后门排查方法', heat: 78, count: 112 },
  { key: '入侵检测', label: '入侵检测与应急响应', heat: 70, count: 98 },
  { key: '文件完整性', label: '文件完整性监控', heat: 62, count: 85 },
  { key: '网络监控', label: '网络流量异常监控', heat: 55, count: 72 },
  { key: '权限提升', label: '权限提升检测与防御', heat: 48, count: 60 },
]

async function doSearch() {
  if (!query.value.trim()) return
  searching.value = true
  initial.value = false
  const t0 = Date.now()
  try {
    const [l1Res, legacyRes] = await Promise.allSettled([
      api.post('/l1/knowledge/retrieve', { message: query.value, top_k: 10 }),
      api.get('/knowledge/search', { params: { q: query.value } }),
    ])
    if (l1Res.status === 'fulfilled' && l1Res.value?.refs?.length) {
      l1Meta.value = {
        sensitivity: l1Res.value.sensitivity || 'normal',
        intent_tags: l1Res.value.intent_tags || [],
        expanded_query: l1Res.value.expanded_query || '',
      }
      results.value = l1Res.value.refs.map(r => ({
        id: r.id,
        title: r.title,
        content: r.snippet,
        score: r.score,
        source: r.source,
        tags: r.category ? [r.category] : [],
        severity: r.severity,
        suggested_actions: r.suggested_actions,
        do_not: r.do_not,
      }))
    } else if (legacyRes.status === 'fulfilled') {
      l1Meta.value = { sensitivity: 'normal', intent_tags: [], expanded_query: '' }
      results.value = legacyRes.value.results || []
    } else {
      results.value = []
    }
    searchTime.value = Date.now() - t0
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.message || '未知'))
  } finally {
    searching.value = false
  }
}

function openDetail(item) {
  detailItem.value = item
  detailVisible.value = true
}

function renderMarkdown(content) {
  if (!content) return ''
  return content
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code>$2</code></pre>')
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/## (.+)/g, '<h3>$1</h3>')
    .replace(/# (.+)/g, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

async function refreshKnowledge() {
  wikiSyncing.value = true
  try {
    const res = await api.post('/knowledge/refresh')
    wikiMeta.value = res || {}
    wikiStatus.value = res?.ok ? '已同步' : '同步失败'
    ElMessage.success(`Wiki 已同步：${res.doc_count || 0} 篇文档`)
    await loadKnowledgeStats()
    await loadWikiStatus()
  } catch (e) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message || '未知'))
  } finally {
    wikiSyncing.value = false
  }
}

async function loadWikiStatus() {
  try {
    const st = await api.get('/knowledge/wiki-status')
    wikiMeta.value = { ...wikiMeta.value, ...(st.last_sync || {}), doc_count: st.index?.doc_count }
    wikiBoundary.value = st.boundary || {}
    if (st.index_loaded && (st.index?.doc_count || 0) > 0) {
      wikiStatus.value = '已同步'
    }
  } catch { /* offline */ }
}

async function loadKnowledgeStats() {
  for (const cat of categories.value) {
    try {
      const res = await api.get('/knowledge/search', { params: { q: cat.key } })
      cat.count = res.total || (res.results?.length || 0)
    } catch { cat.count = 0 }
  }
  try {
    const res = await api.get('/knowledge/search', { params: { q: 'test' } })
    wikiStatus.value = (res.results?.some(r => r.source === 'wiki')) ? '已同步' : '待同步'
  } catch { wikiStatus.value = '待同步' }
}

onMounted(async () => {
  await loadWikiStatus()
  loadKnowledgeStats()
})
</script>

<style scoped>
.knowledge {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.wiki-sync-panel {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
}

.wiki-sync-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
}

.wiki-sync-head h3 {
  margin: 0 0 4px;
  font-size: var(--text-base);
}

.wiki-sync-desc {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.wiki-sync-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.wiki-sync-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.l1-knowledge-banner {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-primary-200);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(14, 165, 233, 0.05));
}

.l1-banner-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
}

.l1-badge {
  font-size: var(--text-sm);
  font-weight: 800;
  color: var(--color-primary-600);
}

.l1-desc {
  margin: 4px 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.l1-sensitivity {
  font-size: var(--text-sm);
  font-weight: 700;
  padding: 4px 10px;
  border-radius: var(--radius-full);
}
.sens-high { background: var(--color-success-bg); color: var(--color-success); }
.sens-medium { background: var(--color-warning-bg); color: var(--color-warning); }
.sens-normal { background: var(--color-neutral-100); color: var(--color-neutral-500); }

.intent-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: var(--space-3);
}
.intent-label { font-size: var(--text-xs); color: var(--color-text-muted); }

.search-tag.intent-tag {
  border: 1px dashed var(--color-primary-300);
  background: rgba(59, 130, 246, 0.06);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-neutral-900);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin: var(--space-1) 0 0;
}

.page-actions {
  display: flex;
  gap: var(--space-2);
}

/* ---- 搜索区 ---- */
.search-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.search-bar {
  display: flex;
  gap: var(--space-2);
}

.search-bar .el-input {
  flex: 1;
}

/* 搜索框聚焦光晕 */
.search-bar :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 2px var(--color-primary-200) inset, var(--shadow-glow-primary) !important;
}

.search-tags {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.search-tag-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.search-tag {
  font-size: var(--text-xs);
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-neutral-100);
  color: var(--color-neutral-600);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.search-tag:hover {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
}

.blue-team-tags {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.blue-team-tag-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  font-weight: 600;
}

.blue-team-tag {
  font-size: var(--text-xs);
  padding: 2px 10px;
  border-radius: var(--radius-full);
  border: 1px solid;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all var(--duration-fast) var(--ease-out);
}

.blue-team-tag:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
  box-shadow: var(--shadow-glow-primary);
}

/* ---- 搜索结果 ---- */
.results-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.results-meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.result-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  animation: slide-up var(--duration-normal) var(--ease-out) both;
}

.result-card:nth-child(1) { animation-delay: 0ms; }
.result-card:nth-child(2) { animation-delay: 50ms; }
.result-card:nth-child(3) { animation-delay: 100ms; }
.result-card:nth-child(n+4) { animation-delay: 150ms; }

.result-card:hover {
  border-color: var(--color-primary-200);
  box-shadow: var(--shadow-sm);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.result-source {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 1px 8px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.result-source.blue_team { background: var(--color-info-bg); color: var(--color-info); }
.result-source.playbook { background: var(--color-success-bg); color: var(--color-success); }
.result-source.sigma { background: var(--color-warning-bg); color: var(--color-warning); }
.result-source.ioc { background: var(--color-danger-bg); color: var(--color-danger); }

.result-score {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.result-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
  margin: 0 0 var(--space-2);
  line-height: var(--leading-snug);
}

.result-snippet {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  line-height: var(--leading-relaxed);
  margin: 0 0 var(--space-2);
}

.result-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.result-tag {
  font-size: var(--text-xs);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-neutral-50);
  color: var(--color-neutral-500);
}

/* ---- 空状态 ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--color-neutral-300);
}

.empty-state p {
  margin: 0;
  font-size: var(--text-sm);
}

/* ---- 分类浏览 ---- */
.browse-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.section-card-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.section-card-header h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
  letter-spacing: var(--tracking-tight);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
}

.category-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.category-card:hover {
  border-color: var(--color-primary-200);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.category-card:hover .category-icon {
  transform: rotate(-5deg) scale(1.1);
}

.category-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--duration-normal) var(--ease-spring);
}

.category-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
}

.category-count {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

/* ---- 蓝队知识推荐 ---- */
.recommend-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
}

.recommend-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.recommend-card:hover {
  border-color: var(--color-primary-200);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.recommend-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.recommend-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recommend-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.recommend-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  line-height: var(--leading-relaxed);
}

.recommend-heat {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.heat-bar {
  height: 4px;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--color-primary-400), var(--color-primary-600));
  transition: width var(--duration-slow) var(--ease-out);
}

.heat-value {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-primary-500);
  font-variant-numeric: tabular-nums;
}

/* ---- 知识热度排行 ---- */
.hot-list {
  padding: var(--space-3) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hot-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.hot-item:hover {
  background: var(--color-neutral-50);
}

.hot-rank {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--color-neutral-400);
  background: var(--color-neutral-100);
  flex-shrink: 0;
}

.hot-rank.rank-1 { background: #fef3c7; color: #d97706; }
.hot-rank.rank-2 { background: #f1f5f9; color: #64748b; }
.hot-rank.rank-3 { background: #fef2f2; color: #dc2626; }

.hot-label {
  font-size: var(--text-sm);
  color: var(--color-neutral-700);
  font-weight: 500;
  flex: 1;
  min-width: 0;
}

.hot-bar-wrap {
  flex: 1;
  max-width: 120px;
  height: 6px;
  background: var(--color-neutral-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.hot-bar {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--color-primary-400), var(--color-primary-600));
  transition: width var(--duration-slow) var(--ease-out);
}

.hot-count {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  font-variant-numeric: tabular-nums;
  width: 48px;
  text-align: right;
}

/* ---- 详情弹窗 ---- */
.detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.detail-meta {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.detail-source {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 1px 8px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.detail-source.blue_team { background: var(--color-info-bg); color: var(--color-info); }
.detail-source.playbook { background: var(--color-success-bg); color: var(--color-success); }
.detail-source.sigma { background: var(--color-warning-bg); color: var(--color-warning); }
.detail-source.ioc { background: var(--color-danger-bg); color: var(--color-danger); }

.detail-score {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.detail-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.detail-tag {
  font-size: var(--text-xs);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-neutral-50);
  color: var(--color-neutral-500);
}

.detail-content {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--color-neutral-700);
}

.detail-content :deep(h2) {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-neutral-900);
  margin: var(--space-4) 0 var(--space-2);
}

.detail-content :deep(h3) {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-neutral-800);
  margin: var(--space-3) 0 var(--space-1);
}

.detail-content :deep(h4) {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
  margin: var(--space-2) 0 var(--space-1);
}

.detail-content :deep(.md-code-block) {
  background: var(--color-neutral-900);
  color: #e2e5ef;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  margin: var(--space-2) 0;
}

.detail-content :deep(code) {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  background: var(--color-neutral-100);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
}

.detail-content :deep(strong) {
  font-weight: 600;
  color: var(--color-neutral-900);
}

@media (max-width: 768px) {
  .category-grid { grid-template-columns: repeat(2, 1fr); }
  .recommend-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
