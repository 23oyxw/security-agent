<template>
  <div class="l5-page page-theme-ops">
    <header class="l5-hero">
      <div>
        <h1 class="l5-title">L5 链路量化分析</h1>
        <p class="l5-core">
          依托统计模型识别链路异常，散点图定位单点偶发故障、热力图锁定批量区域故障，联动链路追踪拆解调用栈，精准定位故障位置、自动追溯链路根源。
        </p>
      </div>
      <div class="l5-hero-meta">
        <el-tag type="info" effect="plain">模型：3σ + IQR · 加权密度</el-tag>
        <el-tag type="success" effect="plain">绘图：ECharts</el-tag>
        <el-tag v-if="scatter?.anomaly_count != null" type="danger" effect="plain">
          异常 {{ scatter.anomaly_count }} 点
        </el-tag>
      </div>
    </header>

    <!-- 六维量化 + 各层对照 -->
    <section class="l5-metrics-row">
      <article class="l5-card l5-card--wide">
        <header class="card-head">
          <h2>L5 六维量化指标</h2>
          <span class="card-sub">{{ L5_FORMULA }}</span>
        </header>
        <div class="metric-grid">
          <div v-for="m in metricValues" :key="m.key" class="metric-cell" :style="{ '--mc': m.color }">
            <span class="metric-label">{{ m.label }}</span>
            <span class="metric-val">{{ m.value != null ? m.value + '%' : '—' }}</span>
            <span class="metric-src">{{ m.sourceLayer }}</span>
          </div>
        </div>
        <ul v-if="evolutionHints.length" class="evolve-hints">
          <li v-for="(h, i) in evolutionHints" :key="i">{{ h }}</li>
        </ul>
      </article>
      <article class="l5-card">
        <header class="card-head"><h2>各层数据对照</h2></header>
        <table class="cross-table">
          <thead><tr><th>层</th><th>Agent</th><th>产出</th><th>馈入 L5</th></tr></thead>
          <tbody>
            <tr v-for="r in L5_LAYER_CROSS" :key="r.layer">
              <td>{{ r.layer }}</td><td>{{ r.agent }}</td><td>{{ r.data }}</td><td>{{ r.feeds }}</td>
            </tr>
          </tbody>
        </table>
      </article>
    </section>

    <section class="l5-grid">
      <article class="l5-card">
        <header class="card-head">
          <h2>散点图 · 单点/偶发异常</h2>
          <span class="card-sub">{{ scatter?.definition || '加载中…' }}</span>
        </header>
        <div ref="scatterRef" class="chart-box" />
        <p v-if="selectedTrace" class="trace-hint">
          选中 <code>{{ selectedTrace.trace_id }}</code> · 路径 {{ selectedTrace.path_id }}
          <el-button link type="primary" size="small" @click="loadRootCause(selectedTrace.trace_id)">溯源</el-button>
        </p>
      </article>

      <article class="l5-card">
        <header class="card-head">
          <h2>热力图 · 时段/集群异常</h2>
          <span class="card-sub">{{ heatmap?.definition || '加载中…' }}</span>
        </header>
        <div ref="heatmapRef" class="chart-box" />
      </article>
    </section>

    <section class="l5-grid l5-grid--split">
      <article class="l5-card">
        <header class="card-head">
          <h2>链路溯源闭环</h2>
          <span class="card-sub">Trace/Span → 调用链拆解 → 根因输出</span>
        </header>
        <div v-if="rootCause" class="root-cause">
          <div class="rc-summary">
            <strong>{{ rootCause.root_cause }}</strong>
            <span v-if="rootCause.trace_id" class="rc-id">{{ rootCause.trace_id }}</span>
          </div>
          <ol class="rc-steps">
            <li v-for="(s, i) in rootCause.steps" :key="i">{{ s }}</li>
          </ol>
          <div class="rc-spans">
            <div v-for="sp in rootCause.spans" :key="sp.name" class="rc-span" :class="{ err: sp.error }">
              <span>{{ sp.name }}</span>
              <span>{{ sp.duration_ms }} ms</span>
            </div>
          </div>
          <div ref="waterfallRef" class="chart-box chart-box--sm" />
          <p class="chain-note">调用链拆解：网关 → 服务 → 中间件 → 数据库（对比基线锁定最慢/报错节点）</p>
          <el-button v-if="rootCause.trace_id" size="small" @click="goTrace(rootCause.trace_id)">打开 L4 卷宗</el-button>
        </div>
        <el-empty v-else description="点击散点图中的异常点进行溯源" :image-size="64" />
      </article>

      <article class="l5-card">
        <header class="card-head">
          <h2>集成测试 · 模块链路</h2>
          <span class="card-sub">{{ catalog?.method || '分层集成 + 链路矩阵' }}</span>
        </header>
        <div class="test-toolbar">
          <el-checkbox v-model="selectAll" :indeterminate="indeterminate" @change="toggleAll">全选</el-checkbox>
          <el-button type="primary" size="small" :loading="testRunning" @click="runTests">运行选中</el-button>
          <el-button size="small" :loading="testRunning" @click="runTestsAll">跑全链路</el-button>
        </div>
        <el-checkbox-group v-model="selectedTests" class="test-list">
          <label v-for="t in catalog?.tests || []" :key="t.id" class="test-row">
            <el-checkbox :value="t.id">
              <span class="test-name">{{ t.name }}</span>
              <el-tag size="small" effect="plain">{{ t.layer }}</el-tag>
            </el-checkbox>
          </label>
        </el-checkbox-group>
        <div v-if="testResult" class="test-result">
          <div class="test-stats">
            通过 {{ testResult.passed }}/{{ testResult.total }} · {{ testResult.pass_rate }}%
          </div>
          <div v-for="r in testResult.results" :key="r.id" class="test-item" :class="r.status">
            <span>{{ r.name }}</span>
            <span>{{ r.status }} · {{ r.elapsed_ms }}ms</span>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  fetchL5Scatter,
  fetchL5Heatmap,
  fetchL5RootCause,
  fetchL5IntegrationCatalog,
  runL5Integration,
} from '../api/l5'
import api from '../api'
import {
  L5_FORMULA,
  L5_LAYER_CROSS,
  buildL5MetricValues,
  buildEvolutionHints,
} from '../constants/l5-metrics'
import { useAgentStore } from '../stores/agent'

const agentStore = useAgentStore()
const router = useRouter()

const scatter = ref(null)
const heatmap = ref(null)
const rootCause = ref(null)
const catalog = ref(null)
const testResult = ref(null)
const testRunning = ref(false)
const selectedTests = ref([])
const selectedTrace = ref(null)

const route = useRoute()
const metricValues = ref(buildL5MetricValues({}))
const evolutionHints = ref([])

const waterfallRef = ref(null)
const scatterRef = ref(null)
const heatmapRef = ref(null)
let waterfallChart = null
let scatterChart = null
let heatmapChart = null

const selectAll = computed({
  get() {
    const all = catalog.value?.tests?.map(t => t.id) || []
    return all.length > 0 && selectedTests.value.length === all.length
  },
  set(v) {
    selectedTests.value = v ? (catalog.value?.tests?.map(t => t.id) || []) : []
  },
})

const indeterminate = computed(() => {
  const n = catalog.value?.tests?.length || 0
  return selectedTests.value.length > 0 && selectedTests.value.length < n
})

function toggleAll(v) {
  selectAll.value = v
}

function goTrace(traceId) {
  router.push({ path: '/trace', query: { id: traceId } })
}

async function loadRootCause(traceId) {
  rootCause.value = await fetchL5RootCause(traceId)
  await nextTick()
  renderWaterfall()
}

function renderWaterfall() {
  if (!waterfallRef.value || !rootCause.value?.spans?.length) return
  if (!waterfallChart) waterfallChart = echarts.init(waterfallRef.value)
  const spans = rootCause.value.spans
  waterfallChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: spans.map(s => s.name), axisLabel: { rotate: 20, fontSize: 10 } },
    yAxis: { type: 'value', name: 'ms' },
    series: [{
      type: 'bar',
      data: spans.map(s => ({
        value: s.duration_ms,
        itemStyle: { color: s.error ? '#ef4444' : '#0ea5e9' },
      })),
    }],
  })
}

async function loadEvalMetrics() {
  try {
    const ev = await api.get('/eval/score')
    metricValues.value = buildL5MetricValues(ev?.dimension_scores || {})
    evolutionHints.value = buildEvolutionHints(metricValues.value)
  } catch { /* mock/offline */ }
}

function renderScatter() {
  if (!scatterRef.value || !scatter.value?.points?.length) return
  if (!scatterChart) scatterChart = echarts.init(scatterRef.value)
  const pts = scatter.value.points
  const normal = pts.filter(p => !p.is_anomaly).map(p => [p.latency_ms, p.error_rate, p.jitter_ms, p.trace_id, p.path_id])
  const anomaly = pts.filter(p => p.is_anomaly).map(p => [p.latency_ms, p.error_rate, p.jitter_ms, p.trace_id, p.path_id])

  scatterChart.setOption({
    tooltip: {
      formatter(p) {
        const d = p.data
        return `Trace ${d[3]}<br/>耗时 ${d[0]}ms · 错误率 ${d[1]}%<br/>抖动 ${d[2]}ms · 路径 ${d[4]}`
      },
    },
    grid: { left: 48, right: 24, top: 32, bottom: 40 },
    xAxis: { name: '耗时(ms)', type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
    yAxis: { name: '错误率(%)', type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
    series: [
      {
        name: '正常',
        type: 'scatter',
        symbolSize: d => Math.max(8, Math.min(28, d[2] / 8)),
        itemStyle: { color: '#3b82f6', opacity: 0.75 },
        data: normal,
      },
      {
        name: '离群/异常',
        type: 'scatter',
        symbolSize: d => Math.max(10, Math.min(32, d[2] / 6)),
        itemStyle: { color: '#ef4444', borderColor: '#fecaca', borderWidth: 1 },
        data: anomaly,
      },
    ],
  })
  scatterChart.off('click')
  scatterChart.on('click', params => {
    const d = params.data
    selectedTrace.value = { trace_id: d[3], path_id: d[4] }
    loadRootCause(d[3])
  })
}

function renderHeatmap() {
  if (!heatmapRef.value || !heatmap.value?.matrix?.length) return
  if (!heatmapChart) heatmapChart = echarts.init(heatmapRef.value)
  const { x_labels: xl, y_labels: yl, matrix } = heatmap.value
  const data = []
  matrix.forEach((row, yi) => {
    row.forEach((val, xi) => data.push([xi, yi, val]))
  })
  const maxVal = Math.max(...data.map(d => d[2]), 1)

  heatmapChart.setOption({
    tooltip: { position: 'top' },
    grid: { left: 80, right: 24, top: 24, bottom: 48 },
    xAxis: { type: 'category', data: xl, splitArea: { show: true } },
    yAxis: { type: 'category', data: yl, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#0f172a', '#0369a1', '#f59e0b', '#ef4444'] },
    },
    series: [{
      type: 'heatmap',
      data,
      label: { show: false },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' } },
    }],
  })
}

async function loadCharts() {
  scatter.value = await fetchL5Scatter()
  heatmap.value = await fetchL5Heatmap()
  await nextTick()
  renderScatter()
  renderHeatmap()
  const qTrace = route.query.trace
    || agentStore.lastExecute?.trace_id
    || agentStore.lastAudit?.trace_id
  if (qTrace) {
    selectedTrace.value = { trace_id: qTrace, path_id: '' }
    await loadRootCause(qTrace)
  } else {
    const first = scatter.value.points?.find(p => p.is_anomaly) || scatter.value.points?.[0]
    if (first?.trace_id) {
      selectedTrace.value = { trace_id: first.trace_id, path_id: first.path_id }
      await loadRootCause(first.trace_id)
    }
  }
}

async function loadCatalog() {
  catalog.value = await fetchL5IntegrationCatalog()
  selectedTests.value = catalog.value.tests?.map(t => t.id) || []
}

async function runTests() {
  testRunning.value = true
  try {
    testResult.value = await runL5Integration(selectedTests.value.length ? selectedTests.value : null)
    ElMessage.success(`集成测试完成：${testResult.value.passed}/${testResult.value.total} 通过`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    testRunning.value = false
  }
}

function runTestsAll() {
  selectedTests.value = catalog.value?.tests?.map(t => t.id) || []
  runTests()
}

function onResize() {
  scatterChart?.resize()
  heatmapChart?.resize()
  waterfallChart?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    await Promise.all([loadCharts(), loadCatalog(), loadEvalMetrics()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || 'L5 数据加载失败')
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  scatterChart?.dispose()
  heatmapChart?.dispose()
  waterfallChart?.dispose()
})

watch(() => route.query.trace, tid => {
  if (tid) loadRootCause(tid)
})
</script>

<style scoped>
.l5-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-6);
}

.l5-hero {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(15, 23, 42, 0.6));
  border: 1px solid rgba(14, 165, 233, 0.25);
}

.l5-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
}

.l5-core {
  margin: 0;
  max-width: 52rem;
  color: var(--color-text-secondary);
  line-height: 1.55;
  font-size: var(--text-sm);
}

.l5-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: flex-start;
}

.l5-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.l5-grid--split {
  align-items: start;
}

.l5-card {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid var(--color-border-default);
}

.card-head h2 {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
}

.card-sub {
  display: block;
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.chart-box {
  height: 280px;
  margin-top: var(--space-3);
}

.trace-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.root-cause {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.rc-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.rc-id {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.rc-steps {
  margin: 0;
  padding-left: 1.25rem;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.rc-spans {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.rc-span {
  display: flex;
  justify-content: space-between;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  font-size: var(--text-sm);
}

.rc-span.err {
  border-left: 3px solid #ef4444;
}

.test-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  margin: var(--space-3) 0;
}

.test-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.test-row {
  display: block;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.03);
}

.test-name {
  margin-right: var(--space-2);
}

.test-result {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
}

.test-stats {
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.test-item {
  display: flex;
  justify-content: space-between;
  padding: var(--space-1) 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.test-item.pass { color: #22c55e; }
.test-item.fail { color: #ef4444; }

.l5-metrics-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-4);
}

.l5-card--wide { grid-column: span 1; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.metric-cell {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--mc);
  background: rgba(255, 255, 255, 0.04);
}

.metric-label { display: block; font-size: 12px; color: var(--color-text-muted); }
.metric-val { display: block; font-size: 22px; font-weight: 700; margin: 4px 0; }
.metric-src { font-size: 10px; color: var(--color-text-muted); }

.evolve-hints {
  margin: var(--space-3) 0 0;
  padding-left: 1.25rem;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.cross-table {
  width: 100%;
  margin-top: var(--space-2);
  font-size: 11px;
  border-collapse: collapse;
}

.cross-table th,
.cross-table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
}

.chart-box--sm { height: 180px; margin-top: var(--space-2); }

.chain-note {
  margin: var(--space-2) 0 0;
  font-size: 11px;
  color: var(--color-text-muted);
}

@media (max-width: 960px) {
  .l5-metrics-row { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 960px) {
  .l5-grid {
    grid-template-columns: 1fr;
  }
}
</style>
