/**
 * ECharts 主题 — 与 design tokens 对齐
 * 图表始终绘制在白底 panel 上，颜色用语义/指标色，不随页面背景染色
 */

export const METRIC_COLORS = {
  cpu: '#3b82f6',
  memory: '#10b981',
  disk: '#f59e0b',
  process: '#8b5cf6',
  load: '#f97316',
  uptime: '#06b6d4',
}

export const CHART_PALETTE = [
  METRIC_COLORS.cpu,
  METRIC_COLORS.memory,
  METRIC_COLORS.disk,
  METRIC_COLORS.process,
  METRIC_COLORS.load,
  METRIC_COLORS.uptime,
]

const AXIS = {
  axisLine: { lineStyle: { color: '#cbd5e1' } },
  axisLabel: { color: '#475569', fontSize: 13 },
  splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
}

export function chartGrid(extra = {}) {
  return { top: 8, bottom: 28, left: 48, right: 16, ...extra }
}

export function categoryAxis(data, extra = {}) {
  return { type: 'category', data, ...AXIS, ...extra }
}

export function valueAxis(extra = {}) {
  return { type: 'value', ...AXIS, ...extra }
}

export function chartTooltip(extra = {}) {
  return {
    trigger: 'axis',
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
    borderColor: '#e2e8f0',
    textStyle: { color: '#334155', fontSize: 14 },
    ...extra,
  }
}

/** 读取当前页面主题图表主色（Trace 等页随路由变化） */
export function getPageChartColors() {
  if (typeof document === 'undefined') {
    return { primary: METRIC_COLORS.cpu, secondary: METRIC_COLORS.uptime }
  }
  const s = getComputedStyle(document.documentElement)
  return {
    primary: s.getPropertyValue('--page-chart-primary').trim() || METRIC_COLORS.cpu,
    secondary: s.getPropertyValue('--page-chart-secondary').trim() || METRIC_COLORS.uptime,
  }
}

export function pageChartGradient(echarts, direction = 'vertical') {
  const { primary, secondary } = getPageChartColors()
  const isV = direction === 'vertical'
  return new echarts.graphic.LinearGradient(0, 0, isV ? 0 : 1, isV ? 1 : 0, [
    { offset: 0, color: primary },
    { offset: 1, color: secondary },
  ])
}

export function metricBarData(values) {
  const keys = ['cpu', 'memory', 'disk']
  return values.map((value, i) => ({
    value,
    itemStyle: {
      color: METRIC_COLORS[keys[i]] || CHART_PALETTE[i],
      borderRadius: [4, 4, 0, 0],
    },
  }))
}

/** L5 散点/热力 — 与 ops 主题白底图表一致 */
export const L5_CHART = {
  normal: METRIC_COLORS.cpu,
  anomaly: METRIC_COLORS.load,
  heatRange: ['#f0f9ff', '#0ea5e9', '#f59e0b', '#ef4444'],
}

/** 三层防御层色 — 与 three-layer-defense.js 一致 */
export const DEFENSE_LAYER_COLORS = {
  static_risk: '#3b82f6',
  dynamic_intent: '#10b981',
  restricted_exec: '#f59e0b',
}

export function l5ValueAxis(name, extra = {}) {
  return valueAxis({ name, nameTextStyle: { color: '#64748b', fontSize: 11 }, ...extra })
}

/** 雷达图 — L5 六维 / Trace 多维 */
export function buildRadarChartOption({ indicators, values, name = '得分', color = '#0ea5e9' }) {
  return {
    tooltip: chartTooltip(),
    radar: {
      indicator: indicators,
      radius: '62%',
      axisName: { color: '#475569', fontSize: 11 },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: { areaStyle: { color: ['rgba(241,245,249,0.8)', 'rgba(248,250,252,0.5)'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name,
        areaStyle: { color: `${color}33` },
        lineStyle: { color, width: 2 },
        itemStyle: { color },
      }],
    }],
  }
}

/** 三层防御得分条 — 水平柱 */
export function buildDefenseLayersChartOption(layers = []) {
  const names = layers.map(l => l.name || l.short || l.id)
  const scores = layers.map(l => l.score ?? 0)
  const colors = layers.map(l => DEFENSE_LAYER_COLORS[l.id] || '#94a3b8')
  return {
    tooltip: chartTooltip({ trigger: 'axis', axisPointer: { type: 'shadow' } }),
    grid: chartGrid({ left: 120, right: 24, top: 8, bottom: 24 }),
    xAxis: valueAxis({ max: 100, name: '分' }),
    yAxis: categoryAxis(names, { inverse: true }),
    series: [{
      type: 'bar',
      data: scores.map((v, i) => ({
        value: v,
        itemStyle: { color: colors[i], borderRadius: [0, 4, 4, 0] },
      })),
      label: { show: true, position: 'right', formatter: '{c}', fontSize: 11, color: '#475569' },
    }],
  }
}

/** L5 散点 — 3σ/IQR 离群 */
export function buildL5ScatterOption({ normal = [], anomaly = [], latencyRange = null }) {
  const lo = latencyRange?.[0] ?? 0
  const hi = latencyRange?.[1] ?? 0
  const useLog = hi > 0 && lo > 0 && hi / lo > 20
  return {
    tooltip: {
      ...chartTooltip({ trigger: 'item' }),
      formatter(p) {
        const d = p.data
        const lat = d[6] ?? d[0]
        const err = d[5] ?? '—'
        const risk = d[7] ?? d[1]
        const label = d[4] || '—'
        return [
          `<b>${label}</b>`,
          `Trace ${String(d[3]).slice(0, 18)}`,
          `耗时 ${lat} ms`,
          `综合风险 ${risk}`,
          `阶段异常 ${err}%`,
        ].join('<br/>')
      },
    },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: '#64748b' } },
    grid: chartGrid({ left: 56, right: 20, top: 36, bottom: 52 }),
    xAxis: {
      ...l5ValueAxis('耗时(ms)'),
      ...(useLog ? { type: 'log', logBase: 10, min: Math.max(80, lo * 0.7) } : { min: 0 }),
    },
    yAxis: l5ValueAxis('综合风险分', { min: 0, max: 100, splitNumber: 5 }),
    series: [
      {
        name: '正常',
        type: 'scatter',
        symbolSize: 9,
        itemStyle: { color: L5_CHART.normal, opacity: 0.78 },
        data: normal,
      },
      {
        name: '离群/异常',
        type: 'scatter',
        symbolSize: 11,
        itemStyle: { color: L5_CHART.anomaly, borderColor: '#fecaca', borderWidth: 1 },
        data: anomaly,
      },
    ],
  }
}

/** L5 热力 — 时段 × 意图故障密度 */
export function buildL5HeatmapOption({ xLabels = [], yLabels = [], matrix = [], heatRange = L5_CHART.heatRange }) {
  const data = []
  matrix.forEach((row, yi) => {
    row.forEach((val, xi) => data.push([xi, yi, val ?? 0]))
  })
  const vals = data.map(d => d[2])
  const maxVal = Math.max(...vals, 1)
  const hasSignal = vals.some(v => v > 0)
  return {
    tooltip: {
      position: 'top',
      textStyle: { fontSize: 12 },
      formatter(p) {
        const xi = p.value[0]
        const yi = p.value[1]
        const x = xLabels[xi] ?? xi
        const y = yLabels[yi] ?? yi
        const v = p.value[2]
        if (!v) return `${y}<br/>${x}时 · 无任务`
        return `${y}<br/>${x}时<br/>风险热度 <b>${v}</b>`
      },
    },
    grid: { left: 92, right: 56, top: 24, bottom: 40 },
    xAxis: {
      ...categoryAxis(xLabels.map(l => `${l}时`), { splitArea: { show: true } }),
      axisLabel: { fontSize: 10, interval: 0 },
      name: '时段',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { fontSize: 10, color: '#64748b' },
    },
    yAxis: {
      ...categoryAxis(yLabels, { splitArea: { show: true } }),
      axisLabel: { fontSize: 10, width: 76, overflow: 'truncate' },
      name: '意图',
      nameTextStyle: { fontSize: 10, color: '#64748b' },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'vertical',
      right: 8,
      top: 'middle',
      itemHeight: 100,
      itemWidth: 12,
      text: ['高', '低'],
      textStyle: { fontSize: 10, color: '#64748b' },
      inRange: { color: heatRange },
      show: hasSignal,
    },
    series: [{
      type: 'heatmap',
      data,
      label: {
        show: true,
        fontSize: 9,
        color: '#334155',
        formatter: p => (p.value[2] > 0 ? Math.round(p.value[2]) : ''),
      },
      itemStyle: {
        borderColor: '#e2e8f0',
        borderWidth: 1,
      },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.25)' } },
    }],
  }
}

/** Trace 瀑布 — 横向柱（多阶段可读） */
export function buildWaterfallBarOption(spans = []) {
  const horizontal = spans.length > 5
  const labels = spans.map(s => s.label || s.title || s.name)
  const barData = spans.map(s => ({
    value: s.duration_ms,
    itemStyle: {
      color: s.error || s.is_error ? METRIC_COLORS.load : (s.is_slowest ? METRIC_COLORS.disk : METRIC_COLORS.uptime),
      borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
    },
  }))
  if (horizontal) {
    return {
      tooltip: {
        ...chartTooltip(),
        formatter(p) {
          const sp = spans[p.dataIndex]
          if (!sp) return ''
          return `${sp.layer} · ${sp.title}<br/>${sp.duration_ms} ms${sp.tool ? `<br/>${sp.tool}` : ''}`
        },
      },
      grid: chartGrid({ left: 120, right: 24, top: 12, bottom: 24 }),
      xAxis: valueAxis({ name: 'ms', nameTextStyle: { color: '#64748b', fontSize: 11 } }),
      yAxis: categoryAxis(labels, { inverse: true, axisLabel: { fontSize: 10, width: 108, overflow: 'truncate' } }),
      series: [{ type: 'bar', data: barData, barMaxWidth: 22 }],
    }
  }
  return {
    tooltip: {
      ...chartTooltip(),
      formatter(p) {
        const sp = spans[p.dataIndex]
        if (!sp) return ''
        return `${sp.layer} · ${sp.title}<br/>${sp.duration_ms} ms${sp.tool ? `<br/>${sp.tool}` : ''}`
      },
    },
    grid: chartGrid({ left: 48, right: 16, top: 24, bottom: 72 }),
    xAxis: categoryAxis(labels, { axisLabel: { rotate: 28, fontSize: 9, interval: 0 } }),
    yAxis: valueAxis({ name: 'ms', nameTextStyle: { color: '#64748b', fontSize: 11 } }),
    series: [{ type: 'bar', data: barData, barMaxWidth: 36 }],
  }
}

/** 直方图 — 耗时/风险分布 */
export function buildHistogramOption({ title = '', binLabels = [], counts = [], color = METRIC_COLORS.cpu }) {
  return {
    title: title ? { text: title, left: 0, textStyle: { fontSize: 12, color: '#475569', fontWeight: 600 } } : undefined,
    tooltip: chartTooltip(),
    grid: chartGrid({ left: 48, right: 16, top: title ? 36 : 16, bottom: 48 }),
    xAxis: categoryAxis(binLabels, { axisLabel: { rotate: 32, fontSize: 9, interval: 0 } }),
    yAxis: valueAxis({ name: '样本数', nameTextStyle: { color: '#64748b', fontSize: 10 } }),
    series: [{
      type: 'bar',
      data: counts.map(v => ({ value: v, itemStyle: { color, borderRadius: [4, 4, 0, 0] } })),
      barMaxWidth: 28,
    }],
  }
}

/** 箱线图 — Tukey Q1/Q3/IQR */
export function buildBoxPlotOption({ name = '耗时(ms)', box = {}, color = METRIC_COLORS.uptime }) {
  const vals = [box.min ?? 0, box.q1 ?? 0, box.median ?? 0, box.q3 ?? 0, box.max ?? 0]
  return {
    tooltip: {
      trigger: 'item',
      formatter() {
        return [
          `<b>${name}</b>`,
          `n=${box.n ?? 0}`,
          `min ${box.min} · Q1 ${box.q1}`,
          `中位 ${box.median} · Q3 ${box.q3}`,
          `max ${box.max} · 均值 ${box.mean} · σ ${box.std}`,
        ].join('<br/>')
      },
    },
    grid: chartGrid({ left: 56, right: 24, top: 16, bottom: 32 }),
    xAxis: categoryAxis([name]),
    yAxis: valueAxis({ name: 'ms', nameTextStyle: { color: '#64748b', fontSize: 10 } }),
    series: [{
      type: 'boxplot',
      data: [vals],
      itemStyle: { color, borderColor: color },
    }],
  }
}

/** 评估趋势折线 */
export function buildEvalTrendOption(points = []) {
  const xs = points.map((p, i) => p.n ?? i + 1)
  const ys = points.map(p => p.score ?? 0)
  return {
    tooltip: chartTooltip(),
    grid: chartGrid({ left: 48, right: 16, top: 16, bottom: 32 }),
    xAxis: categoryAxis(xs.map(String), { name: '窗口序', nameGap: 24 }),
    yAxis: valueAxis({ min: 0, max: 100, name: '分' }),
    series: [{
      type: 'line',
      smooth: true,
      data: ys,
      symbolSize: 6,
      lineStyle: { color: METRIC_COLORS.cpu, width: 2 },
      areaStyle: { color: 'rgba(59,130,246,0.12)' },
    }],
  }
}
