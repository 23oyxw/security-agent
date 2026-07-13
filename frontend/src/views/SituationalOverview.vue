<template>
  <div class="situation-view">
    <PageHeader
      title="态势总览"
      subtitle="L1 静态环境感知（眼）· 8 维只读仪表盘 · Static Eye Dashboard"
      layer="L1"
      layer-label="静态感知"
      agent="core_dispatch · analyze"
    >
      <template #actions>
        <el-tag size="small" type="info" effect="plain">{{ STATIC_EYE_CONSTRAINT }}</el-tag>
        <el-button size="small" type="primary" @click="$router.push('/agent')">L1 三感知分析</el-button>
        <el-button size="small" @click="$router.push('/canvas')">架构画布</el-button>
        <el-button size="small" :loading="loading" @click="fetchAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </template>
    </PageHeader>

    <!-- 总览条 -->
    <section class="hero-strip reveal-item">
      <div class="hero-health" :class="eyeCtx.healthOk === false ? 'is-alert' : 'is-ok'">
        <el-icon :size="28"><View /></el-icon>
        <div>
          <span class="hero-label">系统态势 System Posture</span>
          <span class="hero-value">{{ eyeCtx.healthLabel }}</span>
        </div>
      </div>
      <div class="hero-meta">
        <span>进程 Processes: <strong>{{ eyeCtx.processCount ?? '—' }}</strong></span>
        <span>刷新 Refresh: {{ lastRefresh || '—' }}</span>
        <span>指标 Metrics: {{ metricsStore.lastUpdated || '—' }}</span>
        <span>间隔 Interval: {{ pollSec }}s</span>
      </div>
    </section>

    <!-- 8 维轴 -->
    <section class="axis-section reveal-item reveal-delay-1">
      <header class="section-head">
        <h2>静态之眼 · 8 维态势</h2>
        <span class="section-hint">网络 · 端口 · CPU · 内存 · 磁盘 · 链路 · 权限 · 状态</span>
      </header>
      <div class="axis-grid">
        <article
          v-for="(ax, idx) in axisCards"
          :key="ax.id"
          class="axis-card motion-lift"
          :class="{ 'is-alert': ax.alert, [`stagger-${idx + 1}`]: true }"
        >
          <div class="axis-accent" :style="{ background: ax.alert ? 'var(--color-danger)' : 'var(--color-primary-500)' }" />
          <div class="axis-icon"><el-icon :size="18"><component :is="ax.icon" /></el-icon></div>
          <div class="axis-body">
            <span class="axis-cn">{{ ax.cn }}</span>
            <span class="axis-en">{{ ax.en }}</span>
            <span class="axis-value">{{ ax.value }}</span>
            <span class="axis-hint">{{ ax.hint }}</span>
          </div>
        </article>
      </div>
    </section>

    <!-- 图表 + 明细 -->
    <section class="detail-row reveal-item reveal-delay-2">
      <div class="panel-card">
        <header class="panel-header">
          <span class="panel-title"><el-icon :size="16"><DataAnalysis /></el-icon> 资源占用 Resource</span>
          <el-tag size="small" effect="plain">CPU / Memory / Disk</el-tag>
        </header>
        <div ref="resourceChart" class="chart-box" v-loading="loading" />
      </div>

      <div class="panel-card">
        <header class="panel-header">
          <span class="panel-title"><el-icon :size="16"><Monitor /></el-icon> 监听端口 Listening Ports</span>
          <el-tag size="small" effect="plain">Top {{ ports.length }}</el-tag>
        </header>
        <div class="port-table" v-loading="loading">
          <div v-if="!ports.length" class="empty-hint">暂无端口数据 · Mock 或后端 /perception/os/ports</div>
          <div v-for="p in ports.slice(0, 12)" :key="p.port + (p.process || '')" class="port-row">
            <code class="port-num">{{ p.port }}</code>
            <span class="port-proto">{{ p.proto || 'tcp' }}</span>
            <span class="port-proc">{{ p.process || p.program || '—' }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 三感知并列提示 -->
    <section class="triple-hint reveal-item reveal-delay-3">
      <span class="triple-label">L1 并行三感知 Parallel Triple</span>
      <div class="triple-chips">
        <el-tag effect="plain" type="warning">① 边界 Boundary</el-tag>
        <el-tag effect="plain" type="primary">② 知识 Knowledge</el-tag>
        <el-tag effect="plain" type="success">③ 静态 Static Eye ← 本页</el-tag>
      </div>
      <p class="triple-note">
        态势总览是静态之眼的只读入口；完整三感知需在
        <router-link to="/agent">计划模式对话</router-link>
        中触发 L1 analyze。
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { initChart, scheduleChartResize } from '../composables/useEcharts'
import api from '../api'
import { useMetricsStore } from '../stores/metrics'
import PageHeader from '../components/common/PageHeader.vue'
import { chartTooltip, categoryAxis, valueAxis, metricBarData, chartGrid } from '../utils/chartTheme'
import {
  STATIC_EYE_AXES,
  STATIC_EYE_CONSTRAINT,
  buildEyeContext,
} from '../constants/static-perception'

const loading = ref(false)
const lastRefresh = ref('')
const pollSec = ref(10)
const metricsStore = useMetricsStore()
const metrics = ref({})
const snapshot = ref({})
const portCount = ref(null)
const ports = ref([])
const resourceChart = ref(null)
let chartInstance = null
let pollTimer = null

const eyeCtx = computed(() => buildEyeContext(metrics.value, snapshot.value, { portCount: portCount.value }))

const axisCards = computed(() =>
  STATIC_EYE_AXES.map(ax => ({
    ...ax,
    value: ax.format(eyeCtx.value),
    alert: ax.alert(eyeCtx.value),
  })),
)

function syncMetricsFromStore() {
  if (!metricsStore.raw || metricsStore.raw.cpu_percent == null) return
  metrics.value = { ...metricsStore.raw }
  nextTick(renderChart)
}

async function fetchContextAndPorts() {
  loading.value = true
  try {
    const [cRes, pRes] = await Promise.allSettled([
      api.get('/perception/context'),
      api.get('/perception/os/ports'),
    ])
    if (cRes.status === 'fulfilled' && cRes.value) {
      snapshot.value = cRes.value.snapshot || cRes.value.summary || cRes.value
      if (cRes.value.summary && !snapshot.value.summary) {
        snapshot.value = { summary: cRes.value.summary, ...snapshot.value }
      }
    }
    if (pRes.status === 'fulfilled' && pRes.value) {
      const list = pRes.value.ports || pRes.value.listening || pRes.value.items || []
      ports.value = Array.isArray(list) ? list : []
      portCount.value = pRes.value.count ?? ports.value.length
    }
    lastRefresh.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } finally {
    loading.value = false
  }
}

async function fetchAll() {
  await metricsStore.fetchMetrics()
  syncMetricsFromStore()
  await fetchContextAndPorts()
}

async function renderChart() {
  if (!resourceChart.value) return
  if (!chartInstance) chartInstance = await initChart(resourceChart.value)
  const ctx = eyeCtx.value
  chartInstance.setOption({
    tooltip: chartTooltip(),
    grid: chartGrid(),
    xAxis: categoryAxis(['CPU', 'Memory', 'Disk']),
    yAxis: valueAxis({ max: 100, axisLabel: { formatter: '{value}%', color: '#475569', fontSize: 11 } }),
    series: [{
      type: 'bar',
      barWidth: 48,
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11, color: '#334155' },
      data: metricBarData([
        Number(ctx.cpu) || 0,
        Number(ctx.memory) || 0,
        Number(ctx.disk) || 0,
      ]),
    }],
  }, true)
  scheduleChartResize(chartInstance)
}

const resizeHandler = () => chartInstance?.resize()

watch(
  () => [metricsStore.cpuPercent, metricsStore.memoryPercent, metricsStore.diskPercent],
  () => syncMetricsFromStore(),
)

onMounted(() => {
  fetchAll()
  pollTimer = setInterval(fetchAll, pollSec.value * 1000)
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  clearInterval(pollTimer)
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.situation-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-5) var(--space-8);
}

.hero-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-5);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-default);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(16, 185, 129, 0.06));
}

.hero-health {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.hero-health.is-ok { color: var(--color-success); }
.hero-health.is-alert { color: var(--color-danger); }

.hero-label {
  display: block;
  font-size: 10px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.hero-value {
  font-size: var(--text-xl);
  font-weight: 700;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.section-head {
  margin-bottom: var(--space-3);
}

.section-head h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
}

.section-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.axis-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

@media (max-width: 960px) {
  .axis-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 520px) {
  .axis-grid { grid-template-columns: 1fr; }
}

.axis-card {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-default);
  background: var(--color-surface, #fff);
  overflow: hidden;
}

.axis-card.is-alert {
  border-color: var(--color-danger);
  background: var(--color-danger-bg, #fef2f2);
}

.axis-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
}

.axis-icon {
  color: var(--color-primary-500);
  margin-top: 2px;
}

.axis-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.axis-cn {
  font-size: var(--text-sm);
  font-weight: 700;
}

.axis-en {
  font-size: 9px;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.axis-value {
  font-size: var(--text-lg);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  margin-top: 4px;
}

.axis-hint {
  font-size: 10px;
  color: var(--color-text-muted);
}

.detail-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

@media (max-width: 768px) {
  .detail-row { grid-template-columns: 1fr; }
}

.panel-card {
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  background: var(--color-surface, #fff);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  font-weight: 600;
}

.chart-box {
  height: 220px;
  padding: var(--space-2);
}

.port-table {
  padding: var(--space-3) var(--space-4);
  max-height: 220px;
  overflow-y: auto;
}

.port-row {
  display: grid;
  grid-template-columns: 56px 48px 1fr;
  gap: var(--space-2);
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-subtle);
  font-size: var(--text-xs);
}

.port-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-primary-600);
}

.port-proto {
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.port-proc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.empty-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  padding: var(--space-4) 0;
}

.triple-hint {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-primary-200);
  background: var(--color-primary-50, #eff6ff);
}

.triple-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-primary-600);
  margin-bottom: var(--space-2);
}

.triple-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.triple-note {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
