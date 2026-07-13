<template>
  <aside class="trace-memo-dock" :class="{ 'trace-memo-dock--drawer': drawer }">
    <header class="trace-memo-head">
      <div>
        <strong>Trace 阶段图</strong>
        <code class="trace-id">{{ traceId.slice(0, 16) }}</code>
        <span v-if="stageTotal > previewRows.length" class="trace-hint">Top {{ previewRows.length }} / {{ stageTotal }}</span>
      </div>
      <div class="trace-memo-actions">
        <el-button link type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        <el-button link type="primary" size="small" @click="$emit('open-full')">展开 L4</el-button>
        <el-button link size="small" @click="$emit('close')">关闭</el-button>
      </div>
    </header>
    <div class="trace-memo-chart-wrap" :style="{ height: chartHeight + 'px' }">
      <div ref="chartRef" class="trace-memo-chart"></div>
      <div v-if="loading" class="trace-memo-chart-loading">加载中…</div>
      <p v-else-if="chartEmpty" class="trace-memo-chart-empty">暂无阶段耗时，完成一次 L1 分析后刷新</p>
    </div>
    <pre class="trace-memo-text">{{ memoText }}</pre>
  </aside>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { fetchTraceMemo } from '../../api/trace'
import { initChart, getEcharts, scheduleChartResize } from '../../composables/useEcharts'
import { chartTooltip, categoryAxis, valueAxis } from '../../utils/chartTheme'

const props = defineProps({
  traceId: { type: String, required: true },
  drawer: { type: Boolean, default: false },
})
defineEmits(['close', 'open-full'])

const PREVIEW_MAX = 10
const loading = ref(false)
const memoText = ref('加载中…')
const chartEmpty = ref(false)
const stageTotal = ref(0)
const previewRows = ref([])
const chartRef = ref(null)
let chartInst = null
let resizeObs = null

const chartHeight = computed(() => {
  const n = previewRows.value.length || 1
  const rowH = props.drawer ? 22 : 20
  const base = 28
  const max = props.drawer ? 360 : 260
  return Math.min(max, Math.max(140, n * rowH + base))
})

function disposeChart() {
  if (chartInst) {
    try { chartInst.dispose() } catch {}
    chartInst = null
  }
}

function bindResize() {
  if (resizeObs || !chartRef.value || typeof ResizeObserver === 'undefined') return
  resizeObs = new ResizeObserver(() => {
    if (chartInst && !chartInst.isDisposed?.()) scheduleChartResize(chartInst)
  })
  resizeObs.observe(chartRef.value)
}

function unbindResize() {
  if (resizeObs) {
    resizeObs.disconnect()
    resizeObs = null
  }
}

function pickPreviewRows(rows) {
  const sorted = [...rows].sort((a, b) => (b.duration_ms || 0) - (a.duration_ms || 0))
  return sorted.slice(0, PREVIEW_MAX).reverse()
}

async function load() {
  if (!props.traceId) return
  loading.value = true
  chartEmpty.value = false
  try {
    const data = await fetchTraceMemo(props.traceId)
    memoText.value = data.memo || '暂无纪要'
    const rows = data.chart || []
    stageTotal.value = rows.length
    previewRows.value = pickPreviewRows(rows)
    chartEmpty.value = !rows.length
    await nextTick()
    setTimeout(() => paintChart(previewRows.value), 100)
  } catch (e) {
    const detail = e.response?.data?.detail
    memoText.value = `加载失败: ${detail || e.message || e}`
    chartEmpty.value = true
    previewRows.value = []
    disposeChart()
  } finally {
    loading.value = false
  }
}

async function paintChart(rows) {
  if (!chartRef.value) return
  if (!rows.length) {
    disposeChart()
    return
  }
  await getEcharts()
  disposeChart()
  chartInst = await initChart(chartRef.value)
  if (!chartInst) return
  const labels = rows.map(r => String(r.label || '').slice(0, 14))
  const values = rows.map(r => r.duration_ms || 0)
  chartInst.setOption({
    tooltip: chartTooltip(),
    grid: { left: 4, right: 16, top: 8, bottom: 8, containLabel: true },
    xAxis: valueAxis({ name: 'ms', splitNumber: 3 }),
    yAxis: categoryAxis(labels, {
      inverse: true,
      axisLabel: { fontSize: 9, width: 88, overflow: 'truncate', margin: 4 },
    }),
    series: [{
      type: 'bar',
      data: values,
      itemStyle: { color: '#38bdf8', borderRadius: [0, 4, 4, 0] },
      barMaxWidth: 14,
    }],
  }, true)
  scheduleChartResize(chartInst)
  bindResize()
}

watch(() => props.traceId, () => {
  disposeChart()
  load()
})

watch(chartHeight, () => {
  nextTick(() => {
    setTimeout(() => {
      if (chartInst && previewRows.value.length) scheduleChartResize(chartInst)
    }, 80)
  })
})

onMounted(load)
onUnmounted(() => {
  unbindResize()
  disposeChart()
})
</script>

<style scoped>
.trace-memo-dock {
  width: 336px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  align-self: stretch;
  border-left: 1px solid var(--color-border-default);
  background: #f8fafc;
  overflow: hidden;
}
.trace-memo-dock--drawer { width: 100%; border-left: none; }
.trace-memo-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-default);
  background: #fff;
  flex-shrink: 0;
}
.trace-memo-head strong { display: block; font-size: 12px; }
.trace-id { font-size: 10px; color: #0369a1; }
.trace-hint { display: block; font-size: 10px; color: #94a3b8; margin-top: 2px; }
.trace-memo-actions { display: flex; flex-wrap: wrap; gap: 2px; justify-content: flex-end; flex-shrink: 0; }
.trace-memo-chart-wrap {
  position: relative;
  flex-shrink: 0;
  margin: 8px 8px 4px;
  min-height: 140px;
}
.trace-memo-chart {
  width: 100%;
  height: 100%;
  background: #fff;
  border: 1px solid var(--color-border-default);
  border-radius: 8px;
  overflow: hidden;
}
.trace-memo-chart-loading,
.trace-memo-chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 12px;
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
}
.trace-memo-text {
  flex: 1;
  min-height: 80px;
  max-height: 42%;
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  background: #fff;
  border-top: 1px solid var(--color-border-default);
}
</style>