import api from './index'

export function fetchL5Scatter() {
  return api.get('/l5/scatter')
}

export function fetchL5Heatmap() {
  return api.get('/l5/heatmap')
}

export function fetchL5Distributions() {
  return api.get('/l5/distributions')
}

export function fetchL5LayerCross() {
  return api.get('/l5/layer-cross')
}

export function fetchL5RootCause(traceId) {
  return api.get(`/l5/root-cause/${encodeURIComponent(traceId)}`)
}

export function fetchL5IntegrationCatalog() {
  return api.get('/l5/integration/catalog')
}

export function runL5Integration(testIds = null) {
  return api.post('/l5/integration/run', { test_ids: testIds })
}

export function fetchL5MathCatalog() {
  return api.get('/l5/math-catalog')
}

export function fetchL5Clusters() {
  return api.get('/l5/clusters')
}

export function fetchL5ExternalCatalog() {
  return api.get('/l5/integration/external/catalog')
}

export function runL5External(scenarioIds = null) {
  return api.post('/l5/integration/external/run', { scenario_ids: scenarioIds })
}

export function fetchL5PolicyFeedback() {
  return api.get('/l5/policy-feedback')
}

export function applyL5PolicyFeedback() {
  return api.post('/l5/policy-feedback/apply')
}

export function fetchAggregatedAlerts(windowMinutes = 5) {
  return api.get('/alerts/aggregated', { params: { window_minutes: windowMinutes } })
}

export function fetchL5Sync() {
  return api.get('/l5/sync')
}

