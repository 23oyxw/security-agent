/** ECharts 按需加载 — 避免首屏拉取 1MB+ 包 */
let lib = null

export async function getEcharts() {
  if (!lib) lib = await import('echarts')
  return lib
}

export async function initChart(el) {
  if (!el) return null
  const echarts = await getEcharts()
  return echarts.init(el)
}
