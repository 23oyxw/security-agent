<template>
  <div class="trace-view">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
      :agent="pageMeta.agent"
    >
      <template #actions>
        <el-select v-model="pageSize" size="small" style="width:80px" @change="fetchTraces">
          <el-option :value="10" label="10条" />
          <el-option :value="20" label="20条" />
          <el-option :value="50" label="50条" />
        </el-select>
        <PipelineBtn action="refresh" size="small" :loading="loading" @click="fetchTraces" />
        <el-popconfirm title="清除 30 天前的旧 Trace？" @confirm="cleanupOld">
          <template #reference>
            <el-button size="small" type="warning" plain>清理旧记录</el-button>
          </template>
        </el-popconfirm>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div v-for="s in summaryCards" :key="s.label" class="stat-card">
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-suffix">{{ s.suffix }}</div>
      </div>
      <div class="stat-card blue-team-stat">
        <div class="stat-value">{{ blueTeamAuditCount }}</div>
        <div class="stat-label">蓝队审计事件</div>
        <div class="stat-suffix">条</div>
      </div>
    </div>

    <!-- 架构分层说明 -->
    <ArchitectureLayers highlight="trace" :default-expanded="false" />

    <!-- 可视化分析区域 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>追踪分析仪表盘</h3>
        <div class="section-card-actions">
          <el-radio-group v-model="chartView" size="small">
            <el-radio-button value="timeline">时间线</el-radio-button>
            <el-radio-button value="dag">DAG 依赖图</el-radio-button>
            <el-radio-button value="heatmap">热力图</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="chart-area">
        <div ref="traceChart" class="trace-chart" v-loading="chartLoading"></div>
        <div v-if="!traces.length && !chartLoading" class="chart-empty">
          <el-icon :size="32" color="var(--color-neutral-300)"><DataAnalysis /></el-icon>
          <p>暂无追踪数据</p>
        </div>
      </div>
    </div>

    <!-- 追踪记录表格 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>追踪记录</h3>
        <span class="last-refresh">上次刷新: {{ lastRefreshed || '—' }}</span>
      </div>
      <div class="table-wrap">
        <el-table :data="traces" v-loading="loading" stripe size="small" row-key="trace_id" empty-text="暂无溯源记录" @selection-change="onTraceSelect">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="trace_id" label="Trace ID" width="180" show-overflow-tooltip />
          <el-table-column label="降级" width="72">
            <template #default="{ row }">
              <el-tag v-if="row.degradation_level && row.degradation_level !== 'S0'" size="small" type="warning">{{ row.degradation_level }}</el-tag>
              <span v-else class="degradation-s0">S0</span>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">
              <div class="trace-time">{{ displayTime(row) }}</div>
              <div class="trace-time-relative">{{ relativeTime(row.timestamp_raw || row.timestamp) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="阶段" width="72">
            <template #default="{ row }">
              <el-tag size="small" class="stage-count">{{ row.stage_count ?? (row.nodes || []).length }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <span class="status-indicator" :class="row.status === 'success' || row.status === 'allow' ? 'success' : 'warning'">
                <span class="status-dot"></span>
                {{ row.status || '完成' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="target" label="目标" show-overflow-tooltip min-width="160" />
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <div class="action-btns">
                <el-button size="small" text type="primary" @click="openDetail(row)">详情</el-button>
                <el-button size="small" text type="primary" @click="exportTrace(row.trace_id, 'text')">纪要</el-button>
                <el-button size="small" text type="success" @click="exportTrace(row.trace_id, 'html')">分析</el-button>
                <el-button size="small" text type="info" @click="exportTrace(row.trace_id, 'json')">JSON</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="selectedTraceIds.length" class="batch-bar">
          <el-button type="danger" size="small" @click="batchDeleteTraces">删除选中 ({{ selectedTraceIds.length }})</el-button>
          <el-button size="small" @click="selectedTraceIds = []">取消选择</el-button>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 · 按五层分组 -->
    <el-dialog v-model="detailOpen" :title="`Trace 卷宗 · ${detailRow?.trace_id || ''}`" width="860px" destroy-on-close class="trace-detail-dialog">
      <div v-loading="detailLoading" class="detail-body">
        <el-empty v-if="!detailLoading && !detailLayerGroups.length" description="无阶段数据，可导出「纪要」或「分析图」" />
        <template v-else>
          <div class="trace-layer-stack" style="max-height:480px;overflow-y:auto">
            <section v-for="group in detailLayerGroups" :key="group.layer" class="trace-layer-section">
              <header class="trace-layer-head" :style="{ '--layer-accent': group.accent }">
                <span class="trace-layer-id">{{ group.layer }}</span>
                <div class="trace-layer-titles">
                  <span class="trace-layer-cn">{{ group.cn }}</span>
                  <span class="trace-layer-en">{{ group.en }}</span>
                </div>
                <span class="trace-layer-agent">{{ group.agent }}</span>
                <span class="trace-layer-count">{{ group.nodes.length }} 步</span>
              </header>
              <div class="stage-timeline stage-timeline--layer">
                <div
                  v-for="(node, i) in group.nodes"
                  :key="node.node_id || `${group.layer}-${i}`"
                  class="stage-node"
                  :style="{ '--node-index': i, '--layer-accent': group.accent }"
                >
                  <div class="stage-node-marker" :class="node.statusType || (node.status === 'success' ? 'success' : 'warning')">
                    <el-icon v-if="(node.statusType || node.status) === 'success'" :size="14"><CircleCheck /></el-icon>
                    <el-icon v-else :size="14"><WarningFilled /></el-icon>
                  </div>
                  <div class="stage-node-card" :class="{ 'is-tool': node.isTool }">
                    <div class="stage-node-header">
                      <div class="stage-node-title-wrap">
                        <span class="stage-node-name">{{ node.displayTitle || node.name }}</span>
                        <span v-if="node.toolLabel" class="stage-node-tool">{{ node.toolLabel }}</span>
                      </div>
                      <div class="stage-node-badges">
                        <el-tag size="small" effect="plain" :style="{ borderColor: group.accent, color: group.accent }">
                          {{ group.layer }} · {{ node.layerCn || group.cn }}
                        </el-tag>
                        <span class="stage-node-status" :class="'is-' + (node.statusType || 'success')">
                          {{ node.statusCn }} / {{ node.statusEn }}
                        </span>
                        <span v-if="node.duration_ms" class="stage-node-duration">{{ Number(node.duration_ms).toFixed(0) }}ms</span>
                      </div>
                    </div>
                    <div class="stage-node-subline">{{ node.displaySub }}</div>
                    <div class="stage-node-desc">{{ traceNodeDesc(node) }}</div>
                  </div>
                </div>
              </div>
            </section>
          </div>
          <!-- 摘要信息 -->
          <el-descriptions v-if="detailSummary && Object.keys(detailSummary).length" :column="2" size="small" border class="detail-summary">
            <el-descriptions-item v-for="(v, k) in detailSummary" :key="k" :label="String(k)">{{ formatSummaryVal(v) }}</el-descriptions-item>
          </el-descriptions>
          <!-- 导出按钮 -->
          <div class="detail-actions">
            <el-button type="primary" size="small" @click="exportTrace(detailRow.trace_id, 'text')">导出执行纪要 (.txt)</el-button>
            <el-button type="success" size="small" @click="exportTrace(detailRow.trace_id, 'html')">导出可视化分析 (.html)</el-button>
            <el-button size="small" text type="info" @click="goL5Analysis">L5 链路分析</el-button>
            <el-button size="small" text type="info" @click="exportTrace(detailRow.trace_id, 'json')">JSON（调试）</el-button>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  chartTooltip, categoryAxis, valueAxis,
  pageChartGradient,
} from '../utils/chartTheme'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingTime, formatRelativeBeijing } from '../utils/formatTime'
import { downloadBlob, fetchWithAuth } from '../utils/download'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'
import PageHeader from '../components/common/PageHeader.vue'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { NAV_PAGES } from '../constants/navigation'
import { enrichTraceNodes, groupTraceNodesByLayer } from '../constants/trace-layer-map'

const pageMeta = NAV_PAGES.trace

const route = useRoute()
const router = useRouter()

const traces = ref([])
const loading = ref(false)
const pageSize = ref(20)
const lastRefreshed = ref('')
const chartView = ref('timeline')
const chartLoading = ref(false)
const traceChart = ref(null)
let chartInstance = null
let pollTimer = null
const resizeHandler = () => chartInstance?.resize()

const detailOpen = ref(false)
const detailRow = ref(null)
const detailLoading = ref(false)
const detailNodes = ref([])
const detailSummary = ref({})

const detailLayerGroups = computed(() => groupTraceNodesByLayer(detailNodes.value))

const summaryCards = computed(() => [
  { label: '总记录', value: traces.value.length, suffix: '条' },
  { label: '成功率', value: traces.value.length ? Math.round(traces.value.filter(t => t.status !== 'error').length / traces.value.length * 100) : 0, suffix: '%' },
  { label: '平均阶段', value: traces.value.length ? (traces.value.reduce((s, t) => s + (t.stage_count || 0), 0) / traces.value.length).toFixed(1) : 0, suffix: '个' },
  { label: '最近记录', value: traces.value.length ? formatTimeShort(traces.value[0]?.timestamp) : '--', suffix: '' },
])

const blueTeamAuditCount = computed(() => {
  return traces.value.filter(t => {
    const target = (t.target || '').toLowerCase()
    return target.includes('audit') || target.includes('safety') || target.includes('blue') || target.includes('security')
  }).length
})

function displayTime(row) {
  const raw = row.timestamp_raw || row.timestamp
  const assumeUtc = raw && !String(raw).includes('+08') && !String(raw).includes('T') && String(raw).includes(' ')
  return formatBeijingTime(raw, { assumeUtcNaive: assumeUtc })
}
function relativeTime(raw) {
  return formatRelativeBeijing(raw, { assumeUtcNaive: raw && String(raw).match(/^\d{4}-\d{2}-\d{2} \d{2}:/) })
}
function formatTimeShort(ts) {
  const s = formatBeijingTime(ts)
  return s === '—' ? s : s.slice(5, 16)
}
function formatObjBrief(obj, max = 200) {
  if (!obj || typeof obj !== 'object') return ''
  const bits = []
  for (const [k, v] of Object.entries(obj).slice(0, 6)) {
    if (v == null || v === '') continue
    bits.push(`${k}=${typeof v === 'object' ? '…' : String(v).slice(0, 40)}`)
  }
  const s = bits.join('；')
  return s.length > max ? s.slice(0, max - 3) + '…' : s
}
function formatSummaryVal(v) {
  if (v == null) return '—'
  if (typeof v === 'object') return formatObjBrief(v, 400) || '—'
  return String(v)
}
function traceNodeDesc(n) {
  const parts = []
  if (n.toolName) parts.push(`工具 Tool: ${n.toolName}`)
  if (n.detail) parts.push(String(n.detail).slice(0, 160))
  if (n.details && typeof n.details === 'object') {
    const brief = formatObjBrief(n.details, 140)
    if (brief) parts.push(brief)
  }
  if (n.duration_ms) parts.push(`耗时 Duration: ${Number(n.duration_ms).toFixed(0)}ms`)
  if (n.verdict) parts.push(`判定 Verdict: ${n.verdict}`)
  return parts.join(' · ') || '—'
}

function goL5Analysis() {
  if (!detailRow.value?.trace_id) return
  router.push({ path: '/l5', query: { trace: detailRow.value.trace_id } })
}

function nodesFromBundle(bundle) {
  const st = bundle?.sqlite_trace?.stages
  if (Array.isArray(st) && st.length) {
    return st.map((s, i) => ({
      node_id: `stage-${i}`,
      name: s.name || s.stage || `阶段 ${i + 1}`,
      stage: s.name || s.stage,
      detail: typeof s.data === 'object' ? formatObjBrief(s.data, 200) : String(s.data || ''),
      status: 'success',
      duration_ms: s.duration_ms,
    }))
  }
  const events = bundle?.audit_events || []
  if (events.length) {
    return events.slice(0, 30).map((e, i) => ({
      node_id: `audit-${i}`,
      name: e.event_type || e.type || 'audit',
      detail: formatObjBrief(e.payload || e, 180) || String(e.event_type || ''),
      status: 'success',
    }))
  }
  return []
}

async function openDetail(row) {
  if (!row?.trace_id) return
  detailRow.value = row
  detailOpen.value = true
  detailLoading.value = true
  detailNodes.value = []
  detailSummary.value = {}
  try {
    const viz = await api.get(`/trace/${row.trace_id}`)
    let nodes = viz.nodes || []
    let summary = viz.summary || {}
    if (!nodes.length) {
      const bundle = await api.get(`/trace/${row.trace_id}/export`)
      nodes = nodesFromBundle(bundle)
      summary = {
        ...summary,
        status: bundle.sqlite_trace?.status || summary.status,
        user_message: (bundle.sqlite_trace?.user_message || '').slice(0, 200),
        audit_events: (bundle.audit_events || []).length,
      }
    }
    detailNodes.value = enrichTraceNodes(nodes)
    detailSummary.value = summary
    const idx = traces.value.findIndex(t => t.trace_id === row.trace_id)
    if (idx >= 0) {
      traces.value[idx] = { ...traces.value[idx], stage_count: nodes.length, nodes, summary }
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function exportTrace(traceId, format = 'text') {
  if (!traceId) return
  try {
    const res = await fetchWithAuth(`/api/trace/${traceId}/export?format=${format}`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText)
    }
    if (format === 'json') {
      const data = await res.json()
      downloadBlob(JSON.stringify(data, null, 2), `${traceId}-debug.json`, 'application/json')
      ElMessage.success('已导出 JSON（调试用）')
      return
    }
    const text = await res.text()
    const ext = format === 'html' ? 'html' : 'txt'
    const mime = format === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8'
    downloadBlob(text, `${traceId}-report.${ext}`, mime)
    ElMessage.success(
      format === 'html' ? '已导出可视化 HTML' : format === 'text' ? '已导出执行纪要' : '已导出'
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

async function fetchTraces() {
  loading.value = true
  try {
    const res = await api.get('/trace/', { params: { limit: pageSize.value } }).catch(() => ({ traces: [] }))
    const list = res.traces || res.items || res || []
    traces.value = (Array.isArray(list) ? list : []).map(t => ({
      ...t,
      timestamp: t.timestamp || formatBeijingTime(t.timestamp_raw),
      stage_count: (t.nodes || t.stages || []).length,
    }))
  } catch {
    traces.value = []
  } finally {
    loading.value = false
    lastRefreshed.value = new Date().toLocaleString('zh-CN')
    nextTick(renderChart)
  }
}

function renderChart() {
  if (!traceChart.value || !traces.value.length) return
  chartLoading.value = true
  try {
    if (!chartInstance || chartInstance.isDisposed()) {
      if (chartInstance) try { chartInstance.dispose() } catch {}
      if (!traceChart.value) return
      chartInstance = echarts.init(traceChart.value)
    }
    const view = chartView.value
    if (view === 'timeline') {
      const data = traces.value.slice(0, 20).reverse()
      chartInstance.setOption({
        tooltip: chartTooltip(),
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: categoryAxis(data.map(t => formatTimeShort(t.timestamp)), { axisLabel: { rotate: 45, fontSize: 10 } }),
        yAxis: valueAxis({ name: '阶段数', nameTextStyle: { color: '#64748b' } }),
        series: [{
          type: 'bar', data: data.map(t => t.stage_count || 0),
          itemStyle: {
            color: pageChartGradient(echarts),
            borderRadius: [4, 4, 0, 0],
          },
        }],
      })
    } else if (view === 'dag') {
      const nodes = traces.value.slice(0, 10).map((t, i) => ({
        id: t.trace_id, name: t.trace_id.slice(0, 12) + '...',
        symbolSize: 30 + (t.stage_count || 0) * 5,
        itemStyle: { color: t.status === 'success' ? '#10b981' : '#f59e0b' },
      }))
      const links = []
      for (let i = 0; i < nodes.length - 1; i++) {
        links.push({ source: nodes[i].id, target: nodes[i + 1].id })
      }
      chartInstance.setOption({
        tooltip: {},
        series: [{
          type: 'graph', layout: 'force', data: nodes, links,
          roam: true, draggable: true,
          lineStyle: { color: 'source', curveness: 0.3, width: 1.5 },
          label: { show: true, fontSize: 9, position: 'bottom' },
          force: { repulsion: 300, edgeLength: 120 },
        }],
      })
    } else if (view === 'heatmap') {
      const hours = Array.from({ length: 24 }, (_, i) => `${i}时`)
      const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
      const data = []
      for (let d = 0; d < 7; d++) {
        for (let h = 0; h < 24; h++) {
          data.push([h, d, Math.floor(Math.random() * 5)])
        }
      }
      chartInstance.setOption({
        tooltip: { position: 'top' },
        grid: { left: '2%', right: '2%', bottom: '10%', containLabel: true },
        xAxis: { type: 'category', data: hours, splitArea: { show: true } },
        yAxis: { type: 'category', data: days, splitArea: { show: true } },
        visualMap: { min: 0, max: 5, calculable: true, orient: 'horizontal', left: 'center', bottom: '0%',
          textStyle: { color: '#475569' },
          inRange: { color: ['#f8fafc', '#c7d2fe', '#818cf8', '#6366f1', '#4f46e5', '#f59e0b'] }
        },
        series: [{ type: 'heatmap', data, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 10 } } }],
      })
    }
  } finally {
    chartLoading.value = false
  }
}

watch(chartView, () => nextTick(renderChart))

onMounted(async () => {
  await fetchTraces()
  pollTimer = setInterval(fetchTraces, 8000)
  const qid = route.query.id
  if (qid) {
    const row = traces.value.find(t => t.trace_id === qid) || { trace_id: qid }
    openDetail(row)
  }
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
})

// --- 批量操作 ---
const selectedTraceIds = ref([])
function onTraceSelect(rows) { selectedTraceIds.value = rows.map(r => r.trace_id) }

async function batchDeleteTraces() {
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedTraceIds.value.length} 条 Trace？`, '确认', { type: 'warning' })
    const res = await api.post('/trace/cleanup', { trace_ids: selectedTraceIds.value })
    ElMessage.success(`已删除 ${res.deleted_count} 条`)
    selectedTraceIds.value = []
    fetchTraces()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function cleanupOld() {
  try {
    const res = await api.post('/trace/cleanup', { days: 30 })
    ElMessage.success(`已清理 ${res.deleted_count} 条旧记录`)
    fetchTraces()
  } catch (e) { ElMessage.error('清理失败') }
}
</script>

<style scoped>
.trace-view {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-3);
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
  align-items: center;
}

/* 统计卡片 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
  animation: slide-up var(--duration-normal) var(--ease-out) both;
  transition: all var(--duration-normal) var(--ease-out);
}
.stat-card:nth-child(1) { animation-delay: 0ms; }
.stat-card:nth-child(2) { animation-delay: 60ms; }
.stat-card:nth-child(3) { animation-delay: 120ms; }
.stat-card:nth-child(4) { animation-delay: 180ms; }
.stat-card:nth-child(5) { animation-delay: 240ms; }

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 3px;
  height: 100%;
  background: var(--color-primary-500);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-neutral-900);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-top: var(--space-1);
}

.stat-suffix {
  font-size: var(--text-xs);
  color: var(--color-neutral-300);
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
}

.blue-team-stat::before {
  background: linear-gradient(180deg, #ef4444, #8b5cf6) !important;
}

.blue-team-stat .stat-value {
  color: var(--color-primary-700);
}

/* 图表区域 */
.section-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.section-card-actions {
  display: flex;
  gap: var(--space-2);
}

.chart-area {
  padding: var(--space-4);
  height: 320px;
}

.trace-chart {
  width: 100%;
  height: 100%;
}

.chart-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--color-neutral-300);
}

.chart-empty p {
  margin: 0;
  font-size: var(--text-sm);
}

/* 表格 */
.table-wrap {
  padding: 0 var(--space-5) var(--space-4);
}

.last-refresh {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.trace-time {
  font-size: var(--text-sm);
  color: var(--color-neutral-700);
}

.trace-time-relative {
  font-size: 11px;
  color: var(--color-neutral-400);
}

.degradation-s0 {
  color: var(--color-neutral-400);
  font-size: var(--text-xs);
}

.stage-count {
  font-variant-numeric: tabular-nums;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
}

.status-indicator.success { color: var(--color-success); }
.status-indicator.warning { color: var(--color-warning); }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.status-indicator.success .status-dot { background: var(--color-success); }
.status-indicator.warning .status-dot { background: var(--color-warning); }

.action-btns {
  display: flex;
  gap: var(--space-1);
}

.batch-bar {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

/* 详情弹窗 */
.trace-detail-dialog :deep(.el-dialog__body) {
  padding: var(--space-5);
}

.detail-body {
  min-height: 200px;
}

/* 五层分组 Layer groups */
.trace-layer-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.trace-layer-section {
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.trace-layer-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: linear-gradient(90deg, color-mix(in srgb, var(--layer-accent) 12%, #fff), #fff);
  border-bottom: 2px solid var(--layer-accent);
}

.trace-layer-id {
  font-size: 11px;
  font-weight: 800;
  color: #fff;
  background: var(--layer-accent);
  padding: 2px 8px;
  border-radius: 4px;
}

.trace-layer-titles { display: flex; flex-direction: column; gap: 1px; flex: 1; }
.trace-layer-cn { font-size: var(--text-sm); font-weight: 600; color: var(--color-neutral-800); }
.trace-layer-en { font-size: 10px; color: var(--color-neutral-400); }
.trace-layer-agent { font-size: 10px; color: var(--color-neutral-500); }
.trace-layer-count { font-size: 10px; color: var(--color-neutral-400); font-variant-numeric: tabular-nums; }

.stage-timeline--layer {
  padding: var(--space-4) var(--space-4) var(--space-2) calc(32px + var(--space-4));
  margin-bottom: 0;
}

.stage-timeline {
  position: relative;
  padding-left: 32px;
  margin-bottom: var(--space-5);
}

.stage-timeline::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--color-neutral-200);
}

.stage-node {
  position: relative;
  margin-bottom: var(--space-4);
  animation: slide-up var(--duration-normal) var(--ease-out) both;
  animation-delay: calc(var(--node-index, 0) * 80ms);
}

.stage-node-marker {
  position: absolute;
  left: -24px;
  top: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  animation: scale-in var(--duration-normal) var(--ease-spring) both;
  animation-delay: calc(var(--node-index, 0) * 80ms);
}

.stage-node-marker.success { background: var(--color-success-bg); color: var(--color-success); }
.stage-node-marker.warning { background: var(--color-warning-bg); color: var(--color-warning); }
.stage-node-marker.danger { background: var(--color-danger-bg); color: var(--color-danger); }
.stage-node-marker.info { background: var(--color-primary-50); color: var(--color-primary-500); }

.stage-node-card.is-tool {
  border-left: 3px solid var(--layer-accent, var(--color-primary-400));
}

.stage-node-card {
  background: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out);
}

.stage-node-card:hover {
  border-color: var(--color-primary-300);
  box-shadow: var(--shadow-sm);
}

.stage-node-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.stage-node-title-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
}

.stage-node-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.stage-node-tool {
  font-size: 10px;
  color: var(--color-neutral-500);
  background: var(--color-neutral-100);
  padding: 1px 6px;
  border-radius: 4px;
}

.stage-node-status {
  font-size: 10px;
  font-weight: 600;
}

.stage-node-status.is-success { color: var(--color-success); }
.stage-node-status.is-warning { color: var(--color-warning); }
.stage-node-status.is-danger { color: var(--color-danger); }
.stage-node-status.is-info { color: var(--color-primary-500); }

.stage-node-subline {
  font-size: 10px;
  color: var(--color-neutral-400);
  margin-bottom: var(--space-1);
}

.stage-node-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.stage-node-duration {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.stage-node-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  line-height: var(--leading-relaxed);
}

.detail-summary {
  margin-bottom: var(--space-4);
}

.detail-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
