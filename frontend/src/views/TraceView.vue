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
    <ArchitectureLayers highlight="trace" :default-expanded="!panelOpen" />

    <!-- 可视化分析区域 -->
    <div class="section-card">
      <div class="section-card-header">
        <div class="section-card-head-left">
          <h3>追踪分析仪表盘</h3>
          <p class="section-card-desc">
            <strong>L4</strong> 个案视图（本页）· 与
            <router-link to="/l5">L5 链路量化</router-link>
            共用 Trace 库；
            <strong>L5</strong> 负责 3σ/IQR 离群检测、DBSCAN 聚类、六维评分与策略反写
          </p>
        </div>
        <div class="section-card-actions">
          <el-select
            v-if="chartView === 'focus'"
            v-model="focusTraceId"
            size="small"
            filterable
            clearable
            placeholder="选择 Trace"
            style="width: 220px"
            @change="onFocusTraceChange"
          >
            <el-option
              v-for="t in traces"
              :key="t.trace_id"
              :label="`${t.trace_id.slice(0, 14)}… · ${t.stage_count || 0} 阶段`"
              :value="t.trace_id"
            />
          </el-select>
          <el-radio-group v-model="chartView" size="small" @change="onChartViewChange">
            <el-radio-button value="l5_scatter">风险散点</el-radio-button>
            <el-radio-button value="l5_heatmap">意图热力</el-radio-button>
            <el-radio-button value="timeline">耗时趋势</el-radio-button>
            <el-radio-button value="activity">活跃时段</el-radio-button>
            <el-radio-button value="focus">单条分析</el-radio-button>
          </el-radio-group>
          <el-button size="small" :loading="loading" @click="fetchTraces">刷新</el-button>
        </div>
      </div>
      <div class="chart-area chart-area--tall">
        <div ref="traceChart" class="trace-chart" :class="{ 'is-hidden': chartShowEmpty }" v-loading="chartLoading"></div>
        <div v-if="chartView === 'focus' && focusTraceId && focusVizLoading" class="chart-overlay-hint">加载阶段数据…</div>
        <div v-if="chartShowEmpty" class="chart-empty">
          <el-icon :size="32" color="var(--color-neutral-300)"><DataAnalysis /></el-icon>
          <p>{{ chartEmptyText }}</p>
        </div>
      </div>
    </div>

    <!-- 追踪记录（工具栏在卡片外，避免 overflow:hidden 导致无法吸顶） -->
    <div class="trace-records-wrap">
      <div class="trace-records-toolbar" :class="{ 'is-panel-open': panelOpen }">
        <div class="trace-records-toolbar-left">
          <h3>追踪记录</h3>
          <span class="last-refresh">上次刷新: {{ lastRefreshed || '—' }}</span>
        </div>
        <div class="trace-records-toolbar-right">
          <el-select v-model="focusTraceId" size="small" filterable clearable placeholder="聚焦 Trace" style="width: 200px" @change="onFocusTraceChange">
            <el-option v-for="t in traces" :key="t.trace_id" :label="t.trace_id.slice(0, 18)" :value="t.trace_id" />
          </el-select>
          <el-select v-model="pageSize" size="small" style="width: 88px" @change="fetchTraces">
            <el-option :value="10" label="10 条" />
            <el-option :value="20" label="20 条" />
            <el-option :value="50" label="50 条" />
          </el-select>
          <el-button size="small" type="primary" plain :disabled="!focusTraceId" @click="openFocusedMemo">在线纪要</el-button>
          <el-button size="small" type="success" plain :disabled="!focusTraceId" @click="openFocusedAnalysis">在线分析</el-button>
          <PipelineBtn action="refresh" size="small" :loading="loading" @click="fetchTraces" />
        </div>
      </div>

      <!-- 内联详情面板（非弹窗，避免遮挡顶部且支持吸顶） -->
      <div
        v-if="panelOpen && detailRow"
        ref="inlinePanelRef"
        class="trace-inline-panel section-card"
      >
        <div class="trace-panel-sticky-bar">
          <div class="trace-inline-panel-head">
            <div class="trace-inline-panel-title">
              <h3>Trace 详情</h3>
              <code class="trace-inline-id">{{ detailRow.trace_id }}</code>
            </div>
            <div class="trace-inline-tools">
              <el-button size="small" text type="primary" @click="expandAllLayers">全部展开</el-button>
              <el-button size="small" text @click="collapseAllLayers">全部收起</el-button>
              <el-button size="small" text type="info" @click="goL5Analysis">L5</el-button>
              <el-button size="small" @click="closePanel">收起</el-button>
            </div>
          </div>
          <el-tabs v-model="detailTab" class="detail-tabs detail-tabs--in-bar" :lazy="false" @tab-change="onDetailTabChange">
            <el-tab-pane label="卷宗" name="dossier" />
            <el-tab-pane label="在线纪要" name="memo" />
            <el-tab-pane label="阶段图表" name="stages" />
            <el-tab-pane label="在线分析" name="analysis" />
          </el-tabs>
        </div>
        <div v-loading="detailLoading" class="detail-body detail-body--inline">
          <div v-show="detailTab === 'dossier'" class="detail-tab-pane-body">
              <el-empty v-if="!detailLoading && !detailLayerGroups.length" description="无阶段数据，可切换到「阶段图表」或「在线分析」" />
              <template v-else>
                <el-collapse v-model="detailOpenLayers" class="trace-layer-collapse">
            <el-collapse-item
              v-for="group in detailLayerGroups"
              :key="group.layer"
              :name="group.layer"
            >
              <template #title>
                <div class="trace-layer-head trace-layer-head--collapse" :style="{ '--layer-accent': group.accent }">
                  <span class="trace-layer-id">{{ group.layer }}</span>
                  <div class="trace-layer-titles">
                    <span class="trace-layer-cn">{{ group.cn }}</span>
                    <span class="trace-layer-en">{{ group.en }}</span>
                  </div>
                  <span class="trace-layer-agent">{{ group.agent }}</span>
                  <span class="trace-layer-count">{{ group.nodes.length }} 步</span>
                </div>
              </template>
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
            </el-collapse-item>
          </el-collapse>
          <el-descriptions v-if="detailSummary && Object.keys(detailSummary).length" :column="2" size="small" border class="detail-summary">
            <el-descriptions-item v-for="(v, k) in detailSummary" :key="k" :label="String(k)">{{ formatSummaryVal(v) }}</el-descriptions-item>
          </el-descriptions>
              </template>
          </div>

          <div v-show="detailTab === 'memo'" class="detail-tab-pane-body">
            <div v-loading="memoLoading" class="detail-memo-panel">
              <div v-if="memoChartData.length" ref="memoChartRef" class="memo-inline-chart"></div>
              <pre class="memo-online-text">{{ memoText || '加载中…' }}</pre>
            </div>
          </div>

          <div v-show="detailTab === 'stages'" class="detail-tab-pane-body">
              <div v-loading="vizLoading" class="detail-chart-panel">
                <div ref="stageChartRef" class="detail-inline-chart detail-inline-chart--wide"></div>
                <p v-if="!vizLoading && !(vizData?.stage_waterfall || []).length" class="chart-hint">暂无阶段耗时数据</p>
              </div>
          </div>

          <div v-show="detailTab === 'analysis'" class="detail-tab-pane-body">
              <div v-loading="vizLoading" class="detail-chart-panel">
                <div v-if="vizData?.facts && Object.keys(vizData.facts).length" class="viz-facts">
                  <el-tag v-for="(v, k) in vizData.facts" :key="k" size="small" effect="plain">{{ k }}: {{ typeof v === 'object' ? JSON.stringify(v).slice(0, 80) : v }}</el-tag>
                </div>
                <div v-if="(vizData?.charts || []).length" class="analysis-chart-grid">
                  <div v-for="(spec, idx) in vizData.charts" :key="spec.chart_id || idx" class="analysis-chart-card">
                    <div class="analysis-chart-title">{{ spec.title }}</div>
                    <div class="analysis-chart-def">{{ spec.definition }}</div>
                    <div :ref="el => setAnalysisChartRef(el, idx)" class="detail-inline-chart"></div>
                  </div>
                </div>
                <el-empty v-else-if="!vizLoading && !(vizData?.stage_waterfall || []).length" description="暂无分析图表，可查看下方 HTML 报告" />
                <div class="html-preview-wrap">
                  <div class="html-preview-head">
                    <span>完整 HTML 分析报告</span>
                    <el-button size="small" text type="primary" :loading="htmlPreviewLoading" @click="loadHtmlPreview">刷新预览</el-button>
                  </div>
                  <iframe v-if="htmlPreviewUrl" :src="htmlPreviewUrl" class="html-preview-frame" title="Trace HTML 分析" />
                  <p v-else class="chart-hint">正在加载 HTML 分析报告…</p>
                </div>
              </div>
          </div>

          <div class="detail-actions">
            <el-button type="primary" size="small" @click="exportTrace(detailRow.trace_id, 'text')">导出执行纪要 (.txt)</el-button>
            <el-button type="success" size="small" @click="exportTrace(detailRow.trace_id, 'html')">下载 HTML 分析</el-button>
            <el-button size="small" text type="info" @click="exportTrace(detailRow.trace_id, 'json')">JSON（调试）</el-button>
          </div>
        </div>
      </div>

      <div class="section-card trace-records-card">
        <div class="table-wrap">
        <el-table
          :data="traces"
          v-loading="loading"
          stripe
          size="small"
          row-key="trace_id"
          empty-text="暂无溯源记录"
          highlight-current-row
          :row-class-name="traceRowClass"
          @selection-change="onTraceSelect"
          @row-click="onTraceRowClick"
        >
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
                <el-button size="small" text type="primary" @click.stop="openDetail(row)">详情</el-button>
                <el-button size="small" text type="primary" @click.stop="openDetailWithTab(row, 'memo')">纪要</el-button>
                <el-button size="small" text type="success" @click.stop="openDetailWithTab(row, 'analysis')">分析</el-button>
                <el-button size="small" text type="info" @click.stop="exportTrace(row.trace_id, 'json')">JSON</el-button>
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { initChart, getEcharts, scheduleChartResize } from '../composables/useEcharts'
import {
  chartTooltip, categoryAxis, valueAxis,
  pageChartGradient, buildWaterfallBarOption,
  buildL5ScatterOption, buildL5HeatmapOption,
} from '../utils/chartTheme'
import api from '../api'
import { fetchTraceViz, fetchTraceMemo } from '../api/trace'
import { fetchL5Scatter, fetchL5Heatmap } from '../api/l5'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingTime, formatRelativeBeijing } from '../utils/formatTime'
import { downloadBlob, fetchWithAuth } from '../utils/download'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'
import PageHeader from '../components/common/PageHeader.vue'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { NAV_PAGES } from '../constants/navigation'
import { enrichTraceNodes, groupTraceNodesByLayer } from '../constants/trace-layer-map'
import { traceQuery, buildL5Query } from '../utils/pipeline-context'

const pageMeta = NAV_PAGES.trace

const route = useRoute()
const router = useRouter()

const traces = ref([])
const loading = ref(false)
const pageSize = ref(20)
const lastRefreshed = ref('')
const chartView = ref('l5_scatter')
const chartShowEmpty = computed(() => {
  if (chartLoading.value) return false
  if (chartView.value === 'focus') return !focusTraceId.value
  if (chartView.value === 'l5_scatter') return !(l5Scatter.value?.points?.length)
  if (chartView.value === 'l5_heatmap') return !(l5Heatmap.value?.matrix?.length)
  if (chartView.value === 'activity') return !heatmapData.value?.data?.length && !traces.value.length
  if (chartView.value === 'timeline') return !traces.value.length
  return false
})

const chartEmptyText = computed(() => {
  if (chartView.value === 'focus') return '请在上方选择 Trace，或点击下方表格行'
  if (['l5_scatter', 'l5_heatmap'].includes(chartView.value)) {
    return '暂无足够 Trace 样本，请先在智能体对话完成 1 次 plan/execute'
  }
  return '暂无追踪数据'
})

function scatterRow(p, idxInBucket, bucketSize) {
  const risk = p.risk_score ?? p.error_rate ?? 0
  const yJitter = bucketSize > 1 ? (idxInBucket - (bucketSize - 1) / 2) * 2.2 : 0
  return [
    p.latency_ms,
    Math.min(99, Math.max(1, risk + yJitter)),
    p.stages || 4,
    p.trace_id,
    p.path_label || p.path_id,
    p.error_rate,
    p.latency_ms,
    risk,
  ]
}

function bucketScatterPoints(pts) {
  const buckets = new Map()
  for (const p of pts) {
    const risk = p.risk_score ?? p.error_rate ?? 0
    const key = `${Math.round(p.latency_ms / 80)}|${Math.round(risk / 8)}`
    const list = buckets.get(key) || []
    list.push(p)
    buckets.set(key, list)
  }
  const rows = []
  for (const group of buckets.values()) {
    group.forEach((p, i) => rows.push(scatterRow(p, i, group.length)))
  }
  return rows
}

const focusTraceId = ref('')
const focusVizData = ref(null)
const focusVizLoading = ref(false)
const heatmapData = ref(null)
const l5Scatter = ref(null)
const l5Heatmap = ref(null)
const chartLoading = ref(false)
const traceChart = ref(null)
let chartInstance = null
let pollTimer = null
const resizeHandler = () => chartInstance?.resize()

const panelOpen = ref(false)
const inlinePanelRef = ref(null)
const detailRow = ref(null)
const detailLoading = ref(false)
const detailNodes = ref([])
const detailSummary = ref({})
const detailOpenLayers = ref([])
const detailTab = ref('dossier')
const vizData = ref(null)
const vizLoading = ref(false)
const stageChartRef = ref(null)
const analysisChartRefs = ref([])
const htmlPreviewUrl = ref('')
const htmlPreviewLoading = ref(false)
const memoText = ref('')
const memoChartData = ref([])
const memoLoading = ref(false)
const memoChartRef = ref(null)
let stageChartInst = null
let memoChartInst = null
const analysisChartInsts = []

function setAnalysisChartRef(el, idx) {
  if (el) analysisChartRefs.value[idx] = el
}

function traceRowClass({ row }) {
  return row.trace_id === focusTraceId.value ? 'trace-row-focus' : ''
}

function onTraceRowClick(row) {
  if (!row?.trace_id) return
  focusTraceId.value = row.trace_id
  if (chartView.value === 'focus') {
    loadFocusViz(row.trace_id)
  }
}

function onFocusTraceChange(id) {
  if (!id) {
    focusVizData.value = null
    if (chartView.value === 'focus') nextTick(renderChart)
    return
  }
  if (chartView.value !== 'focus') chartView.value = 'focus'
  loadFocusViz(id)
}

function onChartViewChange(view) {
  if (view === 'focus' && !focusTraceId.value && traces.value.length) {
    focusTraceId.value = traces.value[0].trace_id
  }
  ensureRenderChart()
}

async function loadFocusViz(traceId) {
  if (!traceId) return
  focusVizLoading.value = true
  try {
    focusVizData.value = await fetchTraceViz(traceId)
    nextTick(renderChart)
  } catch {
    focusVizData.value = null
  } finally {
    focusVizLoading.value = false
  }
}

function openFocusedAnalysis() {
  if (!focusTraceId.value) return
  const row = traces.value.find(t => t.trace_id === focusTraceId.value) || { trace_id: focusTraceId.value }
  openDetailWithTab(row, 'analysis')
}

function openFocusedMemo() {
  if (!focusTraceId.value) return
  const row = traces.value.find(t => t.trace_id === focusTraceId.value) || { trace_id: focusTraceId.value }
  openDetailWithTab(row, 'memo')
}

function openDetailWithTab(row, tab = 'dossier') {
  detailTab.value = tab
  openDetail(row)
}

function scrollToInlinePanel() {
  nextTick(() => {
    const el = inlinePanelRef.value
    const main = document.querySelector('main.content')
    if (!el || !main) return
    const elRect = el.getBoundingClientRect()
    const mainRect = main.getBoundingClientRect()
    const scrollTop = main.scrollTop + (elRect.top - mainRect.top) - 8
    main.scrollTo({ top: Math.max(0, scrollTop), behavior: 'smooth' })
  })
}

async function loadMemoData(traceId) {
  if (!traceId) return
  memoLoading.value = true
  memoText.value = ''
  memoChartData.value = []
  try {
    const data = await fetchTraceMemo(traceId)
    memoText.value = data.memo || '暂无执行纪要'
    memoChartData.value = data.chart || []
    await nextTick()
    setTimeout(() => renderMemoChart(), 80)
  } catch (e) {
    memoText.value = `加载失败: ${e.response?.data?.detail || e.message || e}`
  } finally {
    memoLoading.value = false
  }
}

async function renderMemoChart() {
  const rows = memoChartData.value || []
  if (!memoChartRef.value || !rows.length) return
  await getEcharts()
  if (memoChartInst) {
    try { memoChartInst.dispose() } catch {}
    memoChartInst = null
  }
  memoChartInst = await initChart(memoChartRef.value)
  if (!memoChartInst) return
  memoChartInst.setOption({
    tooltip: chartTooltip(),
    grid: { left: 48, right: 16, top: 24, bottom: 40, containLabel: true },
    xAxis: categoryAxis(rows.map(r => r.label || ''), { axisLabel: { rotate: 28, fontSize: 9, interval: 0 } }),
    yAxis: valueAxis({ name: 'ms' }),
    series: [{
      type: 'bar',
      data: rows.map(r => r.duration_ms || 0),
      itemStyle: { color: '#38bdf8', borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 32,
    }],
  }, true)
  scheduleChartResize(memoChartInst)
}

async function loadVizData(traceId) {
  if (!traceId) return
  vizLoading.value = true
  vizData.value = null
  try {
    try {
      vizData.value = await fetchTraceViz(traceId)
    } catch {
      const memo = await fetchTraceMemo(traceId)
      const chart = memo.chart || []
      vizData.value = {
        trace_id: traceId,
        stage_waterfall: chart.map(c => ({
          label: c.label || '',
          title: c.label || '',
          duration_ms: c.duration_ms || 0,
        })),
        charts: [],
        facts: {},
      }
    }
    await nextTick()
    setTimeout(() => renderDetailCharts(), 100)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载分析数据失败')
  } finally {
    vizLoading.value = false
  }
}

function buildSpecChartOption(spec) {
  const bars = spec.bars || []
  const labels = bars.map(b => b.label)
  const values = bars.map(b => b.value)
  const colors = bars.map(b => b.color || '#6366f1')
  const base = { tooltip: chartTooltip() }
  if (spec.chart_type === 'donut' || spec.chart_type === 'pie') {
    return {
      ...base,
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        data: bars.map(b => ({ name: b.label, value: b.value, itemStyle: { color: b.color || '#6366f1' } })),
        label: { fontSize: 10 },
      }],
    }
  }
  if (spec.chart_type === 'hbar') {
    return {
      ...base,
      grid: { left: 100, right: 16, top: 16, bottom: 24, containLabel: true },
      xAxis: valueAxis({ name: spec.unit || '' }),
      yAxis: categoryAxis(labels, { inverse: true, axisLabel: { fontSize: 10, width: 90, overflow: 'truncate' } }),
      series: [{ type: 'bar', data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })), barMaxWidth: 20 }],
    }
  }
  if (spec.chart_type === 'gauge') {
    const max = spec.y_max || 100
    return {
      ...base,
      series: [{
        type: 'gauge',
        min: 0,
        max,
        detail: { formatter: `{value}${spec.unit || ''}`, fontSize: 14 },
        data: [{ value: values[0] || 0 }],
      }],
    }
  }
  if (spec.chart_type === 'line') {
    return {
      ...base,
      grid: { left: 48, right: 16, top: 24, bottom: 40, containLabel: true },
      xAxis: categoryAxis(labels, { axisLabel: { rotate: 24, fontSize: 9 } }),
      yAxis: valueAxis({ name: spec.unit || '' }),
      series: [{ type: 'line', smooth: true, data: values, itemStyle: { color: colors[0] } }],
    }
  }
  return {
    ...base,
    grid: { left: 48, right: 16, top: 24, bottom: 48, containLabel: true },
    xAxis: categoryAxis(labels, { axisLabel: { rotate: labels.length > 6 ? 28 : 0, fontSize: 9, interval: 0 } }),
    yAxis: valueAxis({ name: spec.unit || '', max: spec.y_max || undefined }),
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })),
      barMaxWidth: 32,
    }],
  }
}

async function renderDetailCharts() {
  await getEcharts()
  disposeDetailCharts()
  const spans = vizData.value?.stage_waterfall || []
  if (stageChartRef.value && spans.length) {
    stageChartInst = await initChart(stageChartRef.value)
    if (stageChartInst) {
      stageChartInst.setOption(buildWaterfallBarOption(spans), true)
      scheduleChartResize(stageChartInst)
    }
  }
  const specs = vizData.value?.charts || []
  for (let i = 0; i < specs.length; i++) {
    const el = analysisChartRefs.value[i]
    if (!el) continue
    const inst = await initChart(el)
    if (!inst) continue
    analysisChartInsts.push(inst)
    inst.setOption(buildSpecChartOption(specs[i]), true)
    scheduleChartResize(inst)
  }
}

function disposeDetailCharts() {
  if (stageChartInst) {
    try { stageChartInst.dispose() } catch {}
    stageChartInst = null
  }
  if (memoChartInst) {
    try { memoChartInst.dispose() } catch {}
    memoChartInst = null
  }
  while (analysisChartInsts.length) {
    const inst = analysisChartInsts.pop()
    try { inst.dispose() } catch {}
  }
  analysisChartRefs.value = []
}

async function loadHtmlPreview() {
  if (!detailRow.value?.trace_id) return
  htmlPreviewLoading.value = true
  try {
    const res = await fetchWithAuth(`/api/trace/${detailRow.value.trace_id}/export?format=html&inline=1`)
    if (!res.ok) throw new Error('加载失败')
    const html = await res.text()
    if (htmlPreviewUrl.value) URL.revokeObjectURL(htmlPreviewUrl.value)
    htmlPreviewUrl.value = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
  } catch (e) {
    ElMessage.error(e.message || 'HTML 预览失败')
  } finally {
    htmlPreviewLoading.value = false
  }
}

function closePanel() {
  panelOpen.value = false
  disposeDetailCharts()
  memoText.value = ''
  memoChartData.value = []
  if (htmlPreviewUrl.value) {
    URL.revokeObjectURL(htmlPreviewUrl.value)
    htmlPreviewUrl.value = ''
  }
}

function onDetailTabChange(tab) {
  if (!detailRow.value?.trace_id) return
  if (tab === 'memo') {
    loadMemoData(detailRow.value.trace_id)
  } else if (tab === 'stages' || tab === 'analysis') {
    loadVizData(detailRow.value.trace_id)
    if (tab === 'analysis') loadHtmlPreview()
  }
}

watch(detailTab, tab => {
  nextTick(() => {
    setTimeout(() => {
      if (tab === 'memo' && memoChartData.value.length) renderMemoChart()
      if ((tab === 'stages' || tab === 'analysis') && vizData.value) renderDetailCharts()
    }, 150)
  })
})

const detailLayerGroups = computed(() => groupTraceNodesByLayer(detailNodes.value))

function syncDetailOpenLayers(groups = detailLayerGroups.value) {
  detailOpenLayers.value = groups.map(g => g.layer)
}

function expandAllLayers() {
  syncDetailOpenLayers()
}

function collapseAllLayers() {
  detailOpenLayers.value = []
}

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
  router.push({ path: '/l5', query: buildL5Query(null, detailRow.value.trace_id) })
}

async function refreshOpenPanelData() {
  const tid = detailRow.value?.trace_id || focusTraceId.value
  if (!tid) return
  if (panelOpen.value && detailRow.value?.trace_id) {
    if (detailTab.value === 'memo') await loadMemoData(tid)
    else if (detailTab.value === 'stages' || detailTab.value === 'analysis') {
      await loadVizData(tid)
      if (detailTab.value === 'analysis') await loadHtmlPreview()
    }
  }
  if (chartView.value === 'focus' && focusTraceId.value) {
    await loadFocusViz(focusTraceId.value)
  }
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
  focusTraceId.value = row.trace_id
  panelOpen.value = true
  detailLoading.value = true
  detailNodes.value = []
  detailSummary.value = {}
  vizData.value = null
  if (htmlPreviewUrl.value) {
    URL.revokeObjectURL(htmlPreviewUrl.value)
    htmlPreviewUrl.value = ''
  }
  scrollToInlinePanel()
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
    syncDetailOpenLayers(groupTraceNodesByLayer(detailNodes.value))
    const idx = traces.value.findIndex(t => t.trace_id === row.trace_id)
    if (idx >= 0) {
      traces.value[idx] = { ...traces.value[idx], stage_count: nodes.length, nodes, summary }
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载详情失败')
  } finally {
    detailLoading.value = false
    scrollToInlinePanel()
    const tid = row.trace_id
    if (detailTab.value === 'memo') {
      await loadMemoData(tid)
    } else if (detailTab.value === 'stages' || detailTab.value === 'analysis') {
      await loadVizData(tid)
      if (detailTab.value === 'analysis') await loadHtmlPreview()
    }
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
    const [res, hm, sc, l5hm] = await Promise.all([
      api.get('/trace/', { params: { limit: pageSize.value } }).catch(() => ({ traces: [] })),
      api.get('/trace/heatmap', { params: { days: 7 } }).catch(() => null),
      fetchL5Scatter().catch(() => null),
      fetchL5Heatmap().catch(() => null),
    ])
    heatmapData.value = hm
    l5Scatter.value = sc
    l5Heatmap.value = l5hm
    const list = res.traces || res.items || res || []
    traces.value = (Array.isArray(list) ? list : []).map(t => ({
      ...t,
      timestamp: t.timestamp || formatBeijingTime(t.timestamp_raw),
      stage_count: t.stage_count ?? (t.nodes || t.stages || []).length ?? 0,
      stage_ms: t.stage_ms ?? 0,
    }))
  } catch {
    traces.value = []
  } finally {
    loading.value = false
    lastRefreshed.value = new Date().toLocaleString('zh-CN')
    await refreshOpenPanelData()
    await ensureRenderChart()
  }
}

async function ensureRenderChart(retries = 4) {
  for (let i = 0; i < retries; i++) {
    await nextTick()
    if (traceChart.value) {
      renderChart()
      return
    }
    await new Promise(r => setTimeout(r, 60))
  }
}

function canRenderChartView(view = chartView.value) {
  if (view === 'focus') return Boolean(focusTraceId.value)
  if (view === 'l5_scatter') return Boolean(l5Scatter.value?.points?.length)
  if (view === 'l5_heatmap') return Boolean(l5Heatmap.value?.matrix?.length)
  if (view === 'activity') return Boolean(heatmapData.value?.data?.length || traces.value.length)
  if (view === 'timeline') return Boolean(traces.value.length)
  return false
}

function renderChart() {
  if (!traceChart.value || !canRenderChartView()) return
  chartLoading.value = true
  getEcharts().then(echarts => {
    if (!chartInstance || chartInstance.isDisposed()) {
      if (chartInstance) try { chartInstance.dispose() } catch {}
      if (!traceChart.value) { chartLoading.value = false; return }
      initChart(traceChart.value).then(inst => {
        chartInstance = inst
        if (chartInstance) paintTraceChart(echarts)
        chartLoading.value = false
      })
      return
    }
    paintTraceChart(echarts)
    chartLoading.value = false
  })
}

function paintTraceChart(echarts) {
  if (!chartInstance) return
  const view = chartView.value
  if (view === 'l5_scatter') {
    const pts = l5Scatter.value?.points || []
    const normal = bucketScatterPoints(pts.filter(p => !p.is_anomaly))
    const anomaly = bucketScatterPoints(pts.filter(p => p.is_anomaly))
    chartInstance.setOption(buildL5ScatterOption({
      normal,
      anomaly,
      latencyRange: l5Scatter.value?.latency_range,
    }), true)
    chartInstance.off('click')
    chartInstance.on('click', params => {
      const tid = params?.data?.[3]
      if (!tid) return
      focusTraceId.value = tid
      chartView.value = 'focus'
      loadFocusViz(tid)
    })
  } else if (view === 'l5_heatmap') {
    const hm = l5Heatmap.value || {}
    chartInstance.setOption(buildL5HeatmapOption({
      xLabels: hm.x_labels || [],
      yLabels: hm.y_labels || [],
      matrix: hm.matrix || [],
    }), true)
  } else if (view === 'timeline') {
    const data = traces.value.slice(0, 20).reverse()
    chartInstance.setOption({
      tooltip: chartTooltip(),
      grid: { left: 48, right: 16, bottom: 48, top: 24, containLabel: true },
      xAxis: categoryAxis(data.map(t => formatTimeShort(t.timestamp)), { axisLabel: { rotate: 32, fontSize: 10 } }),
      yAxis: valueAxis({ name: '阶段耗时(ms)', nameTextStyle: { color: '#64748b' } }),
      series: [{
        type: 'bar',
        data: data.map(t => Math.round(t.stage_ms || 0)),
        itemStyle: {
          color: pageChartGradient(echarts),
          borderRadius: [4, 4, 0, 0],
        },
      }],
    }, true)
  } else if (view === 'activity') {
    const hm = heatmapData.value
    const hours = hm?.hours?.map(h => `${h}时`) || Array.from({ length: 24 }, (_, i) => `${i}时`)
    const days = hm?.day_labels || ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    const data = hm?.data?.length ? hm.data : []
    const maxVal = hm?.max || Math.max(1, ...data.map(d => d[2] || 0))
    chartInstance.setOption({
      tooltip: { position: 'top', formatter: p => `${days[p.value[1]]} ${hours[p.value[0]]}: ${p.value[2]} 条` },
      grid: { left: 48, right: 16, bottom: 48, top: 16, containLabel: true },
      xAxis: { type: 'category', data: hours, splitArea: { show: true } },
      yAxis: { type: 'category', data: days, splitArea: { show: true } },
      visualMap: { min: 0, max: maxVal, calculable: true, orient: 'horizontal', left: 'center', bottom: 4,
        textStyle: { color: '#475569' },
        inRange: { color: ['#f8fafc', '#c7d2fe', '#818cf8', '#6366f1', '#4f46e5', '#f59e0b'] },
      },
      series: [{ type: 'heatmap', data, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 10 } } }],
    }, true)
  } else if (view === 'focus') {
    const spans = focusVizData.value?.stage_waterfall || []
    if (!spans.length) {
      chartInstance.clear()
      return
    }
    chartInstance.setOption(buildWaterfallBarOption(spans), true)
  }
  scheduleChartResize(chartInstance)
}

watch(chartView, (v) => {
  if (v === 'focus' && focusTraceId.value && !focusVizData.value) {
    loadFocusViz(focusTraceId.value)
  } else {
    ensureRenderChart()
  }
})

watch([l5Scatter, l5Heatmap, heatmapData], () => {
  if (['l5_scatter', 'l5_heatmap', 'activity'].includes(chartView.value)) {
    ensureRenderChart()
  }
})

watch(focusTraceId, (id) => {
  if (chartView.value === 'focus' && id) loadFocusViz(id)
})

onMounted(async () => {
  await fetchTraces()
  pollTimer = setInterval(fetchTraces, 8000)
  openFromRouteQuery()
  window.addEventListener('resize', resizeHandler)
})

function openFromRouteQuery() {
  const qid = route.query.id || route.query.trace
  if (!qid) return
  const tab = route.query.tab || 'analysis'
  const row = traces.value.find(t => t.trace_id === qid) || { trace_id: String(qid) }
  openDetailWithTab(row, tab)
}

watch(
  () => [route.query.id, route.query.trace, route.query.tab],
  () => openFromRouteQuery(),
)

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
  disposeDetailCharts()
  if (htmlPreviewUrl.value) URL.revokeObjectURL(htmlPreviewUrl.value)
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
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin-top: var(--space-1);
}

.stat-suffix {
  font-size: var(--text-sm);
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
  align-items: flex-start;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.section-card-head-left {
  flex: 1;
  min-width: 200px;
}

.section-card-desc {
  margin: 4px 0 0;
  font-size: var(--text-sm);
  line-height: 1.5;
  color: #64748b;
}

.section-card-desc a {
  color: var(--color-primary-600);
  text-decoration: none;
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
  flex-wrap: wrap;
  align-items: center;
}

.chart-area {
  padding: var(--space-4);
  height: 320px;
  position: relative;
  min-height: 320px;
}

.chart-area--tall {
  height: 440px;
  min-height: 440px;
}

.chart-overlay-hint {
  position: absolute;
  bottom: 12px;
  right: 16px;
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
}

.trace-records-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.trace-records-card {
  overflow: visible;
}

.trace-records-toolbar.is-panel-open {
  position: static;
  z-index: auto;
  margin-bottom: 0;
  border: none;
  box-shadow: none;
  padding-bottom: 0;
  background: transparent;
}

.trace-inline-panel {
  overflow: visible;
  border: 1px solid var(--color-primary-200);
  box-shadow: var(--shadow-md);
}

.trace-panel-sticky-bar {
  position: sticky;
  top: 0;
  z-index: 30;
  background: #fff;
  border-bottom: 1px solid var(--color-neutral-100);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.trace-inline-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5) 0;
  background: #fff;
}

.detail-tabs--in-bar {
  padding: 0 var(--space-5);
  margin-bottom: 0;
}

.detail-tabs--in-bar :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.detail-tabs--in-bar :deep(.el-tabs__content) {
  display: none;
}

.detail-tab-pane-body {
  padding-top: var(--space-3);
}

.detail-memo-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.memo-inline-chart {
  width: 100%;
  height: 220px;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  background: #fff;
}

.memo-online-text {
  margin: 0;
  padding: var(--space-4);
  max-height: min(480px, 50vh);
  overflow: auto;
  font-size: var(--text-sm);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  font-family: var(--font-mono, ui-monospace, monospace);
}

.trace-inline-panel-title h3 {
  margin: 0 0 4px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.trace-inline-id {
  font-size: var(--text-sm);
  color: var(--color-primary-600);
  word-break: break-all;
}

.trace-inline-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-body--inline {
  padding: 0 var(--space-5) var(--space-4);
  min-height: 200px;
}

.trace-records-toolbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.trace-records-toolbar-left {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.trace-records-toolbar-left h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
}

.trace-records-toolbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

:deep(.trace-row-focus) {
  background: color-mix(in srgb, var(--color-primary-100) 55%, #fff) !important;
}

.detail-tabs {
  margin-bottom: var(--space-4);
}

.detail-chart-panel {
  min-height: 200px;
}

.detail-inline-chart {
  width: 100%;
  height: 280px;
}

.detail-inline-chart--wide {
  height: 360px;
}

.analysis-chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.analysis-chart-card {
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-neutral-50);
}

.analysis-chart-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
  margin-bottom: 4px;
}

.analysis-chart-def {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin-bottom: var(--space-2);
  line-height: 1.4;
}

.analysis-chart-card .detail-inline-chart {
  height: 220px;
}

.viz-facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.html-preview-wrap {
  margin-top: var(--space-4);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.html-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  background: var(--color-neutral-50);
  border-bottom: 1px solid var(--color-neutral-200);
  font-size: var(--text-sm);
  font-weight: 600;
}

.html-preview-frame {
  width: 100%;
  height: min(560px, 55vh);
  border: none;
  background: #fff;
}

.chart-hint {
  margin: var(--space-2) 0;
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  text-align: center;
}

.trace-chart {
  width: 100%;
  height: 100%;
  min-height: 280px;
}

.trace-chart.is-hidden {
  visibility: hidden;
  pointer-events: none;
}

.chart-empty {
  position: absolute;
  inset: var(--space-4);
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--color-neutral-300);
  background: rgba(248, 250, 252, 0.92);
  border-radius: var(--radius-md);
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
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
}

.trace-time {
  font-size: var(--text-sm);
  color: var(--color-neutral-700);
}

.trace-time-relative {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
}

.degradation-s0 {
  color: var(--color-neutral-400);
  font-size: var(--text-sm);
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

.detail-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  margin-top: var(--space-2);
  border-top: 1px solid var(--color-neutral-100);
}

.detail-body {
  min-height: 160px;
}

.trace-layer-collapse {
  border: none;
  margin-bottom: var(--space-4);
}

.trace-layer-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  line-height: 1.3;
  padding: 4px 0;
  border-bottom: 1px solid var(--color-neutral-100);
}

.trace-layer-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.trace-layer-collapse :deep(.el-collapse-item__content) {
  padding: 0 0 var(--space-3);
}

.trace-layer-head--collapse {
  flex: 1;
  min-width: 0;
  border-bottom: none;
  padding: var(--space-2) 0;
  background: transparent;
}

.trace-layer-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: linear-gradient(90deg, color-mix(in srgb, var(--layer-accent) 12%, #fff), #fff);
  border-bottom: 2px solid var(--layer-accent);
  border-radius: var(--radius-md);
}

.trace-layer-id {
  font-size: var(--text-sm);
  font-weight: 800;
  color: #fff;
  background: var(--layer-accent);
  padding: 2px 8px;
  border-radius: 4px;
}

.trace-layer-titles { display: flex; flex-direction: column; gap: 1px; flex: 1; }
.trace-layer-cn { font-size: var(--text-lg); font-weight: 700; color: var(--color-neutral-800); }
.trace-layer-en { font-size: var(--text-sm); color: var(--color-neutral-400); }
.trace-layer-agent { font-size: var(--text-sm); color: var(--color-neutral-500); }
.trace-layer-count { font-size: var(--text-base); font-weight: 600; color: var(--color-neutral-400); font-variant-numeric: tabular-nums; }

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
  font-size: var(--text-sm);
  color: var(--color-neutral-500);
  background: var(--color-neutral-100);
  padding: 1px 6px;
  border-radius: 4px;
}

.stage-node-status {
  font-size: var(--text-sm);
  font-weight: 600;
}

.stage-node-status.is-success { color: var(--color-success); }
.stage-node-status.is-warning { color: var(--color-warning); }
.stage-node-status.is-danger { color: var(--color-danger); }
.stage-node-status.is-info { color: var(--color-primary-500); }

.stage-node-subline {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin-bottom: var(--space-1);
}

.stage-node-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.stage-node-duration {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.stage-node-desc {
  font-size: var(--text-sm);
  color: var(--color-neutral-500);
  line-height: var(--leading-relaxed);
}

.detail-summary {
  margin-bottom: var(--space-4);
}

@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
