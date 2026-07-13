/** ECharts 按需加载 — 避免首屏拉取 1MB+ 包 */
let lib = null

export async function getEcharts() {
  if (!lib) lib = await import('echarts')
  return lib
}

/** 容器从隐藏/动画变为可见后需多次 resize 才能正确绘制 */
export function scheduleChartResize(chart) {
  if (!chart || chart.isDisposed?.()) return
  const run = () => {
    try { chart.resize() } catch { /* disposed */ }
  }
  requestAnimationFrame(run)
  setTimeout(run, 120)
  setTimeout(run, 400)
}

export async function initChart(el) {
  if (!el) return null
  const echarts = await getEcharts()
  const chart = echarts.init(el)
  scheduleChartResize(chart)
  return chart
}
