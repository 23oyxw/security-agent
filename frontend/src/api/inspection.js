import api from './index'

export function fetchInspectionCatalog() {
  return api.get('/inspection/catalog')
}

export function runInspection(suiteId = 'kylin_baseline') {
  return api.post('/inspection/run', { suite_id: suiteId })
}

export function fetchInspectionRisk() {
  return api.get('/inspection/risk/predict')
}

export function fetchLatestInspectionReport(suiteId = 'kylin_baseline') {
  return api.get(`/inspection/reports/${suiteId}/latest`)
}
