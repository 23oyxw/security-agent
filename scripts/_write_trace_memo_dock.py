# -*- coding: utf-8 -*-
from pathlib import Path

CONTENT = r"""<template>
  <aside class="trace-memo-dock">
    <header class="trace-memo-head">
      <div>
        <strong>Trace</strong>
        <code class="trace-id">{{ traceId.slice(0, 16) }}</code>
      </div>
      <div class="trace-memo-actions">
        <el-button link type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        <el-button link type="primary" size="small" @click="$emit('open-full')">展开</el-button>
        <el-button link size="small" @click="$emit('close')">关闭</el-button>
      </div>
    </header>
    <div ref="chartRef" class="trace-memo-chart" v-loading="loading"></div>
    <pre class="trace-memo-text">{{ memoText }}</pre>
  </aside>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { fetchTraceMemo } from '../../api/trace'
import { initChart, getEcharts } from '../../composables/useEcharts'
import { chartTooltip, categoryAxis, valueAxis } from '../../utils/chartTheme'

const props = defineProps({ traceId: { type: String, required: true } })
defineEmits(['close', 'open-full'])

const loading = ref(false)
const memoText = ref('加载中…')
const chartRef = ref(null)
let chartInst = null

async function load() {
  if (!props.traceId) return
  loading.value = true
  try {
    const data = await fetchTraceMemo(props.traceId)
    memoText.value = data.memo || '暂无纪要'
    await nextTick()
    await paintChart(data.chart || [])
  } catch (e) {
    memoText.value = `加载失败: ${e.message || e}`
  } finally {
    loading.value = false
  }
}

async function paintChart(rows) {
  if (!chartRef.value || !rows.length) return
  await getEcharts()
  if (!chartInst) chartInst = await initChart(chartRef.value)
  if (!chartInst) return
  chartInst.setOption({
    tooltip: chartTooltip(),
    grid: { left: 8, right: 8, top: 20, bottom: 4, containLabel: true },
    xAxis: categoryAxis(rows.map(r => r.label || ''), { axisLabel: { show: false } }),
    yAxis: valueAxis({ name: 'ms' }),
    series: [{ type: 'bar', data: rows.map(r => r.duration_ms || 0), itemStyle: { color: '#38bdf8' } }],
  }, true)
}

watch(() => props.traceId, load, { immediate: true })
onMounted(load)
onUnmounted(() => { if (chartInst) { try { chartInst.dispose() } catch {} chartInst = null } })
</script>

<style scoped>
.trace-memo-dock { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; min-height: 0; border-left: 1px solid var(--color-border-default); background: #f8fafc; }
.trace-memo-head { display: flex; justify-content: space-between; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--color-border-default); background: #fff; }
.trace-memo-head strong { display: block; font-size: 12px; }
.trace-id { font-size: 10px; color: #0369a1; }
.trace-memo-actions { display: flex; flex-wrap: wrap; gap: 2px; }
.trace-memo-chart { height: 150px; margin: 8px; background: #fff; border: 1px solid var(--color-border-default); border-radius: 8px; }
.trace-memo-text { flex: 1; min-height: 0; margin: 0; padding: 10px 12px; overflow: auto; font-size: 11px; line-height: 1.5; white-space: pre-wrap; background: #fff; border-top: 1px solid var(--color-border-default); }
</style>
"""

Path(r"C:\Users\oyxw\security-agent\frontend\src\components\agent\TraceMemoDock.vue").write_text(
    CONTENT, encoding="utf-8"
)
print("ok")
