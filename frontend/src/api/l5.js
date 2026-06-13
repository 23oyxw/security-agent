import api from './index'

export function fetchL5Scatter() {
  return api.get('/l5/scatter')
}

export function fetchL5Heatmap() {
  return api.get('/l5/heatmap')
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
