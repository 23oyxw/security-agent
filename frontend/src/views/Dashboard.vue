<template>
  <div class="dashboard-root">
    <!-- 左侧操作面板 -->
    <aside class="ops-drawer" :class="{ collapsed: drawerClosed }">
      <div class="drawer-toggle" @click="drawerClosed = !drawerClosed">
        <el-icon :size="16"><component :is="drawerClosed ? 'Expand' : 'Fold'" /></el-icon>
      </div>
      <div v-if="!drawerClosed" class="drawer-body">
        <el-collapse v-model="activeDrawerGroups">
          <el-collapse-item name="ops">
            <template #title>
              <span class="collapse-title"><el-icon :size="14"><MagicStick /></el-icon> 快捷操作</span>
            </template>
            <div class="drawer-section">
              <span class="drawer-section-title">CPU 压测</span>
              <div class="drawer-actions">
                <el-button size="small" type="danger" :loading="stressLoading" @click="runStress(10)">10s</el-button>
                <el-button size="small" type="danger" :loading="stressLoading" @click="runStress(30)">30s</el-button>
              </div>
              <div v-if="stressResult" class="drawer-result">{{ stressResult.split('\n')[0] }}</div>
            </div>
            <div class="drawer-section">
              <span class="drawer-section-title">进程管理</span>
              <div class="drawer-actions">
                <el-button size="small" :loading="procLoading" @click="refreshProc">刷新</el-button>
              </div>
              <div v-if="procSummary" class="drawer-result">
                {{ procSummary.total_processes }} 进程 · {{ procSummary.zombies || 0 }} 僵尸
              </div>
            </div>
          </el-collapse-item>

          <el-collapse-item name="filter">
            <template #title>
              <span class="collapse-title"><el-icon :size="14"><DataAnalysis /></el-icon> 数据筛选</span>
            </template>
            <div class="drawer-section">
              <span class="drawer-section-title">告警级别</span>
              <el-select v-model="alertFilter" size="small" class="drawer-select">
                <el-option label="全部" value="" />
                <el-option label="严重" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
              </el-select>
            </div>
            <div class="drawer-section">
              <span class="drawer-section-title">刷新间隔</span>
              <el-select v-model="pollSec" size="small" class="drawer-select">
                <el-option label="5 秒" :value="5" />
                <el-option label="10 秒" :value="10" />
                <el-option label="30 秒" :value="30" />
              </el-select>
            </div>
            <div class="drawer-section">
              <el-button size="small" icon="Refresh" @click="fetchAll" class="drawer-btn-full">立即刷新</el-button>
            </div>
          </el-collapse-item>

          <el-collapse-item name="detail">
            <template #title>
              <span class="collapse-title"><el-icon :size="14"><Document /></el-icon> 辅助明细</span>
            </template>
            <div class="drawer-section">
              <span class="drawer-section-title">监听端口 (Top 10)</span>
              <div class="port-list">
                <div v-for="p in osPorts.slice(0, 10)" :key="p.port" class="port-line">
                  <code class="port-code">{{ p.port }}</code>
                  <span class="port-process">{{ p.process?.slice(0, 28) }}</span>
                </div>
                <span v-if="!osPorts.length" class="text-hint">加载中...</span>
              </div>
            </div>
            <div class="drawer-section">
              <span class="drawer-section-title">可用模块</span>
              <div class="module-tags">
                <el-tag v-for="(v, k) in modules" :key="k" size="small" :type="v === 'active' ? 'success' : 'danger'" effect="plain">{{ k }}</el-tag>
              </div>
            </div>
            <div class="drawer-section">
              <el-button size="small" text type="primary" @click="$router.push('/trace')" class="drawer-btn-full">查看 Trace →</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <PageHeader
        :title="pageMeta.label"
        :subtitle="pageMeta.subtitle"
        :layer="pageMeta.layer || ''"
        :layer-label="pageMeta.layerLabel"
      >
        <template #actions>
          <el-button size="small" type="primary" @click="$router.push('/l5')">L5 链路量化</el-button>
          <el-button size="small" @click="$router.push('/canvas')">架构画布</el-button>
          <el-button size="small" @click="$router.push(buildAgentRoute('pipeline'))">L1 对话</el-button>
          <el-button size="small" @click="$router.push('/trace')">L4 Trace</el-button>
        </template>
      </PageHeader>

      <!-- 五层快捷轨 -->
      <section class="l5-pipeline-strip reveal-item">
        <div
          v-for="step in pipelineSteps"
          :key="step.id"
          class="l5-pipeline-step motion-lift"
          @click="$router.push(step.to)"
        >
          <span class="l5-step-badge">{{ step.id }}</span>
          <span class="l5-step-label">{{ step.label }}</span>
        </div>
      </section>

      <!-- L5 六维指标 -->
      <section class="metrics-section reveal-item reveal-delay-1">
        <header class="section-head">
          <h2 class="section-title">L5 量化指标</h2>
          <span class="section-hint">意图准确率 · 边界召回 · 修复成功率 · 调度利用率 · 批量合规 · 工具命中</span>
        </header>
        <div class="metric-cards">
          <div
            v-for="(s, idx) in l5MetricCards"
            :key="s.key"
            class="metric-card motion-lift"
            :class="`stagger-${idx + 1}`"
          >
            <div class="metric-accent" :style="{ background: s.color }"></div>
            <div class="metric-body">
              <span class="metric-value" :style="{ color: s.color }">{{ s.displayValue }}</span>
              <span class="metric-label">{{ s.label }}</span>
              <span class="metric-sub">{{ s.sourceLayer }} · {{ s.desc }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ====== SECTION 2: 图表 & 评估 ====== -->
      <section class="charts-row reveal-item reveal-delay-2">
        <!-- L1 静态感知绘图（L5 子场景） -->
        <div class="panel-card chart-panel">
          <header class="panel-header">
            <span class="panel-title">
              <el-icon :size="16"><Monitor /></el-icon>
              L1 静态感知绘图
            </span>
            <el-tag size="small" type="info" effect="plain">数学模型 · L5 复盘</el-tag>
          </header>
          <div class="panel-body">
            <div ref="resourceBar" class="chart-container"></div>
            <div class="chart-footer">
              {{ loadStr }} — {{ loadTip }} · 实时 /api/perception/metrics
              <span v-if="metricsUpdatedAt"> · 更新 {{ metricsUpdatedAt }}</span>
            </div>
          </div>
        </div>

        <!-- L5 Agent 评估 -->
        <div class="panel-card eval-panel-card">
          <header class="panel-header">
            <span class="panel-title">
              <el-icon :size="16"><DataAnalysis /></el-icon>
              L5 综合评估
            </span>
            <el-tag size="small" effect="plain">audit_iteration</el-tag>
          </header>
          <div class="panel-body">
            <div v-if="evalScore" class="eval-content">
              <div class="eval-grade" :class="'grade-' + evalScore.grade">{{ evalScore.grade }}</div>
              <span class="eval-composite">{{ evalScore.composite }} 分</span>
              <span class="eval-meta">综合评估 · {{ evalScore.total_evaluations || '—' }} 次</span>

              <div class="eval-dims">
                <div v-for="m in l5MetricCards.filter(x => x.value != null)" :key="m.key" class="eval-dim">
                  <span class="eval-dim-name">{{ m.label }}</span>
                  <el-progress
                    :percentage="m.value"
                    :stroke-width="4"
                    :show-text="false"
                    :color="progressColor(m.value)"
                    class="eval-dim-bar"
                  />
                  <span class="eval-dim-val">{{ m.value }}%</span>
                </div>
              </div>

              <div class="eval-stats">
                <span>Token: {{ evalScore.tokens || '—' }}</span>
                <span>效率比: {{ evalScore.efficiency_ratio || '—' }}</span>
                <span>Trace: {{ traceMetrics.avg_stages || '—' }}阶 · {{ traceMetrics.avg_duration_ms ? (traceMetrics.avg_duration_ms / 1000).toFixed(1) + 's' : '—' }}</span>
              </div>

              <!-- Mini 趋势图 -->
              <div v-if="trendPoints?.length" class="trend-mini">
                <div
                  v-for="(p, i) in trendPoints"
                  :key="i"
                  class="trend-bar"
                  :class="'trend-' + p.grade"
                  :style="{ height: trendBarHeight(p.score) }"
                  :title="'#' + p.n + ' ' + p.score + '分 ' + p.tokens + 'tokens'"
                ></div>
              </div>
              <span class="trend-hint">最近 10 次评分趋势</span>
            </div>
            <el-empty v-else description="完成 L1→L5 全流程后自动生成 L5 指标" :image-size="48" />
          </div>
        </div>
      </section>

      <!-- 各层对照 + 策略自进化 -->
      <section class="l5-cross-row reveal-item reveal-delay-3">
        <div class="panel-card">
          <header class="panel-header">
            <span class="panel-title">各层数据对照</span>
          </header>
          <div class="panel-body">
            <el-table :data="layerCross" size="small" stripe class="cross-table">
              <el-table-column prop="layer" label="层" width="56" />
              <el-table-column prop="agent" label="Agent" width="140" />
              <el-table-column prop="data" label="共享数据" min-width="160" />
              <el-table-column prop="feeds" label="馈入 L5" min-width="160" />
            </el-table>
          </div>
        </div>
        <div class="panel-card">
          <header class="panel-header">
            <span class="panel-title">策略自进化建议</span>
          </header>
          <div class="panel-body">
            <ul class="evolution-list">
              <li v-for="(hint, i) in evolutionHints" :key="i">{{ hint }}</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- ====== SECTION 3: 压测结果 ====== -->
      <section v-if="stressResult" class="alert-section">
        <el-alert type="info" :closable="false" class="stress-alert">
          {{ stressResult }}
        </el-alert>
      </section>

      <!-- ====== SECTION 4: Skill Flow 测试（运维辅助） ====== -->
      <section class="test-section">
        <el-collapse>
          <el-collapse-item title="⚡ L3 封装流程抽测（运维辅助）" name="test">
            <div class="test-grid">
              <div v-for="tc in testCases" :key="tc.key" class="test-case">
                <span class="test-name">{{ tc.label }}</span>
                <span class="test-desc">{{ tc.description }}</span>
                <el-tag v-if="tc.status === 'ok'" type="success" size="small">✓</el-tag>
                <el-tag v-else-if="tc.status === 'blocked'" type="warning" size="small">⊘</el-tag>
                <el-tag v-else-if="tc.status === 'fail'" type="danger" size="small">✗</el-tag>
                <span v-else class="test-pending">—</span>
                <el-button size="small" text type="primary" :loading="tc.status === 'running'" @click="runSingleTest(tc)">测试</el-button>
              </div>
            </div>
            <div class="test-actions">
              <el-button type="primary" size="small" :loading="testAllLoading" @click="runAllTests">全部运行</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </section>

      <!-- ====== SECTION 5: 最近告警 ====== -->
      <section class="alerts-section">
        <div class="panel-card alerts-panel">
          <header class="panel-header">
            <span class="panel-title">
              <el-icon :size="16"><BellFilled /></el-icon>
              最近告警
            </span>
            <el-button text type="primary" size="small" @click="$router.push('/alerts')">查看全部 →</el-button>
          </header>
          <div class="panel-body">
            <el-table :data="alerts.slice(0, 5)" size="small" stripe empty-text="暂无告警" class="alerts-table">
              <el-table-column prop="timestamp" label="时间" width="160" />
              <el-table-column prop="level" label="级别" width="70">
                <template #default="{ row }">
                  <el-tag :type="sevColor(row.level)" size="small">{{ row.level }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="内容" show-overflow-tooltip />
            </el-table>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Monitor, DataAnalysis, BellFilled, MagicStick, Document } from '@element-plus/icons-vue'
import { initChart, scheduleChartResize } from '../composables/useEcharts'
import {
  chartGrid, chartTooltip, categoryAxis, valueAxis,
  metricBarData,
} from '../utils/chartTheme'
import api from '../api'
import { useAlertsStore } from '../stores/alerts'
import { useEvalStore } from '../stores/eval'
import { useMetricsStore } from '../stores/metrics'
import PageHeader from '../components/common/PageHeader.vue'
import { buildAgentRoute } from '../constants/navigation'
import { usePageMeta } from '../composables/usePageMeta'
import { SIDEBAR_LAYERS } from '../constants/pipeline-architecture'
import {
  L5_LAYER_CROSS,
  buildL5MetricValues,
  buildEvolutionHints,
} from '../constants/l5-metrics'

const alertsStore = useAlertsStore()
const evalStore = useEvalStore()
const metricsStore = useMetricsStore()
const { pageMeta } = usePageMeta('dashboard')

/* ---- Refs ---- */
const resourceBar = ref(null)
const drawerClosed = ref(false)
const activeDrawerGroups = ref(['ops'])
const alertFilter = ref('')
const pollSec = ref(10)

/* ---- Data ---- */
const alerts = ref([])
const modules = ref({})
const osPorts = ref([])
const procSummary = ref(null)
const procLoading = ref(false)
const stressLoading = ref(false)
const stressResult = ref('')
const testAllLoading = ref(false)
const evalScore = ref(null)
const evalDims = ref({})
const traceMetrics = ref({ avg_stages: 0, avg_duration_ms: 0, total_traces: 0 })
const trendPoints = ref([])

let pollTimer = null

const loadStr = ref('—')
const loadTip = ref('')
const metricsUpdatedAt = ref('')

const layerCross = L5_LAYER_CROSS

const pipelineSteps = SIDEBAR_LAYERS.map(l => ({
  id: l.id,
  label: l.name,
  to: l.id === 'L1' || l.id === 'L3'
    ? buildAgentRoute('pipeline')
    : l.id === 'L2'
      ? { path: '/safety' }
      : l.id === 'L4'
        ? { path: '/trace' }
        : { path: '/l5' },
}))

const l5MetricCards = computed(() => {
  const items = buildL5MetricValues(evalDims.value)
  return items.map(m => ({
    ...m,
    displayValue: m.value != null ? `${m.value}%` : '—',
  }))
})

const evolutionHints = computed(() => buildEvolutionHints(l5MetricCards.value))

/* 系统快照（供 L1 静态绘图图表，非 L5 主指标） */
const statCards = reactive([
  { key: 'cpu',    label: 'CPU',     value: '--%',   sub: '使用率', color: 'var(--color-metric-cpu)' },
  { key: 'memory', label: '内存',     value: '--%',   sub: '已用',   color: 'var(--color-metric-memory)' },
  { key: 'disk',   label: '磁盘',     value: '--%',   sub: '使用率', color: 'var(--color-metric-disk)' },
  { key: 'process',label: '进程',     value: '--',    sub: '总数',   color: 'var(--color-metric-process)' },
  { key: 'load',   label: '负载1m',   value: '--',    sub: '1/5/15min', color: 'var(--color-metric-load)' },
  { key: 'uptime', label: '运行',     value: '--h',   sub: 'uptime',  color: 'var(--color-metric-uptime)' },
])

const testCases = reactive([
  { key: 'scan',         label: '安全扫描',       flow: 'scan_report',        description: '进程/端口+报告', status: '', elapsed_ms: null },
  { key: 'exec_safe',    label: '安全命令',       flow: 'secure_exec',        description: 'ls (放行)', status: '', elapsed_ms: null, context: { command: 'ls -la /tmp', user_message: '查看', user_confirmed: true } },
  { key: 'exec_block',   label: '拦截命令',       flow: 'secure_exec',        description: 'rm -rf / (拦截)', status: '', elapsed_ms: null, context: { command: 'rm -rf /', user_message: '删除', user_confirmed: false } },
  { key: 'cleanup_scan', label: '清理扫描',       flow: 'system_cleanup_scan', description: '扫描可清理', status: '', elapsed_ms: null },
  { key: 'cleanup_run',  label: '清理执行',       flow: 'system_cleanup_run',  description: 'apt/log', status: '', elapsed_ms: null, context: { categories: ['apt', 'journal', 'log'] } },
  { key: 'alert',        label: '告警响应',       flow: 'alert_response',      description: '模拟告警路由', status: '', elapsed_ms: null, context: { alert_event: { message: 'CPU>90%', level: '高' } } },
])

/* ---- 工具函数 ---- */
function progressColor(p) {
  if (p > 85) return 'var(--color-danger)'
  if (p > 70) return 'var(--color-warning)'
  return 'var(--color-success-muted)'
}

function sevColor(s) {
  const lvl = String(s || '').toLowerCase()
  return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[lvl] || 'info'
}

function trendBarHeight(score) {
  return `${Math.max(4, (score / 100) * 28)}px`
}

function formatUptime(sec) {
  const s = Math.max(0, Math.floor(sec || 0))
  return `${Math.floor(s / 3600)}h${Math.floor((s % 3600) / 60)}m`
}

function applyPerceptionMetrics(perc) {
  if (!perc) return
  const cpu = Math.round(perc.cpu_percent ?? 0)
  const mem = Math.round(perc.memory_percent ?? 0)
  const disk = Math.round(perc.disk_percent ?? 0)
  statCards[0].value = `${cpu}%`
  statCards[1].value = `${mem}%`
  statCards[2].value = `${disk}%`
  if (perc.process_count != null) statCards[3].value = String(perc.process_count)
  const la = perc.load_avg || []
  if (la.length) {
    statCards[4].value = la.map(x => Number(x).toFixed(2)).join(' / ')
    loadStr.value = `负载 ${statCards[4].value}`
    const l1 = parseFloat(la[0]) || 0
    const cores = 8
    loadTip.value = l1 <= cores * 0.5 ? '轻载' : l1 <= cores * 0.8 ? '中载' : l1 <= cores * 1.5 ? '高载' : '过载'
  }
  if (perc.uptime_seconds != null) {
    statCards[5].value = formatUptime(perc.uptime_seconds)
  }
  metricsUpdatedAt.value = metricsStore.lastUpdated || new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

/* ---- 数据获取 ---- */
async function fetchAll() {
  try {
    const [flow, health, mcpRes, evalRes, portsRes] = await Promise.allSettled([
      api.get('/workflow/flow-status'),
      api.get('/health'),
      api.get('/mcp/servers'),
      evalStore.fetchScore({ force: true, maxAgeMs: 0 }),
      api.get('/perception/os/ports'),
    ])
    await metricsStore.fetchMetrics()
    applyPerceptionMetrics(metricsStore.raw)

    if (portsRes.status === 'fulfilled' && portsRes.value) {
      const list = portsRes.value.ports || portsRes.value.listening || portsRes.value.items || []
      osPorts.value = Array.isArray(list) ? list : []
    }

    if (health?.value?.modules) modules.value = health.value.modules
    if (evalRes?.value?.latest) {
      const e = evalRes.value.latest
      evalScore.value = { ...e, total_evaluations: evalRes.value.total_evaluations, efficiency_ratio: evalRes.value.efficiency_ratio }
      evalDims.value = evalRes.value.dimension_scores || {}
      traceMetrics.value = evalRes.value.trace_metrics || {}
      trendPoints.value = evalRes.value.trend_points || []
    }
    // flow-status 仅补充编排层节点，不再覆盖 CPU/内存/磁盘真实读数
    if (flow?.value?.layers?.collection) {
      const ns = flow.value.layers.collection.nodes || []
      const byId = {}
      ns.forEach(n => { byId[n.id] = n })
      if (!metricsStore.raw?.process_count && byId.C4?.value) {
        statCards[3].value = byId.C4.value
      }
      const ut = flow.value.uptime_seconds
      if (ut && !metricsStore.raw?.uptime_seconds) {
        statCards[5].value = formatUptime(ut)
      }
    }
    await alertsStore.fetchRecent(5)
    alerts.value = alertsStore.recent || []
    nextTick(renderChart)
  } catch {/* silent */}
}

async function refreshProc() {
  procLoading.value = true
  try { procSummary.value = await api.get('/ops/processes/summary') } catch {/* silent */}
  finally { procLoading.value = false }
}

async function runStress(duration) {
  stressLoading.value = true
  stressResult.value = `⏳ ${duration}秒压测中...`
  try {
    const res = await api.post('/ops/cpu/stress', null, { params: { duration, cores: 0 } })
    const a = res.analysis || {}
    stressResult.value = [
      `🔬 ${a.summary || ''}`,
      a.bottlenecks?.length ? `⚠️ ${a.bottlenecks.join('; ')}` : '✅ 无瓶颈',
    ].join('\n')
    setTimeout(fetchAll, 2000)
  } catch (e) { stressResult.value = '压测失败: ' + (e.message || '') }
  finally { stressLoading.value = false }
}

async function runSingleTest(tc) {
  tc.status = 'running'
  const t0 = Date.now()
  try {
    const res = await api.post(`/skills/flows/${tc.flow}/run`, { context: tc.context || {} })
    tc.elapsed_ms = Date.now() - t0
    const blocked = (res.steps || []).some(s => s.blocked)
    tc.status = blocked ? 'blocked' : (res.ok ? 'ok' : 'fail')
  } catch { tc.status = 'fail'; tc.elapsed_ms = Date.now() - t0 }
}
async function runAllTests() { testAllLoading.value = true; for (const tc of testCases) await runSingleTest(tc); testAllLoading.value = false }

/* ---- ECharts ---- */
let chartInstance = null
async function renderChart() {
  if (!resourceBar.value) return
  if (!chartInstance) chartInstance = await initChart(resourceBar.value)
  if (!chartInstance) return
  chartInstance.setOption({
    tooltip: chartTooltip(),
    grid: chartGrid(),
    xAxis: categoryAxis(['CPU', '内存', '磁盘']),
    yAxis: valueAxis({ max: 100, axisLabel: { formatter: '{value}%', color: '#475569', fontSize: 11 } }),
    series: [{
      type: 'bar',
      barWidth: 50,
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11, color: '#334155' },
      data: metricBarData([
        parseFloat(statCards[0].value) || 0,
        parseFloat(statCards[1].value) || 0,
        parseFloat(statCards[2].value) || 0,
      ]),
    }],
  }, true)
  scheduleChartResize(chartInstance)
}

const resizeHandler = () => chartInstance?.resize()

watch(pollSec, (v) => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = setInterval(fetchAll, v * 1000) }
})

watch(
  () => [metricsStore.cpuPercent, metricsStore.memoryPercent, metricsStore.diskPercent, metricsStore.lastUpdated],
  () => {
    applyPerceptionMetrics(metricsStore.raw)
    nextTick(renderChart)
  },
)

onMounted(() => {
  fetchAll()
  refreshProc()
  pollTimer = setInterval(fetchAll, pollSec.value * 1000)
  window.addEventListener('resize', resizeHandler)
})
onUnmounted(() => {
  clearInterval(pollTimer)
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
})
</script>

<style scoped>
/* ============================================================
   Dashboard — 安全运维仪表盘 (Professional Refinement v2)
   全部使用 design tokens，零硬编码
   ============================================================ */

.dashboard-root {
  display: flex;
  height: calc(100vh - var(--topbar-height));
  overflow: hidden;
}

/* ============================== */
/* 左侧操作面板                    */
/* ============================== */
.ops-drawer {
  background: var(--glass-topbar, var(--color-surface-overlay));
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-right: 1px solid var(--color-border-default);
  transition: width var(--duration-slow) var(--ease-out), opacity var(--duration-normal) var(--ease-out);
  flex-shrink: 0;
  overflow: hidden;
  width: 260px;
  display: flex;
  flex-direction: column;
}
.ops-drawer.collapsed { width: 40px; }

.drawer-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  cursor: pointer;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border-subtle);
  transition: color var(--duration-fast) var(--ease-out);
}
.drawer-toggle:hover { color: var(--color-primary-500); }

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
}

/* 自定义滚动条 (与深色 sidebar 不同，这里是浅色背景) */
.drawer-body::-webkit-scrollbar { width: 4px; }
.drawer-body::-webkit-scrollbar-track { background: transparent; }
.drawer-body::-webkit-scrollbar-thumb { background: var(--color-neutral-300); border-radius: var(--radius-full); }

.drawer-section { margin-bottom: var(--space-4); }

.collapse-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.drawer-section-title {
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.drawer-actions {
  display: flex;
  gap: var(--space-1);
}

.drawer-select { width: 100%; }
.drawer-btn-full { width: 100%; }

.drawer-result {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--color-neutral-50);
  border-radius: var(--radius-sm);
}

.port-list { display: flex; flex-direction: column; gap: 2px; }
.port-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 2px 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}
.port-code {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--color-primary-500);
  background: var(--color-primary-50);
  padding: 0 var(--space-1);
  border-radius: var(--radius-xs);
}
.port-process {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-hint { font-size: var(--text-xs); color: var(--color-text-muted); }
.module-tags { display: flex; flex-wrap: wrap; gap: var(--space-1); }

/* ============================== */
/* 主内容区                        */
/* ============================== */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}

.l5-pipeline-strip {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.l5-pipeline-step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border, var(--color-border-default));
  background: var(--glass-surface, #fff);
  cursor: pointer;
  font-size: var(--text-xs);
}

.l5-step-badge {
  font-weight: 800;
  color: var(--page-accent, var(--color-primary-600));
}

.l5-step-label {
  color: var(--color-text-secondary);
}

.section-head {
  margin-bottom: var(--space-3);
}

.section-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
}

.section-hint {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-top: 4px;
}

.l5-cross-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.evolution-list {
  margin: 0;
  padding-left: 1.2em;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.55;
}

.evolution-list li + li {
  margin-top: var(--space-2);
}

@media (max-width: 960px) {
  .l5-cross-row { grid-template-columns: 1fr; }
}

/* 主内容滚动条 */
.main-content::-webkit-scrollbar { width: 6px; }
.main-content::-webkit-scrollbar-track { background: transparent; }
.main-content::-webkit-scrollbar-thumb { background: var(--color-neutral-300); border-radius: var(--radius-full); }
.main-content::-webkit-scrollbar-thumb:hover { background: var(--color-neutral-400); }

/* ============================== */
/* Section 间距系统                 */
/* ============================== */
.metrics-section { margin-bottom: var(--space-6); }
.charts-row { margin-bottom: var(--space-6); }
.alert-section { margin-bottom: var(--space-5); }
.test-section { margin-bottom: var(--space-6); }
.alerts-section { margin-bottom: var(--space-8); }

/* ============================== */
/* 指标卡片网格                     */
/* ============================== */
.metric-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.metric-card {
  border: 1px solid var(--border-glass-outer);
  border-radius: var(--radius-lg);
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  cursor: default;
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out),
    border-color var(--duration-normal) var(--ease-out);
  animation: slide-up var(--duration-normal) var(--ease-out) both;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-200);
}

/* 指标卡 — 白底 + 语义色轻 tint（与 el-tag / 图表色一致） */
.metric-cpu {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(239, 246, 255, 0.92) 100%) !important;
  border-color: rgba(59, 130, 246, 0.22) !important;
}
.metric-memory {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(236, 253, 245, 0.92) 100%) !important;
  border-color: rgba(16, 185, 129, 0.22) !important;
}
.metric-disk {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 251, 235, 0.92) 100%) !important;
  border-color: rgba(245, 158, 11, 0.22) !important;
}
.metric-process {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(245, 243, 255, 0.92) 100%) !important;
  border-color: rgba(139, 92, 246, 0.22) !important;
}
.metric-load {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 247, 237, 0.92) 100%) !important;
  border-color: rgba(249, 115, 22, 0.22) !important;
}
.metric-uptime {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(236, 254, 255, 0.92) 100%) !important;
  border-color: rgba(6, 182, 212, 0.22) !important;
}

/* 顶部色条 — 使用 token 颜色变量 */
.metric-accent {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  transition: opacity var(--duration-fast) var(--ease-out);
  opacity: 0.75;
}
.metric-card:hover .metric-accent { opacity: 1; }

/* 各指标卡专属色条 */
.metric-cpu .metric-accent    { background: var(--color-metric-cpu); }
.metric-memory .metric-accent { background: var(--color-metric-memory); }
.metric-disk .metric-accent   { background: var(--color-metric-disk); }
.metric-process .metric-accent{ background: var(--color-metric-process); }
.metric-load .metric-accent   { background: var(--color-metric-load); }
.metric-uptime .metric-accent { background: var(--color-metric-uptime); }

/* 指标卡内部排版 */
.metric-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-5) var(--space-4);
  gap: 2px;
}

.metric-value {
  font-size: var(--text-metric);
  font-weight: var(--weight-bold);
  font-variant-numeric: tabular-nums;
  line-height: var(--leading-tight);
  transition: color var(--duration-fast) var(--ease-out);
}

.metric-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  margin-top: var(--space-1);
}

.metric-sub {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

/* ============================== */
/* 统一面板卡片                     */
/* ============================== */
.panel-card {
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-subtle);
  background: var(--gradient-panel-header);
  min-height: 48px;
  position: relative;
  z-index: 1;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.panel-body { padding: var(--space-5); position: relative; z-index: 1; }

/* ============================== */
/* 图表面板                        */
/* ============================== */
.chart-panel,
.eval-panel-card {
  flex: 1;
  min-width: 360px;
  overflow: auto;
}

.chart-container { height: 35vh; min-height: 280px; max-height: 500px; }

.chart-footer {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-top: var(--space-2);
  line-height: var(--leading-normal);
}

/* ============================== */
/* 评估面板                        */
/* ============================== */
.eval-content {
  text-align: center;
  animation: fade-in var(--duration-slow) var(--ease-out);
}

.eval-grade {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  font-size: var(--text-xl);
  font-weight: var(--weight-extrabold);
  color: var(--color-text-inverse);
  margin-bottom: var(--space-2);
  animation: scale-in var(--duration-normal) var(--ease-spring);
}

.grade-A { background: var(--gradient-success); }
.grade-B { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
.grade-C { background: var(--gradient-warning); }
.grade-D { background: linear-gradient(135deg, #f97316, #fb923c); }
.grade-F { background: var(--gradient-danger); }

.eval-composite {
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.eval-meta {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
}

.eval-dims {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: var(--space-3);
}

.eval-dim {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.eval-dim-name {
  font-size: var(--text-2xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.eval-dim-bar { width: 52px; }
.eval-dim-val { font-size: var(--text-2xs); color: var(--color-text-muted); }

.eval-stats {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  flex-wrap: wrap;
}

/* Mini 趋势图 */
.trend-mini {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  justify-content: center;
  height: 32px;
  margin-top: var(--space-3);
}

.trend-bar {
  width: 12px;
  border-radius: 2px;
  opacity: 0.82;
  transition: height 0.3s var(--ease-out);
  min-height: 4px;
}

.trend-A { background: var(--color-success); }
.trend-B { background: var(--color-primary-500); }
.trend-C { background: var(--color-warning); }
.trend-D,.trend-F { background: var(--color-danger); }

.trend-hint {
  display: block;
  font-size: var(--text-2xs);
  color: var(--color-text-muted);
  margin-top: var(--space-2);
}

/* ============================== */
/* 压测 Alert                      */
/* ============================== */
.stress-alert {
  white-space: pre-line;
  font-size: var(--text-base);
}

/* ============================== */
/* 测试面板                        */
/* ============================== */
.test-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.test-case {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--color-neutral-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-subtle);
  font-size: var(--text-xs);
}

.test-name {
  font-weight: var(--weight-semibold);
  min-width: 72px;
  white-space: nowrap;
}

.test-desc {
  color: var(--color-text-muted);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-pending { color: var(--color-neutral-300); }

.test-actions {
  text-align: center;
  margin-top: var(--space-3);
}

/* ============================== */
/* 告警面板                        */
/* ============================== */
.alerts-panel { min-height: 120px; }
.alerts-table { --el-table-border-color: var(--color-border-subtle); }

/* ============================== */
/* 响应式                          */
/* ============================== */
@media (max-width: 1024px) {
  .charts-row {
    flex-direction: column;
  }
  .chart-panel,
  .eval-panel-card {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .metric-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .ops-drawer { width: 220px; }
  .main-content { padding: var(--space-4); }
}

@media (max-width: 600px) {
  .metric-cards {
    grid-template-columns: 1fr;
  }
  .dashboard-root {
    flex-direction: column;
  }
  .ops-drawer {
    width: 100%;
    height: auto;
    max-height: 40vh;
    border-right: none;
    border-bottom: 1px solid var(--color-border-default);
  }
  .ops-drawer.collapsed { height: 40px; }
}
</style>
