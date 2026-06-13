import api from './index'

export async function listReports() {
  return api.get('/reports/')
}

export async function analyzeTask(prompt, file = null) {
  const form = new FormData()
  form.append('prompt', prompt || '')
  if (file) form.append('file', file)
  return api.post('/reports/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function getAnalysis(analysisId) {
  return api.get('/reports/analysis/' + analysisId)
}

export function reportDownloadUrl(filename) {
  const base = api.defaults.baseURL || '/api'
  return base + '/reports/files/' + encodeURIComponent(filename)
}
