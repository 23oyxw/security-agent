import api from './index'

export function fetchTraceMemo(traceId) {
  return api.get(`/trace/${traceId}/memo`)
}

export function fetchTraceViz(traceId) {
  return api.get(`/trace/${traceId}/viz`)
}