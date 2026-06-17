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
  axisLabel: { color: '#475569', fontSize: 11 },
  splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
}

export function chartGrid(extra = {}) {
  return { top: 8, bottom: 24, left: 40, right: 12, ...extra }
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
    textStyle: { color: '#334155', fontSize: 12 },
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

export function l5ValueAxis(name, extra = {}) {
  return valueAxis({ name, nameTextStyle: { color: '#64748b', fontSize: 11 }, ...extra })
}
